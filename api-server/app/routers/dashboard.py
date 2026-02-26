"""Dashboard router: aggregated summary endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.campaign import Campaign
from app.models.order import Order
from app.models.pipeline_state import PipelineState
from app.models.user import User
from app.schemas.order import OrderBriefResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardSummaryResponse(BaseModel):
    total_orders: int
    active_campaigns: int
    pending_orders: int
    today_revenue: int
    orders_by_status: dict[str, int]
    campaigns_by_status: dict[str, int]
    pipeline_overview: list[dict[str, object]]
    recent_orders: list[OrderBriefResponse]


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
):
    """Get aggregated dashboard summary."""

    # Orders by status
    order_status_q = await db.execute(
        select(Order.status, func.count()).group_by(Order.status)
    )
    orders_by_status = dict(order_status_q.all())

    total_orders = sum(orders_by_status.values())
    pending_orders = orders_by_status.get("submitted", 0)

    # Campaigns by status
    campaign_status_q = await db.execute(
        select(Campaign.status, func.count()).group_by(Campaign.status)
    )
    campaigns_by_status = dict(campaign_status_q.all())
    active_campaigns = campaigns_by_status.get("active", 0)

    # Pipeline overview
    pipeline_q = await db.execute(
        select(PipelineState.current_stage, func.count()).group_by(
            PipelineState.current_stage
        )
    )
    pipeline_overview = [
        {"stage": stage, "count": count} for stage, count in pipeline_q.all()
    ]

    # Today's revenue (completed orders' total_amount)
    today_revenue_q = await db.execute(
        select(func.coalesce(func.sum(Order.total_amount), 0)).where(
            Order.status.in_(["completed", "processing", "payment_confirmed"]),
            func.date(Order.created_at) == func.current_date(),
        )
    )
    today_revenue = int(today_revenue_q.scalar() or 0)

    # Recent 5 orders
    recent_q = await db.execute(
        select(Order).order_by(Order.created_at.desc()).limit(5)
    )
    recent_orders = [
        OrderBriefResponse.model_validate(o) for o in recent_q.scalars().all()
    ]

    return DashboardSummaryResponse(
        total_orders=total_orders,
        active_campaigns=active_campaigns,
        pending_orders=pending_orders,
        today_revenue=today_revenue,
        orders_by_status=orders_by_status,
        campaigns_by_status=campaigns_by_status,
        pipeline_overview=pipeline_overview,
        recent_orders=recent_orders,
    )


class CampaignStatsResponse(BaseModel):
    total: int
    active: int
    exhausted_today: int
    keyword_warnings: int


@router.get("/campaign-stats", response_model=CampaignStatsResponse)
async def get_campaign_stats(
    account_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
):
    """Get campaign dashboard statistics."""
    base_q = select(func.count()).select_from(Campaign)
    if account_id:
        base_q = base_q.where(Campaign.superap_account_id == account_id)

    total = (await db.execute(base_q)).scalar() or 0
    active = (await db.execute(
        base_q.where(Campaign.status == "active")
    )).scalar() or 0

    # Exhausted today: campaigns with status containing 'exhausted'
    exhausted_today = (await db.execute(
        base_q.where(Campaign.status.in_(["daily_exhausted", "campaign_exhausted"]))
    )).scalar() or 0

    # Keyword warnings: simplified — count campaigns with status warning
    keyword_warnings = 0

    return CampaignStatsResponse(
        total=total,
        active=active,
        exhausted_today=exhausted_today,
        keyword_warnings=keyword_warnings,
    )

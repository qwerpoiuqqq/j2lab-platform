"""Dashboard router: aggregated summary endpoint with role-based filtering.

Role visibility:
  - system_admin: 전체 데이터
  - company_admin: 자기 회사 범위
  - order_handler: 본인이 담당하는 건만 (배정된 주문/캠페인)
  - distributor: 주문만 (본인+하위), 캠페인/파이프라인 숨김
  - sub_account: 주문만 (본인), 캠페인/파이프라인 숨김
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.campaign import Campaign
from app.models.order import Order, OrderItem
from app.models.pipeline_state import PipelineState
from app.models.user import User, UserRole
from app.schemas.order import OrderBriefResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _apply_order_scope(query, user: User):
    """Apply role-based scoping to an Order query."""
    role = UserRole(user.role)
    if role == UserRole.SYSTEM_ADMIN:
        return query
    if role in (UserRole.COMPANY_ADMIN, UserRole.ORDER_HANDLER):
        return query.where(Order.company_id == user.company_id)
    if role == UserRole.DISTRIBUTOR:
        sub_q = select(User.id).where(User.parent_id == user.id)
        return query.where((Order.user_id == user.id) | Order.user_id.in_(sub_q))
    if role == UserRole.SUB_ACCOUNT:
        return query.where(Order.user_id == user.id)
    return query


def _apply_campaign_scope(query, user: User):
    """Apply role-based scoping to a Campaign query."""
    role = UserRole(user.role)
    if role == UserRole.SYSTEM_ADMIN:
        return query
    if role == UserRole.COMPANY_ADMIN:
        return query.where(Campaign.company_id == user.company_id)
    if role == UserRole.ORDER_HANDLER:
        # order_handler: 본인에게 배정된 캠페인만
        return query.where(Campaign.managed_by == user.id)
    # distributor/sub_account should not see campaigns at all
    return query.where(False)


def _can_see_campaigns(user: User) -> bool:
    """Check if user role can view campaign data."""
    return UserRole(user.role) in (
        UserRole.SYSTEM_ADMIN,
        UserRole.COMPANY_ADMIN,
        UserRole.ORDER_HANDLER,
    )


class DashboardSummaryResponse(BaseModel):
    total_orders: int
    active_campaigns: int
    pending_orders: int
    today_revenue: int
    orders_by_status: dict[str, int]
    campaigns_by_status: dict[str, int]
    pipeline_overview: list[dict[str, object]]
    recent_orders: list[OrderBriefResponse]
    user_role: str
    stuck_pipelines: int = 0


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get aggregated dashboard summary (role-scoped)."""

    # Orders by status — scoped by role
    base_order_q = select(Order.status, func.count()).group_by(Order.status)
    base_order_q = _apply_order_scope(base_order_q, current_user)
    order_status_q = await db.execute(base_order_q)
    orders_by_status = dict(order_status_q.all())

    total_orders = sum(orders_by_status.values())
    pending_orders = orders_by_status.get("submitted", 0)

    # Campaigns by status — only for roles that can see campaigns
    campaigns_by_status: dict[str, int] = {}
    active_campaigns = 0
    pipeline_overview: list[dict[str, object]] = []

    if _can_see_campaigns(current_user):
        base_campaign_q = select(Campaign.status, func.count()).group_by(Campaign.status)
        base_campaign_q = _apply_campaign_scope(base_campaign_q, current_user)
        campaign_status_q = await db.execute(base_campaign_q)
        campaigns_by_status = dict(campaign_status_q.all())
        active_campaigns = campaigns_by_status.get("active", 0)

        # Pipeline overview — scoped
        pipeline_base = select(PipelineState.current_stage, func.count()).group_by(
            PipelineState.current_stage
        )
        role = UserRole(current_user.role)
        if role != UserRole.SYSTEM_ADMIN:
            # Join through order_item → order to filter by company
            pipeline_base = (
                pipeline_base
                .join(OrderItem, PipelineState.order_item_id == OrderItem.id)
                .join(Order, OrderItem.order_id == Order.id)
                .where(Order.company_id == current_user.company_id)
            )
        pipeline_q = await db.execute(pipeline_base)
        pipeline_overview = [
            {"stage": stage, "count": count} for stage, count in pipeline_q.all()
        ]

    # Today's revenue — scoped
    revenue_q = select(func.coalesce(func.sum(Order.total_amount), 0)).where(
        Order.status.in_(["completed", "processing", "payment_confirmed"]),
        func.date(Order.created_at) == func.current_date(),
    )
    revenue_q = _apply_order_scope(revenue_q, current_user)
    today_revenue_q = await db.execute(revenue_q)
    today_revenue = int(today_revenue_q.scalar() or 0)

    # Recent 5 orders — scoped
    recent_base = select(Order).order_by(Order.created_at.desc()).limit(5)
    recent_base = _apply_order_scope(recent_base, current_user)
    recent_q = await db.execute(recent_base)
    recent_orders = [
        OrderBriefResponse.model_validate(o) for o in recent_q.scalars().all()
    ]

    # Stuck pipelines: extraction_done with an error_message (auto-assign failed)
    stuck_pipelines = 0
    if _can_see_campaigns(current_user):
        from app.models.pipeline_state import PipelineState as PS
        stuck_q = select(func.count()).select_from(PS).where(
            PS.current_stage == "extraction_done",
            PS.error_message.isnot(None),
        )
        if UserRole(current_user.role) != UserRole.SYSTEM_ADMIN:
            stuck_q = (
                select(func.count()).select_from(PS)
                .join(OrderItem, PS.order_item_id == OrderItem.id)
                .join(Order, OrderItem.order_id == Order.id)
                .where(
                    PS.current_stage == "extraction_done",
                    PS.error_message.isnot(None),
                    Order.company_id == current_user.company_id,
                )
            )
        stuck_count_q = await db.execute(stuck_q)
        stuck_pipelines = int(stuck_count_q.scalar() or 0)

    return DashboardSummaryResponse(
        total_orders=total_orders,
        active_campaigns=active_campaigns,
        pending_orders=pending_orders,
        today_revenue=today_revenue,
        orders_by_status=orders_by_status,
        campaigns_by_status=campaigns_by_status,
        pipeline_overview=pipeline_overview,
        recent_orders=recent_orders,
        user_role=current_user.role,
        stuck_pipelines=stuck_pipelines,
    )


@router.get("/enhanced")
async def get_enhanced_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Enhanced dashboard with deadlines, warnings, registration queue, weekly trend.
    All data is role-scoped.
    """
    from datetime import datetime, timedelta, timezone
    from app.models.campaign_keyword_pool import CampaignKeywordPool

    now = datetime.now(timezone.utc)

    # Upcoming deadlines — scoped
    deadline_base = select(Order).where(
        Order.completed_at.isnot(None),
        Order.completed_at >= now,
        Order.completed_at <= now + timedelta(days=7),
        Order.status.in_(["processing", "payment_confirmed"]),
    ).order_by(Order.completed_at.asc()).limit(20)
    deadline_base = _apply_order_scope(deadline_base, current_user)
    deadline_q = await db.execute(deadline_base)
    upcoming_deadlines = []
    for order in deadline_q.scalars().all():
        days_remaining = (order.completed_at - now).days
        urgency = "red" if days_remaining <= 1 else "orange" if days_remaining <= 3 else "yellow"
        upcoming_deadlines.append({
            "order_id": order.id,
            "order_number": order.order_number,
            "deadline": order.completed_at.isoformat() if order.completed_at else None,
            "days_remaining": days_remaining,
            "urgency": urgency,
            "status": order.status,
        })

    # Keyword warnings — only for campaign-visible roles
    keyword_warnings = []
    if _can_see_campaigns(current_user):
        kw_q = (
            select(
                Campaign.id,
                Campaign.place_name,
                Campaign.campaign_code,
                func.count(CampaignKeywordPool.id).filter(CampaignKeywordPool.is_used == False).label("remaining"),
                func.count(CampaignKeywordPool.id).label("total"),
            )
            .outerjoin(CampaignKeywordPool, Campaign.id == CampaignKeywordPool.campaign_id)
            .where(Campaign.status == "active")
        )
        kw_q = _apply_campaign_scope(kw_q, current_user)
        kw_q = kw_q.group_by(Campaign.id).having(
            func.count(CampaignKeywordPool.id).filter(CampaignKeywordPool.is_used == False) <= 5
        )
        keyword_warning_q = await db.execute(kw_q)
        keyword_warnings = [
            {
                "campaign_id": row[0],
                "place_name": row[1],
                "campaign_code": row[2],
                "remaining": row[3],
                "total": row[4],
            }
            for row in keyword_warning_q.all()
        ]

    # Registration queue — only for campaign-visible roles
    registration_queue = []
    if _can_see_campaigns(current_user):
        reg_base = (
            select(Campaign.status, Campaign.registration_step, func.count())
            .where(Campaign.status.in_(["pending", "queued", "registering"]))
        )
        reg_base = _apply_campaign_scope(reg_base, current_user)
        reg_base = reg_base.group_by(Campaign.status, Campaign.registration_step)
        reg_q = await db.execute(reg_base)
        registration_queue = [
            {"status": s, "registration_step": rs, "count": c}
            for s, rs, c in reg_q.all()
        ]

    # Weekly trend — scoped
    weekly_trend = []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).date()
        day_q = select(func.count()).select_from(Order).where(
            func.date(Order.created_at) == day
        )
        day_q = _apply_order_scope(day_q, current_user)
        day_count_q = await db.execute(day_q)
        weekly_trend.append({
            "date": day.isoformat(),
            "count": day_count_q.scalar() or 0,
        })

    return {
        "upcoming_deadlines": upcoming_deadlines,
        "keyword_warnings": keyword_warnings,
        "registration_queue": registration_queue,
        "weekly_trend": weekly_trend,
    }


class CampaignStatsResponse(BaseModel):
    total: int
    active: int
    exhausted_today: int
    keyword_warnings: int


@router.get("/campaign-stats", response_model=CampaignStatsResponse)
async def get_campaign_stats(
    account_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get campaign dashboard statistics (role-scoped)."""
    from app.models.campaign_keyword_pool import CampaignKeywordPool

    base_q = select(func.count()).select_from(Campaign)
    # Role scoping
    base_q = _apply_campaign_scope(base_q, current_user)
    if account_id:
        base_q = base_q.where(Campaign.superap_account_id == account_id)

    total = (await db.execute(base_q)).scalar() or 0
    active = (await db.execute(
        base_q.where(Campaign.status == "active")
    )).scalar() or 0

    exhausted_today = (await db.execute(
        base_q.where(Campaign.status.in_(["daily_exhausted", "campaign_exhausted"]))
    )).scalar() or 0

    # Real keyword warnings: active campaigns with remaining keywords <= 5
    kw_warn_q = (
        select(func.count(func.distinct(Campaign.id)))
        .outerjoin(CampaignKeywordPool, Campaign.id == CampaignKeywordPool.campaign_id)
        .where(Campaign.status == "active")
    )
    kw_warn_q = _apply_campaign_scope(kw_warn_q, current_user)
    if account_id:
        kw_warn_q = kw_warn_q.where(Campaign.superap_account_id == account_id)
    kw_warn_q = kw_warn_q.group_by(Campaign.id).having(
        func.count(CampaignKeywordPool.id).filter(CampaignKeywordPool.is_used == False) <= 5
    )
    # Count the number of campaigns matching the warning condition
    kw_warn_result = await db.execute(
        select(func.count()).select_from(kw_warn_q.subquery())
    )
    keyword_warnings = kw_warn_result.scalar() or 0

    return CampaignStatsResponse(
        total=total,
        active=active,
        exhausted_today=exhausted_today,
        keyword_warnings=keyword_warnings,
    )

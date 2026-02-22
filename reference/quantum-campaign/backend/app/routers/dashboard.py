"""대시보드 API 라우터.

Phase 3 - Task 3.9: 계정 목록, 대행사 목록, 대시보드 통계 API
"""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.campaign import Campaign
from app.models.keyword import KeywordPool


router = APIRouter(tags=["dashboard"])


# ============================================================
# Pydantic 스키마
# ============================================================

class AgencyListItem(BaseModel):
    """대행사 목록 항목."""

    agency_name: str
    campaign_count: int = 0


class AgencyListResponse(BaseModel):
    """대행사 목록 응답."""

    agencies: List[AgencyListItem]


class DashboardStatsResponse(BaseModel):
    """대시보드 통계 응답."""

    total_campaigns: int
    active_campaigns: int
    exhausted_today: int
    keyword_warnings: int


# ============================================================
# API 엔드포인트
# ============================================================

@router.get("/agencies", response_model=AgencyListResponse)
async def list_agencies(db: Session = Depends(get_db)):
    """필터용 대행사 목록 조회.

    캠페인에 등록된 대행사명 기준으로 중복 제거하여 반환합니다.
    """
    rows = (
        db.query(Campaign.agency_name, func.count(Campaign.id))
        .filter(
            Campaign.agency_name.isnot(None),
            Campaign.agency_name != "",
            Campaign.status != "pending_extend",
        )
        .group_by(Campaign.agency_name)
        .order_by(Campaign.agency_name)
        .all()
    )

    items = [
        AgencyListItem(agency_name=name, campaign_count=count)
        for name, count in rows
    ]

    return AgencyListResponse(agencies=items)


@router.get("/dashboard/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    account_id: Optional[int] = Query(None, description="계정 ID 필터 (선택)"),
    db: Session = Depends(get_db),
):
    """대시보드 통계.

    전체 캠페인 수, 활성 캠페인 수, 오늘 소진 수, 키워드 경고 수를 반환합니다.
    account_id를 지정하면 해당 계정 캠페인만 집계합니다.
    """
    base_query = db.query(Campaign).filter(
        Campaign.status != "pending_extend",
    )
    if account_id is not None:
        base_query = base_query.filter(Campaign.account_id == account_id)

    total = base_query.count()

    active = (
        base_query.filter(Campaign.status == "active")
        .count()
    )

    exhausted = (
        base_query.filter(Campaign.status == "daily_exhausted")
        .count()
    )

    # 키워드 경고: 활성 + 미종료 캠페인 중 키워드 부족인 것
    today = date.today()
    active_campaigns = (
        base_query.filter(
            Campaign.status == "active",
            Campaign.end_date >= today,
        )
        .all()
    )

    campaign_ids = [c.id for c in active_campaigns]
    unused_counts: dict = {}
    if campaign_ids:
        rows = (
            db.query(KeywordPool.campaign_id, func.count(KeywordPool.id))
            .filter(
                KeywordPool.campaign_id.in_(campaign_ids),
                KeywordPool.is_used == False,
            )
            .group_by(KeywordPool.campaign_id)
            .all()
        )
        unused_counts = dict(rows)

    keyword_warnings = 0
    for c in active_campaigns:
        remaining_days = (c.end_date - today).days + 1
        unused = unused_counts.get(c.id, 0)
        if remaining_days > 0 and unused < remaining_days * 1.5:
            keyword_warnings += 1

    return DashboardStatsResponse(
        total_campaigns=total,
        active_campaigns=active,
        exhausted_today=exhausted,
        keyword_warnings=keyword_warnings,
    )

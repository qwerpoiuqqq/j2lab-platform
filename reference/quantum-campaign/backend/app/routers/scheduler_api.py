"""스케줄러 진단 및 수동 실행 API."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.account import Account
from app.models.campaign import Campaign
from app.services.scheduler import (
    check_and_rotate_keywords,
    get_scheduler_state,
)

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


# ============================================================
# 스키마
# ============================================================

class SchedulerStatusResponse(BaseModel):
    """스케줄러 상태 응답."""

    is_running: bool
    scheduler_active: bool
    last_run: Optional[str] = None
    last_result: Optional[Dict[str, Any]] = None
    last_error: Optional[str] = None
    run_count: int
    recent_logs: List[str]


class CampaignDiagnosticItem(BaseModel):
    """캠페인 진단 항목."""

    id: int
    place_name: str
    campaign_code: Optional[str] = None
    status: Optional[str] = None
    registration_step: Optional[str] = None
    last_keyword_change: Optional[str] = None
    keyword_total: int = 0
    keyword_unused: int = 0
    account_user_id: Optional[str] = None


class DiagnosticResponse(BaseModel):
    """전체 진단 응답."""

    scheduler: SchedulerStatusResponse
    campaigns: List[CampaignDiagnosticItem]
    summary: Dict[str, Any]


class TriggerResponse(BaseModel):
    """수동 실행 응답."""

    success: bool
    message: str
    result: Optional[Dict[str, Any]] = None


# ============================================================
# 엔드포인트
# ============================================================

@router.get("/status", response_model=SchedulerStatusResponse)
async def get_status():
    """스케줄러 현재 상태 조회."""
    return SchedulerStatusResponse(**get_scheduler_state())


@router.get("/diagnostic", response_model=DiagnosticResponse)
async def get_diagnostic(db: Session = Depends(get_db)):
    """전체 시스템 진단.

    스케줄러 상태 + 캠페인 상태 + 키워드 현황을 한눈에 확인.
    """
    from sqlalchemy import func
    from app.models.keyword import KeywordPool

    # 캠페인 + 키워드 현황
    campaigns = (
        db.query(Campaign)
        .order_by(Campaign.id)
        .all()
    )

    # 키워드 통계 배치 조회
    keyword_stats = {}
    if campaigns:
        ids = [c.id for c in campaigns]
        total_rows = (
            db.query(KeywordPool.campaign_id, func.count(KeywordPool.id))
            .filter(KeywordPool.campaign_id.in_(ids))
            .group_by(KeywordPool.campaign_id)
            .all()
        )
        unused_rows = (
            db.query(KeywordPool.campaign_id, func.count(KeywordPool.id))
            .filter(
                KeywordPool.campaign_id.in_(ids),
                KeywordPool.is_used == False,
            )
            .group_by(KeywordPool.campaign_id)
            .all()
        )
        for cid, cnt in total_rows:
            keyword_stats.setdefault(cid, {})["total"] = cnt
        for cid, cnt in unused_rows:
            keyword_stats.setdefault(cid, {})["unused"] = cnt

    # 계정 매핑
    accounts = {a.id: a for a in db.query(Account).all()}

    items = []
    for c in campaigns:
        stats = keyword_stats.get(c.id, {})
        account = accounts.get(c.account_id)
        items.append(CampaignDiagnosticItem(
            id=c.id,
            place_name=c.place_name,
            campaign_code=c.campaign_code,
            status=c.status,
            registration_step=c.registration_step,
            last_keyword_change=(
                c.last_keyword_change.isoformat() if c.last_keyword_change else None
            ),
            keyword_total=stats.get("total", 0),
            keyword_unused=stats.get("unused", 0),
            account_user_id=account.user_id if account else None,
        ))

    # 요약
    summary = {
        "total_campaigns": len(campaigns),
        "with_code": sum(1 for c in campaigns if c.campaign_code),
        "without_code": sum(1 for c in campaigns if not c.campaign_code),
        "status_dist": {},
        "ever_rotated": sum(1 for c in campaigns if c.last_keyword_change),
        "never_rotated": sum(1 for c in campaigns if not c.last_keyword_change),
        "active_accounts": sum(1 for a in accounts.values() if a.is_active),
    }
    for c in campaigns:
        s = c.status or "unknown"
        summary["status_dist"][s] = summary["status_dist"].get(s, 0) + 1

    return DiagnosticResponse(
        scheduler=SchedulerStatusResponse(**get_scheduler_state()),
        campaigns=items,
        summary=summary,
    )


@router.post("/trigger", response_model=TriggerResponse)
async def trigger_rotation():
    """스케줄러 수동 실행 (상태 동기화 + 키워드 변경)."""
    state = get_scheduler_state()
    if state["is_running"]:
        return TriggerResponse(
            success=False,
            message="스케줄러가 이미 실행 중입니다. 잠시 후 다시 시도해주세요.",
        )

    try:
        result = await check_and_rotate_keywords()
        return TriggerResponse(
            success=True,
            message="스케줄러 수동 실행 완료",
            result=result,
        )
    except Exception as e:
        return TriggerResponse(
            success=False,
            message=f"실행 오류: {str(e)}",
        )

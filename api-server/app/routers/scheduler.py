"""Scheduler router: status and manual trigger (proxied to campaign-worker)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import RoleChecker
from app.models.user import User, UserRole
from app.schemas.common import MessageResponse
from app.services.worker_clients import (
    WorkerDispatchError,
    get_campaign_worker_scheduler_status,
    trigger_campaign_worker_scheduler,
)
from pydantic import BaseModel

router = APIRouter(prefix="/scheduler", tags=["scheduler"])

admin_checker = RoleChecker([
    UserRole.SYSTEM_ADMIN,
    UserRole.COMPANY_ADMIN,
    UserRole.ORDER_HANDLER,
])


class SchedulerStatusResponse(BaseModel):
    status: str = "waiting"
    last_run: str | None = None
    execution_count: int = 0
    keyword_changes: int = 0
    keyword_failures: int = 0
    skipped_today: int = 0
    error_message: str | None = None
    recent_logs: list = []


@router.get("/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status(
    _current_user: User = Depends(admin_checker),
):
    """Get keyword rotation scheduler status from campaign-worker."""
    try:
        data = await get_campaign_worker_scheduler_status()
        return SchedulerStatusResponse(**data)
    except WorkerDispatchError:
        return SchedulerStatusResponse(
            status="unreachable",
            error_message="Campaign worker is not reachable",
        )


@router.post("/trigger", response_model=MessageResponse)
async def trigger_scheduler(
    _current_user: User = Depends(admin_checker),
):
    """Manually trigger keyword rotation on campaign-worker."""
    try:
        await trigger_campaign_worker_scheduler()
        return MessageResponse(message="Scheduler triggered successfully")
    except WorkerDispatchError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Campaign worker error: {e}",
        )

"""Scheduler router: status and manual trigger (stub for campaign-worker integration)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.deps import RoleChecker, get_current_active_user
from app.models.user import User, UserRole
from app.schemas.common import MessageResponse

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
    """Get keyword rotation scheduler status.

    This is a stub — will be connected to campaign-worker in Phase 3.
    """
    return SchedulerStatusResponse(
        status="waiting",
        last_run=None,
        execution_count=0,
        keyword_changes=0,
        keyword_failures=0,
        skipped_today=0,
    )


@router.post("/trigger", response_model=MessageResponse)
async def trigger_scheduler(
    _current_user: User = Depends(admin_checker),
):
    """Manually trigger keyword rotation.

    This is a stub — will be connected to campaign-worker in Phase 3.
    """
    return MessageResponse(message="Scheduler trigger queued (stub)")

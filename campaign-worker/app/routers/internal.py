"""Internal API router for campaign-worker.

These endpoints are only accessible within the Docker network.
api-server calls these to manage campaign operations.

Endpoints:
- POST /internal/campaigns/register     - Register a campaign on superap.io
- POST /internal/campaigns/{id}/extend   - Extend a campaign
- POST /internal/campaigns/{id}/rotate   - Manual keyword rotation
- POST /internal/campaigns/bulk-sync     - Bulk status sync
- GET  /internal/scheduler/status        - Scheduler status
- POST /internal/scheduler/trigger       - Manual scheduler trigger
- GET  /internal/health                  - Health check
"""

from __future__ import annotations

import logging
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.campaign_registrar import (
    extend_campaign,
    register_campaign,
)
from app.services.campaign_syncer import bulk_sync_campaigns
from app.services.keyword_rotator import (
    check_and_rotate_keywords,
    get_scheduler_state,
    rotate_keywords_for_campaign,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])


# ==================== Request/Response Schemas ====================


class RegisterCampaignRequest(BaseModel):
    """Request to register a campaign on superap.io."""

    campaign_id: int = Field(..., description="Campaign DB ID")
    account_id: Optional[int] = Field(
        None, description="Superap account DB ID (optional, uses campaign's assigned account)"
    )
    template_id: Optional[int] = Field(
        None, description="Campaign template DB ID (optional)"
    )


class RegisterCampaignResponse(BaseModel):
    """Response for campaign registration."""

    success: bool
    campaign_id: int
    campaign_code: Optional[str] = None
    message: str


class ExtendCampaignRequest(BaseModel):
    """Request to extend a campaign."""

    new_end_date: date = Field(..., description="New end date")
    additional_total: int = Field(..., ge=1, description="Additional total limit")
    new_daily_limit: Optional[int] = Field(
        None, ge=1, description="New daily limit (optional)"
    )


class ExtendCampaignResponse(BaseModel):
    """Response for campaign extension."""

    success: bool
    campaign_id: int
    new_total_limit: Optional[int] = None
    new_end_date: Optional[str] = None
    message: str


class RotateKeywordsResponse(BaseModel):
    """Response for keyword rotation."""

    success: bool
    message: str
    keywords_used: int = 0
    remaining: int = 0


class BulkSyncRequest(BaseModel):
    """Request for bulk campaign status sync."""

    account_ids: Optional[List[int]] = Field(
        None, description="Optional list of account IDs to sync (all if empty)"
    )


class BulkSyncResponse(BaseModel):
    """Response for bulk sync."""

    success: bool
    synced_count: int = 0
    accounts_processed: int = 0
    message: str


class SchedulerStatusResponse(BaseModel):
    """Scheduler status response."""

    is_running: bool
    scheduler_active: bool
    last_run: Optional[str] = None
    run_count: int = 0
    last_error: Optional[str] = None
    recent_logs: List[str] = []


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    service: str
    version: str


# ==================== Endpoints ====================


@router.post("/campaigns/register", response_model=RegisterCampaignResponse)
async def api_register_campaign(
    request: RegisterCampaignRequest,
    background_tasks: BackgroundTasks,
):
    """Register a campaign on superap.io.

    The registration runs in the background. Use scheduler status or
    campaign status polling to track progress.
    """
    campaign_id = request.campaign_id

    # Run registration in background
    background_tasks.add_task(register_campaign, campaign_id)

    logger.info(f"Campaign {campaign_id} registration queued")

    return RegisterCampaignResponse(
        success=True,
        campaign_id=campaign_id,
        message="Registration queued",
    )


@router.post("/campaigns/{campaign_id}/extend", response_model=ExtendCampaignResponse)
async def api_extend_campaign(
    campaign_id: int,
    request: ExtendCampaignRequest,
    background_tasks: BackgroundTasks,
):
    """Extend a campaign (update total limit and end date on superap.io)."""

    async def _do_extend() -> None:
        result = await extend_campaign(
            campaign_id=campaign_id,
            new_end_date=request.new_end_date,
            additional_total=request.additional_total,
            new_daily_limit=request.new_daily_limit,
        )
        if result.get("success"):
            logger.info(f"Campaign {campaign_id} extended successfully")
        else:
            logger.error(f"Campaign {campaign_id} extension failed: {result.get('error')}")

    background_tasks.add_task(_do_extend)

    return ExtendCampaignResponse(
        success=True,
        campaign_id=campaign_id,
        message="Extension queued",
    )


@router.post("/campaigns/{campaign_id}/rotate-keywords", response_model=RotateKeywordsResponse)
async def api_rotate_keywords(campaign_id: int):
    """Manually trigger keyword rotation for a specific campaign.

    Unlike automatic rotation, this runs synchronously and returns the result.
    Note: requires the account to be logged in via the scheduler or a recent operation.
    This endpoint creates a temporary client for the rotation.
    """
    from app.services.superap_client import SuperapClient
    from app.core.database import async_session_factory
    from app.models.campaign import Campaign
    from app.models.superap_account import SuperapAccount
    from app.utils.crypto import decrypt_password
    from sqlalchemy import select

    # Load campaign and account
    async with async_session_factory() as session:
        result = await session.execute(
            select(Campaign).where(Campaign.id == campaign_id)
        )
        campaign = result.scalar_one_or_none()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if not campaign.campaign_code:
            raise HTTPException(
                status_code=400, detail="Campaign has no superap code"
            )

        account_result = await session.execute(
            select(SuperapAccount).where(
                SuperapAccount.id == campaign.superap_account_id
            )
        )
        account = account_result.scalar_one_or_none()
        if not account:
            raise HTTPException(status_code=400, detail="Account not found")

    # Create temporary client and rotate
    client = SuperapClient(headless=settings.PLAYWRIGHT_HEADLESS)
    try:
        await client.initialize()
        password = decrypt_password(account.password_encrypted)
        login_ok = await client.login(
            str(account.id), account.user_id_superap, password
        )
        if not login_ok:
            raise HTTPException(status_code=500, detail="Login failed")

        rot_result = await rotate_keywords_for_campaign(
            campaign_id=campaign_id,
            client=client,
            trigger_type="manual",
        )

        return RotateKeywordsResponse(
            success=rot_result.get("success", False),
            message=rot_result.get("message", ""),
            keywords_used=rot_result.get("keywords_used", 0),
            remaining=rot_result.get("remaining", 0),
        )
    finally:
        try:
            await client.close()
        except Exception:
            pass


@router.post("/campaigns/bulk-sync", response_model=BulkSyncResponse)
async def api_bulk_sync(
    request: BulkSyncRequest,
    background_tasks: BackgroundTasks,
):
    """Trigger bulk campaign status sync from superap.io.

    Runs in the background.
    """

    async def _do_sync() -> None:
        result = await bulk_sync_campaigns(account_ids=request.account_ids)
        logger.info(f"Bulk sync result: {result}")

    background_tasks.add_task(_do_sync)

    return BulkSyncResponse(
        success=True,
        message="Bulk sync queued",
    )


@router.get("/scheduler/status", response_model=SchedulerStatusResponse)
async def api_scheduler_status():
    """Get current scheduler status."""
    state = get_scheduler_state()
    return SchedulerStatusResponse(
        is_running=state.get("is_running", False),
        scheduler_active=state.get("scheduler_active", False),
        last_run=state.get("last_run"),
        run_count=state.get("run_count", 0),
        last_error=state.get("last_error"),
        recent_logs=state.get("recent_logs", []),
    )


@router.post("/scheduler/trigger")
async def api_trigger_scheduler(background_tasks: BackgroundTasks):
    """Manually trigger the keyword rotation scheduler."""
    state = get_scheduler_state()
    if state.get("is_running"):
        raise HTTPException(
            status_code=409, detail="Scheduler is already running"
        )

    background_tasks.add_task(check_and_rotate_keywords)

    return {"status": "ok", "message": "Scheduler triggered"}


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
    )

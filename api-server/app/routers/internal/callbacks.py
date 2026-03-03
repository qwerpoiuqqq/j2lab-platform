"""Internal callback router: worker -> api-server notifications.

These endpoints are called by keyword-worker and campaign-worker
to report job completion/failure. They trigger pipeline state transitions.

In production, these should only be accessible from the Docker internal network.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import verify_internal_secret
from app.schemas.campaign import CampaignCallbackRequest
from app.schemas.extraction_job import ExtractionCallbackRequest
from app.services import campaign_service, extraction_service, pipeline_service
from app.services import pipeline_orchestrator
from app.services import notification_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/callback", tags=["internal-callbacks"])


@router.post("/extraction/{job_id}")
async def extraction_callback(
    job_id: int,
    body: ExtractionCallbackRequest,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(verify_internal_secret),
):
    """Callback from keyword-worker when extraction completes or fails.

    Triggers:
    1. Update extraction job status
    2. Update pipeline state (extraction_done or failed)
    3. If completed, auto-assign could be triggered (Phase 1C interface only)
    """
    job = await extraction_service.get_job_by_id(db, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extraction job not found",
        )

    # Update extraction job
    updated_job = await extraction_service.handle_extraction_callback(
        db,
        job=job,
        status=body.status,
        result_count=body.result_count,
        place_id=body.place_id,
        place_name=body.place_name,
        error_message=body.error_message,
    )

    # Update pipeline state if linked to an order item
    if updated_job.order_item_id:
        pipeline_state = await pipeline_service.get_pipeline_state(
            db, updated_job.order_item_id
        )
        if pipeline_state:
            if body.status == "running":
                try:
                    await pipeline_service.transition_stage(
                        db,
                        state=pipeline_state,
                        to_stage="extraction_running",
                        trigger_type="auto_extraction_running",
                        message="Extraction job started",
                    )
                except ValueError:
                    pass  # Already past extraction_queued
            elif body.status == "completed":
                try:
                    # If still at extraction_queued (running callback was missed),
                    # transition through extraction_running first
                    if pipeline_state.current_stage == "extraction_queued":
                        await pipeline_service.transition_stage(
                            db,
                            state=pipeline_state,
                            to_stage="extraction_running",
                            trigger_type="auto_extraction_running",
                            message="Extraction running (inferred from completion)",
                        )

                    await pipeline_service.transition_stage(
                        db,
                        state=pipeline_state,
                        to_stage="extraction_done",
                        trigger_type="auto_extraction_complete",
                        message=f"Extraction completed: {body.result_count} keywords",
                    )
                    # Link extraction job to pipeline
                    pipeline_state.extraction_job_id = updated_job.id
                    await db.flush()

                    # Trigger auto-assignment
                    try:
                        await pipeline_orchestrator.on_extraction_complete(
                            db, updated_job.order_item_id, updated_job
                        )
                    except Exception as e:
                        logger.error(
                            "Auto-assignment trigger failed for item %s: %s",
                            updated_job.order_item_id,
                            e,
                        )
                except ValueError:
                    pass  # Transition not valid from current state
            elif body.status == "failed":
                try:
                    await pipeline_service.transition_stage(
                        db,
                        state=pipeline_state,
                        to_stage="failed",
                        trigger_type="error",
                        error_message=body.error_message,
                    )
                except ValueError:
                    pass

    return {
        "message": f"Extraction callback processed: {body.status}",
        "job_id": job_id,
    }


@router.post("/campaign/{campaign_id}")
async def campaign_callback(
    campaign_id: int,
    body: CampaignCallbackRequest,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(verify_internal_secret),
):
    """Callback from campaign-worker when registration completes or fails.

    Triggers:
    1. Update campaign status
    2. Update pipeline state (campaign_active or failed)
    """
    campaign = await campaign_service.get_campaign_by_id(db, campaign_id)
    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )

    # Update campaign
    updated_campaign = await campaign_service.handle_campaign_callback(
        db,
        campaign=campaign,
        status=body.status,
        campaign_code=body.campaign_code,
        error_message=body.error_message,
        registration_step=body.registration_step,
    )

    # Send campaign notifications (best-effort)
    if body.status == "active":
        try:
            await notification_service.notify_campaign_activated(db, updated_campaign)
        except Exception as e:
            logger.error("notify_campaign_activated failed for campaign %s: %s", campaign_id, e)
    elif body.status == "failed":
        try:
            await notification_service.notify_campaign_failed(
                db, updated_campaign, body.error_message or "Unknown error"
            )
        except Exception as e:
            logger.error("notify_campaign_failed failed for campaign %s: %s", campaign_id, e)

    # Update pipeline state if linked to an order item
    if updated_campaign.order_item_id:
        pipeline_state = await pipeline_service.get_pipeline_state(
            db, updated_campaign.order_item_id
        )
        if pipeline_state:
            if body.status == "active":
                try:
                    await pipeline_service.transition_stage(
                        db,
                        state=pipeline_state,
                        to_stage="campaign_active",
                        trigger_type="auto_registration_complete",
                        message=f"Campaign registered: {body.campaign_code}",
                    )
                    # Link campaign to pipeline
                    pipeline_state.campaign_id = updated_campaign.id
                    await db.flush()

                    # Auto-complete order item
                    from app.models.order import OrderItem, OrderItemStatus, Order, OrderStatus
                    item_result = await db.execute(
                        select(OrderItem).where(OrderItem.id == updated_campaign.order_item_id)
                    )
                    order_item = item_result.scalar_one_or_none()
                    if order_item and order_item.status != OrderItemStatus.COMPLETED.value:
                        order_item.status = OrderItemStatus.COMPLETED.value
                        order_item.result_message = f"캠페인 등록 완료: {body.campaign_code}"
                        await db.flush()

                        # Check if all items in order are completed
                        order_result = await db.execute(
                            select(Order).where(Order.id == order_item.order_id)
                        )
                        order = order_result.scalar_one_or_none()
                        if order:
                            all_items = order.items
                            all_done = all(
                                i.status in (OrderItemStatus.COMPLETED.value, OrderItemStatus.FAILED.value)
                                for i in all_items
                            )
                            if all_done and order.status == OrderStatus.PROCESSING.value:
                                order.status = OrderStatus.COMPLETED.value
                                order.completed_at = order.completed_at or datetime.now(timezone.utc)
                                await db.flush()
                                logger.info("Order %s auto-completed (all items done)", order.id)
                except ValueError:
                    pass
            elif body.status == "failed":
                try:
                    await pipeline_service.transition_stage(
                        db,
                        state=pipeline_state,
                        to_stage="failed",
                        trigger_type="error",
                        error_message=body.error_message,
                    )
                except ValueError:
                    pass

    return {
        "message": f"Campaign callback processed: {body.status}",
        "campaign_id": campaign_id,
    }


# ============================================================
# Conversion threshold callback
# ============================================================


class ConversionThresholdCallbackRequest(BaseModel):
    """Request body for conversion threshold callback."""

    event_type: str  # "switched", "exhausted", "error"
    message: str
    new_campaign_id: Optional[int] = None


@router.post("/conversion-threshold/{campaign_id}")
async def conversion_threshold_callback(
    campaign_id: int,
    body: ConversionThresholdCallbackRequest,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(verify_internal_secret),
):
    """Callback from campaign-worker when a campaign exceeds conversion threshold.

    Creates a notification for system admins about the network switch event.
    """
    campaign = await campaign_service.get_campaign_by_id(db, campaign_id)
    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )

    # Determine notification type and title based on event
    if body.event_type == "switched":
        title = f"[네트워크 자동 전환] {campaign.place_name}"
        notif_type = "campaign"
    elif body.event_type == "exhausted":
        title = f"[네트워크 소진 경고] {campaign.place_name}"
        notif_type = "campaign"
    else:
        title = f"[전환수 초과 오류] {campaign.place_name}"
        notif_type = "system"

    # Find system_admin users to notify
    from app.models.user import User
    admin_result = await db.execute(
        select(User).where(User.role == "system_admin", User.is_active.is_(True))
    )
    admins = list(admin_result.scalars().all())

    # Also notify the campaign's handler if set
    handler_ids = set()
    if campaign.managed_by:
        handler_ids.add(campaign.managed_by)
    for admin in admins:
        handler_ids.add(admin.id)

    for user_id in handler_ids:
        await notification_service.create_notification(
            db,
            user_id=user_id,
            type=notif_type,
            title=title,
            message=body.message,
            related_id=campaign_id,
        )

    await db.flush()

    logger.info(
        "Conversion threshold callback processed: campaign=%s, event=%s, notified=%d users",
        campaign_id,
        body.event_type,
        len(handler_ids),
    )

    return {
        "message": f"Conversion threshold callback processed: {body.event_type}",
        "campaign_id": campaign_id,
        "notified_users": len(handler_ids),
    }

"""Internal callback router: worker -> api-server notifications.

These endpoints are called by keyword-worker and campaign-worker
to report job completion/failure. They trigger pipeline state transitions.

In production, these should only be accessible from the Docker internal network.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.campaign import CampaignCallbackRequest
from app.schemas.extraction_job import ExtractionCallbackRequest
from app.services import campaign_service, extraction_service, pipeline_service

router = APIRouter(prefix="/internal/callback", tags=["internal-callbacks"])


@router.post("/extraction/{job_id}")
async def extraction_callback(
    job_id: int,
    body: ExtractionCallbackRequest,
    db: AsyncSession = Depends(get_db),
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
            if body.status == "completed":
                try:
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

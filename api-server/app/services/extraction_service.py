"""Extraction service: manages extraction jobs on api-server side.

The actual extraction happens in keyword-worker. This service:
- Creates extraction job records
- Updates status on callbacks
- Coordinates with pipeline service
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction_job import ExtractionJob, ExtractionJobStatus
from app.schemas.extraction_job import ExtractionJobCreate

logger = logging.getLogger(__name__)


async def get_jobs(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    status: str | None = None,
) -> tuple[list[ExtractionJob], int]:
    """Get paginated extraction jobs."""
    query = select(ExtractionJob)
    count_query = select(func.count()).select_from(ExtractionJob)

    if status:
        query = query.where(ExtractionJob.status == status)
        count_query = count_query.where(ExtractionJob.status == status)

    query = query.order_by(ExtractionJob.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    jobs = list(result.scalars().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    return jobs, total


async def get_job_by_id(
    db: AsyncSession, job_id: int
) -> ExtractionJob | None:
    """Get a single extraction job by ID."""
    result = await db.execute(
        select(ExtractionJob).where(ExtractionJob.id == job_id)
    )
    return result.scalar_one_or_none()


async def create_job(
    db: AsyncSession, data: ExtractionJobCreate
) -> ExtractionJob:
    """Create a new extraction job (status: queued).

    In production, this would also dispatch the job to keyword-worker.
    """
    job = ExtractionJob(
        order_item_id=data.order_item_id,
        naver_url=data.naver_url,
        target_count=data.target_count,
        max_rank=data.max_rank,
        min_rank=data.min_rank,
        name_keyword_ratio=data.name_keyword_ratio,
        status=ExtractionJobStatus.QUEUED.value,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)

    # Dispatch is handled by pipeline_orchestrator to avoid double dispatch
    return job


async def cancel_job(db: AsyncSession, job: ExtractionJob) -> ExtractionJob:
    """Cancel a queued or running extraction job."""
    if job.status not in (
        ExtractionJobStatus.QUEUED.value,
        ExtractionJobStatus.RUNNING.value,
    ):
        raise ValueError(
            f"Cannot cancel job in '{job.status}' status. "
            "Only queued or running jobs can be cancelled."
        )
    job.status = ExtractionJobStatus.CANCELLED.value
    job.completed_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(job)

    # Notify worker to cancel
    try:
        from app.services.worker_clients import cancel_extraction_job
        await cancel_extraction_job(job.id)
    except Exception as e:
        logger.warning("Failed to notify worker about cancellation of job %s: %s", job.id, e)

    return job


async def handle_extraction_callback(
    db: AsyncSession,
    job: ExtractionJob,
    status: str,
    result_count: int | None = None,
    place_id: int | None = None,
    place_name: str | None = None,
    error_message: str | None = None,
) -> ExtractionJob:
    """Handle callback from keyword-worker.

    Updates job status and links to place if extraction completed.
    Cancelled callbacks can carry partial extraction counts.
    """
    now = datetime.now(timezone.utc)

    if status == "completed":
        job.status = ExtractionJobStatus.COMPLETED.value
        job.result_count = result_count or 0
        job.place_id = place_id
        job.place_name = place_name
        job.completed_at = now
    elif status == "failed":
        job.status = ExtractionJobStatus.FAILED.value
        job.error_message = error_message
        job.completed_at = now
    elif status == "cancelled":
        job.status = ExtractionJobStatus.CANCELLED.value
        job.result_count = result_count or 0
        job.place_id = place_id
        job.place_name = place_name
        job.error_message = error_message
        job.completed_at = now
    elif status == "running":
        job.status = ExtractionJobStatus.RUNNING.value
        job.started_at = now
    else:
        raise ValueError(f"Invalid callback status: {status}")

    await db.flush()
    await db.refresh(job)
    return job

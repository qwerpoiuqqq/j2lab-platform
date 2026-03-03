"""Internal API router for keyword-worker.

These endpoints are only accessible within the Docker network.
api-server calls these to manage extraction jobs.

Endpoints:
- POST /internal/jobs          - Create extraction job
- GET  /internal/jobs/{id}/status  - Get job status
- GET  /internal/jobs/{id}/results - Get job results
- POST /internal/jobs/{id}/cancel  - Cancel job
- GET  /internal/health        - Health check
- GET  /internal/capacity      - Current capacity info
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.extraction_job import ExtractionJob, ExtractionJobStatus
from app.services.extraction_service import extraction_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])


# ==================== Request/Response Schemas ====================


class CreateJobRequest(BaseModel):
    """Request body for creating an extraction job."""

    job_id: Optional[int] = Field(
        None,
        description="Pre-assigned job ID from api-server (if not provided, uses DB auto-increment)",
    )
    naver_url: str = Field(..., description="Naver Place URL to extract keywords from")
    target_count: int = Field(100, ge=10, le=500, description="Target keyword count")
    max_rank: int = Field(50, ge=5, le=100, description="Maximum rank to check")
    min_rank: int = Field(1, ge=1, description="Minimum rank filter")
    name_keyword_ratio: float = Field(
        0.30,
        ge=0.0,
        le=1.0,
        description="Ratio of name-based keywords",
    )
    order_item_id: Optional[int] = Field(
        None, description="Associated order item ID"
    )


class CreateJobResponse(BaseModel):
    """Response for job creation."""

    job_id: int
    status: str
    message: str


class JobStatusResponse(BaseModel):
    """Response for job status query."""

    job_id: int
    status: str
    place_name: Optional[str] = None
    result_count: int = 0
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class JobResultsResponse(BaseModel):
    """Response for job results query."""

    job_id: int
    status: str
    result_count: int = 0
    results: Optional[list] = None


class PlaceNameResponse(BaseModel):
    """Response for place name lookup."""

    place_id: int
    place_name: str | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    service: str
    version: str


class CapacityResponse(BaseModel):
    """Capacity information response."""

    max_concurrent_jobs: int
    running_jobs: int
    available_slots: int


# ==================== Endpoints ====================


@router.post("/jobs", response_model=CreateJobResponse)
async def create_job(
    request: CreateJobRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Create a new keyword extraction job.

    The job will be queued and executed in the background.
    """
    # Check capacity
    running = len(extraction_service._running_jobs)
    if running >= settings.MAX_CONCURRENT_JOBS:
        raise HTTPException(
            status_code=429,
            detail=f"Worker at capacity ({running}/{settings.MAX_CONCURRENT_JOBS} jobs running)",
        )

    # Create job record in DB
    if request.job_id:
        # Use pre-assigned ID from api-server
        existing = await db.get(ExtractionJob, request.job_id)
        if existing:
            if existing.status == ExtractionJobStatus.QUEUED.value:
                # Re-queue existing job
                background_tasks.add_task(
                    extraction_service.execute_job, existing.id
                )
                return CreateJobResponse(
                    job_id=existing.id,
                    status="queued",
                    message="Job re-queued successfully",
                )
            raise HTTPException(
                status_code=409,
                detail=f"Job {request.job_id} already exists with status: {existing.status}",
            )
        job = ExtractionJob(
            id=request.job_id,
            naver_url=request.naver_url,
            target_count=request.target_count,
            max_rank=request.max_rank,
            min_rank=request.min_rank,
            name_keyword_ratio=request.name_keyword_ratio,
            order_item_id=request.order_item_id,
            status=ExtractionJobStatus.QUEUED.value,
        )
    else:
        job = ExtractionJob(
            naver_url=request.naver_url,
            target_count=request.target_count,
            max_rank=request.max_rank,
            min_rank=request.min_rank,
            name_keyword_ratio=request.name_keyword_ratio,
            order_item_id=request.order_item_id,
            status=ExtractionJobStatus.QUEUED.value,
        )

    db.add(job)
    await db.flush()
    job_id = job.id
    await db.commit()

    # Start job in background
    background_tasks.add_task(extraction_service.execute_job, job_id)

    logger.info("Job %d created for URL: %s", job_id, request.naver_url)

    return CreateJobResponse(
        job_id=job_id,
        status="queued",
        message="Job queued successfully",
    )


@router.get("/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get the current status of an extraction job."""
    job = await db.get(ExtractionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        place_name=job.place_name,
        result_count=job.result_count,
        error_message=job.error_message,
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )


@router.get("/jobs/{job_id}/results", response_model=JobResultsResponse)
async def get_job_results(
    job_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get the results of a completed extraction job."""
    job = await db.get(ExtractionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobResultsResponse(
        job_id=job.id,
        status=job.status,
        result_count=job.result_count,
        results=job.results,
    )


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Cancel a running or queued extraction job."""
    job = await db.get(ExtractionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in (
        ExtractionJobStatus.QUEUED.value,
        ExtractionJobStatus.RUNNING.value,
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job with status: {job.status}",
        )

    # Signal the running job to stop
    extraction_service.cancel_job(job_id)

    # If still queued (not yet picked up), mark as cancelled directly
    if job.status == ExtractionJobStatus.QUEUED.value:
        job.status = ExtractionJobStatus.CANCELLED.value
        await db.commit()

    return {"status": "ok", "message": f"Job {job_id} cancellation requested"}


@router.get("/place-name/{place_id}", response_model=PlaceNameResponse)
async def get_place_name(place_id: int):
    """Lightweight place name lookup using Playwright.

    Opens a headless browser, navigates to the Naver Place page,
    and extracts just the business name from Apollo State.
    """
    from app.services.place_scraper import PlaceScraper

    url = f"https://m.place.naver.com/restaurant/{place_id}/home"
    try:
        async with PlaceScraper(headless=True) as scraper:
            place_data = await scraper.get_place_data_by_url(url)
            if place_data and place_data.name:
                return PlaceNameResponse(
                    place_id=place_id,
                    place_name=place_data.name,
                )
        return PlaceNameResponse(place_id=place_id, place_name=None)
    except Exception as e:
        logger.warning("Place name lookup failed for %d: %s", place_id, e)
        return PlaceNameResponse(
            place_id=place_id,
            place_name=None,
            error=str(e),
        )


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
    )


@router.get("/capacity", response_model=CapacityResponse)
async def get_capacity():
    """Get current worker capacity information."""
    running = len(extraction_service._running_jobs)
    return CapacityResponse(
        max_concurrent_jobs=settings.MAX_CONCURRENT_JOBS,
        running_jobs=running,
        available_slots=max(0, settings.MAX_CONCURRENT_JOBS - running),
    )

"""Extraction jobs router: manage keyword extraction jobs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import RoleChecker, get_current_active_user
from app.models.user import User, UserRole
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.extraction_job import ExtractionJobCreate, ExtractionJobResponse
from app.services import extraction_service

router = APIRouter(prefix="/extraction", tags=["extraction"])

admin_checker = RoleChecker([
    UserRole.SYSTEM_ADMIN,
    UserRole.COMPANY_ADMIN,
    UserRole.ORDER_HANDLER,
])


@router.post(
    "/start",
    response_model=ExtractionJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_extraction(
    body: ExtractionJobCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Start a new keyword extraction job.

    In production, this dispatches to keyword-worker.
    For Phase 1C, it creates the job record in queued status.
    """
    job = await extraction_service.create_job(db, body)
    return job


@router.get("/jobs", response_model=PaginatedResponse[ExtractionJobResponse])
async def list_jobs(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
):
    """List extraction jobs."""
    pagination = PaginationParams(page=page, size=size)
    jobs, total = await extraction_service.get_jobs(
        db,
        skip=pagination.offset,
        limit=pagination.size,
        status=status_filter,
    )
    return PaginatedResponse.create(
        items=[ExtractionJobResponse.model_validate(j) for j in jobs],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.get("/jobs/{job_id}", response_model=ExtractionJobResponse)
async def get_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
):
    """Get extraction job details/results."""
    job = await extraction_service.get_job_by_id(db, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extraction job not found",
        )
    return job


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=ExtractionJobResponse,
)
async def cancel_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Cancel a queued or running extraction job."""
    job = await extraction_service.get_job_by_id(db, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extraction job not found",
        )
    try:
        updated = await extraction_service.cancel_job(db, job)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return updated

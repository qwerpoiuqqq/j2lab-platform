"""Pipeline router: state and log queries."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.pipeline import (
    PipelineLogResponse,
    PipelineOverviewItem,
    PipelineStateResponse,
)
from app.services import pipeline_service

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.get("/overview")
async def get_pipeline_overview(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
):
    """Get count of pipeline states by stage."""
    rows = await pipeline_service.get_pipeline_overview(db)
    return {
        "stages": [
            PipelineOverviewItem(stage=stage, count=count)
            for stage, count in rows
        ]
    }


@router.get("/{order_item_id}", response_model=PipelineStateResponse)
async def get_pipeline_state(
    order_item_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
):
    """Get pipeline state for an order item."""
    state = await pipeline_service.get_pipeline_state(db, order_item_id)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline state not found for this order item",
        )
    return state


@router.get(
    "/{order_item_id}/logs",
    response_model=PaginatedResponse[PipelineLogResponse],
)
async def get_pipeline_logs(
    order_item_id: int,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
):
    """Get pipeline transition logs."""
    state = await pipeline_service.get_pipeline_state(db, order_item_id)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline state not found for this order item",
        )

    pagination = PaginationParams(page=page, size=size)
    logs, total = await pipeline_service.get_pipeline_logs(
        db,
        pipeline_state_id=state.id,
        skip=pagination.offset,
        limit=pagination.size,
    )
    return PaginatedResponse.create(
        items=[PipelineLogResponse.model_validate(lg) for lg in logs],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )

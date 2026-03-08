"""Pipeline router: state and log queries + manual extraction trigger."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import RoleChecker, get_current_active_user
from app.models.order import OrderItem
from app.models.user import User, UserRole
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.pipeline import (
    PipelineLogResponse,
    PipelineOverviewItem,
    PipelineStateResponse,
)
from app.services import pipeline_orchestrator, pipeline_service

logger = logging.getLogger(__name__)

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


@router.post("/retry-stuck", response_model=MessageResponse)
async def retry_stuck_pipelines(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(RoleChecker([UserRole.SYSTEM_ADMIN])),
):
    """Retry pipelines stuck for >5 minutes. system_admin only."""
    result = await pipeline_orchestrator.retry_stuck_pipelines(db)
    return MessageResponse(
        message=f"Retried {result['retried']} pipelines ({result['skipped']} skipped, {result['total_stuck']} total stuck)",
        detail=result,
    )


@router.post("/{order_item_id}/start-extraction", response_model=MessageResponse)
async def start_extraction_manually(
    order_item_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(
        RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ORDER_HANDLER])
    ),
):
    """Manually start extraction for an order item (skip deadline wait).

    Only works when pipeline is at payment_confirmed stage.
    """
    state = await pipeline_service.get_pipeline_state(db, order_item_id)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline state not found for this order item",
        )

    if state.current_stage != "payment_confirmed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"현재 단계가 '{state.current_stage}'입니다. 'payment_confirmed' 단계에서만 수동 시작할 수 있습니다.",
        )

    item_result = await db.execute(
        select(OrderItem).where(OrderItem.id == order_item_id)
    )
    item = item_result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order item not found",
        )

    try:
        await pipeline_orchestrator._advance_to_extraction(db, item, state)
        await db.commit()
    except Exception as e:
        logger.exception("Manual extraction start failed for item %s", order_item_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"추출 시작에 실패했습니다: {str(e)}",
        )

    # Dispatch to keyword-worker AFTER commit
    try:
        await pipeline_orchestrator.dispatch_pending_extraction_jobs(db)
    except Exception:
        logger.exception("Extraction dispatch failed for item %s (job created but not dispatched)", order_item_id)

    return MessageResponse(message=f"키워드 추출이 시작되었습니다 (order_item_id={order_item_id})")


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

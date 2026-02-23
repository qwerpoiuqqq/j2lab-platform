"""Pipeline service: state machine management for order item pipelines."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline_log import PipelineLog
from app.models.pipeline_state import (
    PipelineStage,
    PipelineState,
    VALID_PIPELINE_TRANSITIONS,
)


async def get_pipeline_state(
    db: AsyncSession, order_item_id: int
) -> PipelineState | None:
    """Get pipeline state for an order item."""
    result = await db.execute(
        select(PipelineState).where(
            PipelineState.order_item_id == order_item_id
        )
    )
    return result.scalar_one_or_none()


async def create_pipeline_state(
    db: AsyncSession,
    order_item_id: int,
    initial_stage: str = PipelineStage.DRAFT.value,
) -> PipelineState:
    """Create a new pipeline state for an order item."""
    state = PipelineState(
        order_item_id=order_item_id,
        current_stage=initial_stage,
    )
    db.add(state)
    await db.flush()
    await db.refresh(state)

    # Log initial state
    log = PipelineLog(
        pipeline_state_id=state.id,
        from_stage=None,
        to_stage=initial_stage,
        trigger_type="user_action",
        message="Pipeline created",
    )
    db.add(log)
    await db.flush()

    return state


async def transition_stage(
    db: AsyncSession,
    state: PipelineState,
    to_stage: str,
    trigger_type: str = "user_action",
    message: str | None = None,
    error_message: str | None = None,
) -> PipelineState:
    """Transition pipeline state to a new stage.

    Validates the transition is allowed, updates state, and creates a log entry.
    """
    current = PipelineStage(state.current_stage)
    target = PipelineStage(to_stage)

    valid_targets = VALID_PIPELINE_TRANSITIONS.get(current, [])
    if target not in valid_targets:
        raise ValueError(
            f"Invalid pipeline transition: {state.current_stage} -> {to_stage}. "
            f"Valid transitions: {[s.value for s in valid_targets]}"
        )

    previous = state.current_stage
    state.previous_stage = previous
    state.current_stage = to_stage
    state.error_message = error_message
    state.updated_at = datetime.now(timezone.utc)

    # Create log entry
    log = PipelineLog(
        pipeline_state_id=state.id,
        from_stage=previous,
        to_stage=to_stage,
        trigger_type=trigger_type,
        message=message or error_message,
    )
    db.add(log)

    await db.flush()
    await db.refresh(state)
    return state


async def get_pipeline_logs(
    db: AsyncSession,
    pipeline_state_id: int,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[PipelineLog], int]:
    """Get pipeline transition logs."""
    query = (
        select(PipelineLog)
        .where(PipelineLog.pipeline_state_id == pipeline_state_id)
        .order_by(PipelineLog.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    count_query = (
        select(func.count())
        .select_from(PipelineLog)
        .where(PipelineLog.pipeline_state_id == pipeline_state_id)
    )

    result = await db.execute(query)
    logs = list(result.scalars().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    return logs, total


async def get_pipeline_overview(
    db: AsyncSession,
) -> list[tuple[str, int]]:
    """Get count of pipeline states by stage."""
    result = await db.execute(
        select(PipelineState.current_stage, func.count())
        .group_by(PipelineState.current_stage)
        .order_by(PipelineState.current_stage)
    )
    return list(result.all())

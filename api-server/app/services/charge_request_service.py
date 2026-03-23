"""ChargeRequest service: create, list, approve, reject charge/refund requests."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.charge_request import ChargeRequest, ChargeRequestStatus
from app.schemas.charge_request import ChargeRequestCreate


async def create_charge_request(
    db: AsyncSession,
    user_id: uuid.UUID,
    body: ChargeRequestCreate,
) -> ChargeRequest:
    """Create a new pending charge/refund request."""
    req = ChargeRequest(
        user_id=user_id,
        request_type=body.request_type,
        amount=body.amount,
        reason=body.reason,
        status=ChargeRequestStatus.PENDING.value,
    )
    db.add(req)
    await db.flush()
    await db.refresh(req)
    return req


async def list_charge_requests(
    db: AsyncSession,
    user_id: uuid.UUID | None = None,
    status: str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[ChargeRequest], int]:
    """List charge requests with optional filters."""
    query = select(ChargeRequest).order_by(ChargeRequest.created_at.desc())
    count_query = select(func.count()).select_from(ChargeRequest)

    if user_id is not None:
        query = query.where(ChargeRequest.user_id == user_id)
        count_query = count_query.where(ChargeRequest.user_id == user_id)
    if status is not None:
        query = query.where(ChargeRequest.status == status)
        count_query = count_query.where(ChargeRequest.status == status)

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    items = list(result.scalars().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    return items, total


async def get_charge_request_by_id(
    db: AsyncSession,
    request_id: int,
) -> ChargeRequest | None:
    """Get a single charge request by ID."""
    result = await db.execute(
        select(ChargeRequest).where(ChargeRequest.id == request_id)
    )
    return result.scalar_one_or_none()


async def approve_charge_request(
    db: AsyncSession,
    req: ChargeRequest,
    approver_id: uuid.UUID,
) -> ChargeRequest:
    """Approve a pending charge request and apply balance deposit."""
    from app.services import balance_service

    if req.status != ChargeRequestStatus.PENDING.value:
        raise ValueError(f"Cannot approve a request with status '{req.status}'")

    req.status = ChargeRequestStatus.APPROVED.value
    req.approved_by = approver_id
    req.approved_at = datetime.now(timezone.utc)
    await db.flush()

    # Apply balance change based on request type
    if req.request_type == "refund":
        await balance_service.withdraw(
            db,
            user_id=req.user_id,
            amount=int(req.amount),
            description=f"환불 승인 (요청 #{req.id})",
            created_by=approver_id,
        )
    else:
        await balance_service.deposit(
            db,
            user_id=req.user_id,
            amount=int(req.amount),
            description=f"충전 승인 (요청 #{req.id})",
            created_by=approver_id,
        )

    await db.refresh(req)
    return req


async def reject_charge_request(
    db: AsyncSession,
    req: ChargeRequest,
    rejected_reason: str | None = None,
) -> ChargeRequest:
    """Reject a pending charge request."""
    if req.status != ChargeRequestStatus.PENDING.value:
        raise ValueError(f"Cannot reject a request with status '{req.status}'")

    req.status = ChargeRequestStatus.REJECTED.value
    req.rejected_reason = rejected_reason
    await db.flush()
    await db.refresh(req)
    return req


async def get_pending_summary(db: AsyncSession) -> dict:
    """Return count and total amount of pending charge requests."""
    result = await db.execute(
        select(func.count(), func.coalesce(func.sum(ChargeRequest.amount), 0)).where(
            ChargeRequest.status == ChargeRequestStatus.PENDING.value
        )
    )
    row = result.one()
    return {"pending_count": row[0], "pending_total": int(row[1])}

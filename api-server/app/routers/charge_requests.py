"""Charge requests router: submit, list, approve, reject balance top-up/refund requests."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import RoleChecker, get_current_active_user
from app.models.user import User, UserRole
from app.schemas.charge_request import (
    ChargeRequestCreate,
    ChargeRequestListResponse,
    ChargeRequestReject,
    ChargeRequestResponse,
    ChargeSummaryResponse,
)
from app.services import charge_request_service

router = APIRouter(prefix="/charge-requests", tags=["charge-requests"])

admin_checker = RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN])


def _to_response(req) -> ChargeRequestResponse:
    """Convert ChargeRequest model to response, injecting user display fields."""
    data = ChargeRequestResponse.model_validate(req)
    if req.user:
        data.user_name = req.user.name
        data.user_login_id = req.user.login_id
    return data


@router.get("/summary", response_model=ChargeSummaryResponse)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Return count and total of pending charge requests (admin only)."""
    summary = await charge_request_service.get_pending_summary(db)
    return ChargeSummaryResponse(**summary)


@router.post("/", response_model=ChargeRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_charge_request(
    body: ChargeRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Submit a new charge or refund request. Any authenticated user."""
    req = await charge_request_service.create_charge_request(db, current_user.id, body)
    await db.commit()
    await db.refresh(req)
    return _to_response(req)


@router.get("/", response_model=ChargeRequestListResponse)
async def list_charge_requests(
    status_filter: str | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List charge requests.

    - system_admin / company_admin: all requests (optionally filtered by status)
    - others: only their own requests
    """
    is_admin = UserRole(current_user.role) in (
        UserRole.SYSTEM_ADMIN,
        UserRole.COMPANY_ADMIN,
    )
    user_id_filter = None if is_admin else current_user.id

    items, total = await charge_request_service.list_charge_requests(
        db,
        user_id=user_id_filter,
        status=status_filter,
        skip=skip,
        limit=limit,
    )
    return ChargeRequestListResponse(
        items=[_to_response(r) for r in items],
        total=total,
    )


@router.post("/{request_id}/approve", response_model=ChargeRequestResponse)
async def approve_charge_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_checker),
):
    """Approve a pending charge request and apply balance. Admin only."""
    req = await charge_request_service.get_charge_request_by_id(db, request_id)
    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Charge request not found")
    try:
        req = await charge_request_service.approve_charge_request(db, req, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await db.commit()
    await db.refresh(req)
    return _to_response(req)


@router.post("/{request_id}/reject", response_model=ChargeRequestResponse)
async def reject_charge_request(
    request_id: int,
    body: ChargeRequestReject,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_checker),
):
    """Reject a pending charge request. Admin only."""
    req = await charge_request_service.get_charge_request_by_id(db, request_id)
    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Charge request not found")
    try:
        req = await charge_request_service.reject_charge_request(db, req, body.reason)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await db.commit()
    await db.refresh(req)
    return _to_response(req)

"""Orders router: full order lifecycle with state transitions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import RoleChecker, get_current_active_user
from app.models.user import User, UserRole
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.order import (
    OrderBriefResponse,
    OrderCreate,
    OrderRejectRequest,
    OrderResponse,
    OrderUpdate,
)
from app.services import order_service

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("/", response_model=PaginatedResponse[OrderBriefResponse])
async def list_orders(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List orders with role-based filtering and pagination.

    - system_admin: sees all orders
    - company_admin, order_handler: sees orders in the same company
    - distributor: sees own + sub_account orders
    - sub_account: sees only own orders
    """
    pagination = PaginationParams(page=page, size=size)
    orders, total = await order_service.get_orders(
        db,
        skip=pagination.offset,
        limit=pagination.size,
        status=status_filter,
        current_user=current_user,
    )
    return PaginatedResponse.create(
        items=[OrderBriefResponse.model_validate(o) for o in orders],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.post(
    "/",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
    body: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a new order in draft status.

    Available to all authenticated users (distributor, sub_account typically).
    Prices are resolved automatically based on the user's price tier.
    """
    try:
        order = await order_service.create_order(db, body, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return order


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a single order by ID with items."""
    order = await order_service.get_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    if not order_service.can_view_order(current_user, order):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this order",
        )

    return order


@router.patch("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: int,
    body: OrderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        RoleChecker(
            [UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ORDER_HANDLER]
        )
    ),
):
    """Update an order (only in draft status)."""
    order = await order_service.get_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    try:
        updated = await order_service.update_order(db, order, notes=body.notes)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return updated


@router.post("/{order_id}/submit", response_model=OrderResponse)
async def submit_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN, UserRole.DISTRIBUTOR])
    ),
):
    """Submit an order: draft -> submitted.

    Typically done by the distributor confirming a sub_account's order.
    """
    order = await order_service.get_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    # Distributors can only submit their own or sub_account orders
    user_role = UserRole(current_user.role)
    if user_role == UserRole.DISTRIBUTOR:
        if not order_service.can_view_order(current_user, order):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to submit this order",
            )

    try:
        submitted = await order_service.submit_order(db, order, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return submitted


@router.post("/{order_id}/confirm-payment", response_model=OrderResponse)
async def confirm_payment(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN])
    ),
):
    """Confirm payment: submitted -> payment_confirmed.

    Deducts balance from the order's user. company_admin or system_admin only.
    """
    order = await order_service.get_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    # company_admin can only confirm orders in their company
    user_role = UserRole(current_user.role)
    if user_role == UserRole.COMPANY_ADMIN:
        if order.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Company admin can only confirm orders in their own company",
            )

    try:
        confirmed = await order_service.confirm_payment(db, order, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return confirmed


@router.post("/{order_id}/reject", response_model=OrderResponse)
async def reject_order(
    order_id: int,
    body: OrderRejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN])
    ),
):
    """Reject an order: submitted -> rejected. company_admin or system_admin only."""
    order = await order_service.get_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    # company_admin can only reject orders in their company
    user_role = UserRole(current_user.role)
    if user_role == UserRole.COMPANY_ADMIN:
        if order.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Company admin can only reject orders in their own company",
            )

    try:
        rejected = await order_service.reject_order(db, order, body.reason)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return rejected


@router.post("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN])
    ),
):
    """Cancel an order: draft/submitted -> cancelled. company_admin or system_admin only."""
    order = await order_service.get_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    try:
        cancelled = await order_service.cancel_order(db, order, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return cancelled

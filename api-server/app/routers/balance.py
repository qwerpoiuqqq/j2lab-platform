"""Balance router: balance inquiry, deposit, withdrawal, transaction history."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import RoleChecker, get_current_active_user
from app.models.user import User, UserRole
from app.schemas.balance import (
    BalanceResponse,
    EffectiveBalanceResponse,
    BalanceTransactionResponse,
    DepositRequest,
    WithdrawRequest,
)
from app.schemas.common import PaginatedResponse, PaginationParams
from app.services import balance_service, user_service

router = APIRouter(prefix="/balance", tags=["balance"])


def _can_view_balance(viewer: User, target_user_id: uuid.UUID) -> bool:
    """Check if viewer can see target user's balance.

    - system_admin: anyone
    - company_admin: users in same company
    - Others: only self
    """
    viewer_role = UserRole(viewer.role)
    if viewer_role == UserRole.SYSTEM_ADMIN:
        return True
    if viewer.id == target_user_id:
        return True
    # company_admin: will check company match in the endpoint
    if viewer_role == UserRole.COMPANY_ADMIN:
        return True  # Further validated in endpoint
    return False


@router.get("/effective/me", response_model=EffectiveBalanceResponse)
async def get_effective_balance_me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get the effective balance owner and balance for the current user."""
    owner = await balance_service.get_effective_balance_owner(db, current_user.id)
    balance = int(owner.balance) if owner.balance else 0
    return EffectiveBalanceResponse(
        requested_user_id=current_user.id,
        effective_user_id=owner.id,
        effective_user_name=owner.name,
        effective_user_role=owner.role,
        balance=balance,
    )


@router.get("/{user_id}", response_model=BalanceResponse)
async def get_balance(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a user's current balance.

    - system_admin: any user
    - company_admin: users in same company
    - Others: only self
    """
    if not _can_view_balance(current_user, user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this user's balance",
        )

    # company_admin: check same company
    if UserRole(current_user.role) == UserRole.COMPANY_ADMIN and current_user.id != user_id:
        target = await user_service.get_user_by_id(db, user_id)
        if target is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        if target.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Company admin can only view balance for users in their own company",
            )

    balance = await balance_service.get_balance(db, user_id)
    return BalanceResponse(user_id=user_id, balance=balance)


@router.get(
    "/{user_id}/transactions",
    response_model=PaginatedResponse[BalanceTransactionResponse],
)
async def list_transactions(
    user_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get balance transaction history for a user.

    - system_admin: any user
    - company_admin: users in same company
    - Others: only self
    """
    if not _can_view_balance(current_user, user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this user's transactions",
        )

    # company_admin: check same company
    if UserRole(current_user.role) == UserRole.COMPANY_ADMIN and current_user.id != user_id:
        target = await user_service.get_user_by_id(db, user_id)
        if target is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        if target.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Company admin can only view transactions for users in their own company",
            )

    pagination = PaginationParams(page=page, size=size)
    transactions, total = await balance_service.get_transactions(
        db, user_id, skip=pagination.offset, limit=pagination.size
    )
    return PaginatedResponse.create(
        items=[BalanceTransactionResponse.model_validate(t) for t in transactions],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.post("/deposit", response_model=BalanceTransactionResponse)
async def deposit(
    body: DepositRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN])
    ),
):
    """Deposit (charge) balance for a user. company_admin or system_admin only."""
    # Validate target user exists
    target = await user_service.get_user_by_id(db, body.user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target user not found",
        )

    # company_admin: must be same company
    if UserRole(current_user.role) == UserRole.COMPANY_ADMIN:
        if target.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Company admin can only deposit to users in their own company",
            )

    try:
        tx = await balance_service.deposit(
            db,
            user_id=body.user_id,
            amount=body.amount,
            description=body.description,
            created_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return tx


@router.post("/withdraw", response_model=BalanceTransactionResponse)
async def withdraw(
    body: WithdrawRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN])
    ),
):
    """Withdraw (deduct) balance from a user. company_admin or system_admin only."""
    # Validate target user exists
    target = await user_service.get_user_by_id(db, body.user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target user not found",
        )

    # company_admin: must be same company
    if UserRole(current_user.role) == UserRole.COMPANY_ADMIN:
        if target.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Company admin can only withdraw from users in their own company",
            )

    try:
        tx = await balance_service.withdraw(
            db,
            user_id=body.user_id,
            amount=body.amount,
            description=body.description,
            created_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return tx

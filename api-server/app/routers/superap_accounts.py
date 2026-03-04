"""Superap accounts router: CRUD with AES encryption."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import RoleChecker
from app.models.user import User, UserRole
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.superap_account import (
    SuperapAccountCreate,
    SuperapAccountResponse,
    SuperapAccountUpdate,
)
from app.services import superap_account_service

router = APIRouter(prefix="/superap-accounts", tags=["superap-accounts"])

admin_viewer = RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN])
admin_editor = RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN])
system_admin_checker = RoleChecker([UserRole.SYSTEM_ADMIN])


@router.get("/", response_model=PaginatedResponse[SuperapAccountResponse])
async def list_accounts(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=100),
    company_id: int | None = None,
    network_preset_id: int | None = None,
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_viewer),
):
    """List superap accounts (company_admin sees own company only)."""
    pagination = PaginationParams(page=page, size=size)

    # Scope to company for company_admin
    effective_company_id = company_id
    if UserRole(current_user.role) == UserRole.COMPANY_ADMIN:
        effective_company_id = current_user.company_id

    accounts, total = await superap_account_service.get_accounts(
        db,
        company_id=effective_company_id,
        network_preset_id=network_preset_id,
        is_active=is_active,
        skip=pagination.offset,
        limit=pagination.size,
    )
    return PaginatedResponse.create(
        items=[SuperapAccountResponse.model_validate(a) for a in accounts],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.post(
    "/",
    response_model=SuperapAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_account(
    body: SuperapAccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_editor),
):
    """Create a new superap account. Password is AES-encrypted.

    company_admin can only create accounts for their own company.
    """
    # company_admin: force company_id to own company
    if UserRole(current_user.role) == UserRole.COMPANY_ADMIN:
        body.company_id = current_user.company_id

    # Check uniqueness
    existing = await superap_account_service.get_account_by_login_id(
        db, body.user_id_superap
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Account with login ID '{body.user_id_superap}' already exists",
        )

    account = await superap_account_service.create_account(db, body)
    return account


@router.patch("/{account_id}", response_model=SuperapAccountResponse)
async def update_account(
    account_id: int,
    body: SuperapAccountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_editor),
):
    """Update a superap account.

    company_admin can only update accounts in their own company.
    """
    account = await superap_account_service.get_account_by_id(db, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Superap account not found",
        )
    # company_admin: scope check
    if UserRole(current_user.role) == UserRole.COMPANY_ADMIN:
        if account.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot update accounts outside your company",
            )
    updated = await superap_account_service.update_account(db, account, body)
    return updated


@router.delete(
    "/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(system_admin_checker),
):
    """Delete a superap account (system_admin only)."""
    account = await superap_account_service.get_account_by_id(db, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Superap account not found",
        )
    try:
        await superap_account_service.delete_account(db, account)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get("/agencies")
async def list_agencies(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_viewer),
):
    """Get distinct agency names from superap accounts."""
    from sqlalchemy import select, distinct
    from app.models.superap_account import SuperapAccount

    result = await db.execute(
        select(distinct(SuperapAccount.agency_name))
        .where(SuperapAccount.agency_name.isnot(None))
        .order_by(SuperapAccount.agency_name)
    )
    agencies = [row[0] for row in result.all() if row[0]]
    return {"agencies": agencies}

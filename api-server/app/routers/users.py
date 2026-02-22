"""Users router: CRUD for user management with role-based access control."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    RoleChecker,
    can_create_role,
    get_current_active_user,
)
from app.models.user import User, UserRole
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.user import UserCreate, UserResponse, UserTreeNode, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_active_user),
):
    """Get current user's own profile."""
    return current_user


@router.get("/", response_model=PaginatedResponse[UserResponse])
async def list_users(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    company_id: int | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        RoleChecker(
            [
                UserRole.SYSTEM_ADMIN,
                UserRole.COMPANY_ADMIN,
                UserRole.ORDER_HANDLER,
                UserRole.DISTRIBUTOR,
                UserRole.SUB_ACCOUNT,
            ]
        )
    ),
):
    """List users with role-based filtering and pagination.

    - system_admin: sees all users
    - company_admin/order_handler: sees users in the same company
    - distributor: sees their sub_accounts
    - sub_account: sees only themselves
    """
    pagination = PaginationParams(page=page, size=size)
    users, total = await user_service.get_users(
        db,
        skip=pagination.offset,
        limit=pagination.size,
        company_id=company_id,
        role=role,
        is_active=is_active,
        current_user=current_user,
    )
    return PaginatedResponse.create(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        RoleChecker(
            [UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN, UserRole.DISTRIBUTOR]
        )
    ),
):
    """Create a new user with role hierarchy enforcement.

    Role creation rules:
    - system_admin: can create any role
    - company_admin: can create order_handler, distributor, sub_account (same company)
    - distributor: can only create sub_account (as parent)
    """
    creator_role = UserRole(current_user.role)
    target_role = body.role

    # Check if creator can create this role
    if not can_create_role(creator_role, target_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{current_user.role}' cannot create users with role '{target_role.value}'",
        )

    # company_admin must create users in their own company
    if creator_role == UserRole.COMPANY_ADMIN:
        if body.company_id is not None and body.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Company admin can only create users in their own company",
            )
        body = body.model_copy(update={"company_id": current_user.company_id})

    # distributor must set themselves as parent
    if creator_role == UserRole.DISTRIBUTOR:
        body = body.model_copy(
            update={
                "parent_id": current_user.id,
                "company_id": current_user.company_id,
            }
        )

    # Non-system_admin roles must have a company_id
    if target_role != UserRole.SYSTEM_ADMIN and body.company_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="company_id is required for non-system_admin users",
        )

    # system_admin should NOT have company_id
    if target_role == UserRole.SYSTEM_ADMIN and body.company_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="system_admin should not have company_id",
        )

    # Check for duplicate email
    existing = await user_service.get_user_by_email(db, body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = await user_service.create_user(db, body)
    return user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a single user by ID. Access depends on role and relationship."""
    user = await user_service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not user_service.can_view_user(current_user, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this user",
        )

    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN])
    ),
):
    """Update a user. system_admin and company_admin can update users."""
    user = await user_service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # company_admin can only update users in their own company
    current_role = UserRole(current_user.role)
    if current_role == UserRole.COMPANY_ADMIN:
        if user.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Company admin can only update users in their own company",
            )

    # Check email uniqueness if updating email
    if body.email is not None and body.email != user.email:
        existing = await user_service.get_user_by_email(db, body.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

    updated = await user_service.update_user(db, user, body)
    return updated


@router.delete("/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(RoleChecker([UserRole.SYSTEM_ADMIN])),
):
    """Soft-delete a user (set is_active=False). system_admin only."""
    user = await user_service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await user_service.delete_user(db, user)
    return MessageResponse(message=f"User '{user.email}' has been deactivated")


@router.get("/{user_id}/descendants", response_model=UserTreeNode)
async def get_user_descendants(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        RoleChecker(
            [UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN, UserRole.DISTRIBUTOR]
        )
    ),
):
    """Get hierarchical tree of user's descendants.

    - system_admin: any user's tree
    - company_admin: users in their company
    - distributor: their own tree only
    """
    user = await user_service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    current_role = UserRole(current_user.role)

    # company_admin can only view trees in their own company
    if current_role == UserRole.COMPANY_ADMIN:
        if user.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Company admin can only view trees in their own company",
            )

    # distributor can only view their own tree
    if current_role == UserRole.DISTRIBUTOR:
        if user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Distributor can only view their own descendant tree",
            )

    tree = await user_service.build_user_tree(db, user)
    return tree

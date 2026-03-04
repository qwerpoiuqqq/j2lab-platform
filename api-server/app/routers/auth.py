"""Auth router: login, refresh, logout, register."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import RoleChecker, can_create_role, get_current_active_user
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, TokenResponse
from app.schemas.common import MessageResponse
from app.schemas.user import UserCreate, UserResponse
from app.services import auth_service, company_service, user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with email + password and receive JWT tokens."""
    user = await auth_service.authenticate_user(db, body.email, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    tokens = await auth_service.create_tokens(db, user)
    return tokens


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """Refresh the access token using a valid refresh token."""
    tokens = await auth_service.refresh_tokens(db, body.refresh_token)
    if tokens is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    return tokens


@router.post("/logout", response_model=MessageResponse)
async def logout(
    body: LogoutRequest,
    db: AsyncSession = Depends(get_db),
):
    """Invalidate a refresh token (logout)."""
    revoked = await auth_service.revoke_refresh_token(db, body.refresh_token)
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid refresh token",
        )
    return MessageResponse(message="Successfully logged out")


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


@router.post("/change-password")
async def change_password(
    request: PasswordChangeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Change the current user's password."""
    success = await auth_service.change_password(
        db, current_user, request.current_password, request.new_password
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="현재 비밀번호가 올바르지 않습니다.",
        )
    return {"message": "비밀번호가 변경되었습니다."}


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN, UserRole.DISTRIBUTOR])
    ),
):
    """Register a new user. Only authorized roles can create users.

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

    # Validate company_id exists if provided
    if body.company_id is not None:
        company = await company_service.get_company_by_id(db, body.company_id)
        if company is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Company with id {body.company_id} not found",
            )

    # Check for duplicate email
    existing = await user_service.get_user_by_email(db, body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = await auth_service.register_user(
        db=db,
        email=body.email,
        password=body.password,
        name=body.name,
        phone=body.phone,
        company_id=body.company_id,
        role=body.role,
        parent_id=body.parent_id,
    )
    return user

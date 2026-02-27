"""FastAPI dependencies for authentication and authorization."""

from __future__ import annotations

import uuid

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import ROLE_HIERARCHY, User, UserRole

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate the current user from the JWT access token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise credentials_exception

    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure the current user is active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user


class RoleChecker:
    """Dependency class for role-based access control.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(RoleChecker([UserRole.SYSTEM_ADMIN]))])
        async def admin_endpoint(): ...

    Or as a direct dependency that returns the user:
        async def endpoint(user: User = Depends(RoleChecker([UserRole.SYSTEM_ADMIN]))):
    """

    def __init__(self, allowed_roles: list[UserRole]) -> None:
        self.allowed_roles = allowed_roles

    async def __call__(
        self,
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        user_role = UserRole(current_user.role)
        if user_role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not authorized. "
                f"Required: {[r.value for r in self.allowed_roles]}",
            )
        return current_user


def require_roles(*roles: UserRole):
    """Shorthand for creating a RoleChecker dependency.

    Usage:
        @router.get("/", dependencies=[Depends(require_roles(UserRole.SYSTEM_ADMIN))])
    """
    return RoleChecker(list(roles))


async def verify_internal_secret(
    x_internal_secret: str = Header(..., alias="X-Internal-Secret"),
) -> None:
    """Verify the internal API secret header for worker callbacks."""
    from app.core.config import settings

    if x_internal_secret != settings.INTERNAL_API_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal secret",
        )


def can_create_role(creator_role: UserRole, target_role: UserRole) -> bool:
    """Check if a creator role can create users with the target role.

    Rules:
    - system_admin can create any role
    - company_admin can create order_handler, distributor, sub_account
    - distributor can only create sub_account
    - Others cannot create users
    """
    if creator_role == UserRole.SYSTEM_ADMIN:
        return True
    if creator_role == UserRole.COMPANY_ADMIN:
        return target_role in (
            UserRole.ORDER_HANDLER,
            UserRole.DISTRIBUTOR,
            UserRole.SUB_ACCOUNT,
        )
    if creator_role == UserRole.DISTRIBUTOR:
        return target_role == UserRole.SUB_ACCOUNT
    return False

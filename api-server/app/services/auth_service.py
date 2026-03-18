"""Authentication service: login, refresh, logout, register."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> User | None:
    """Verify email/password and return user if valid."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None

    return user


async def create_tokens(
    db: AsyncSession,
    user: User,
) -> dict[str, str]:
    """Create access + refresh token pair and store refresh token hash in DB."""
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role}
    )
    refresh_token_raw = create_refresh_token()
    token_hash = hash_token(refresh_token_raw)

    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    db_refresh_token = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(db_refresh_token)
    await db.flush()

    # Cleanup expired/revoked tokens for this user
    await db.execute(
        delete(RefreshToken).where(
            RefreshToken.user_id == user.id,
            RefreshToken.id != db_refresh_token.id,
            or_(
                RefreshToken.expires_at < datetime.now(timezone.utc),
                RefreshToken.revoked_at.isnot(None),
            ),
        ).execution_options(synchronize_session=False)
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token_raw,
        "token_type": "bearer",
    }


async def refresh_tokens(
    db: AsyncSession,
    refresh_token_raw: str,
) -> dict[str, str] | None:
    """Validate refresh token, revoke it, and issue new token pair."""
    token_hash = hash_token(refresh_token_raw)

    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
        )
    )
    db_token = result.scalar_one_or_none()

    if db_token is None:
        return None

    # Compare expiry - handle both tz-aware and naive datetimes (SQLite vs PostgreSQL)
    now = datetime.now(timezone.utc)
    expires_at = db_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        # Token expired, revoke it
        db_token.revoked_at = now
        await db.flush()
        return None

    # Revoke old token
    db_token.revoked_at = now
    await db.flush()

    # Load user
    user_result = await db.execute(
        select(User).where(User.id == db_token.user_id)
    )
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        return None

    # Issue new pair
    return await create_tokens(db, user)


async def revoke_refresh_token(
    db: AsyncSession,
    refresh_token_raw: str,
) -> bool:
    """Revoke (invalidate) a refresh token. Returns True if found and revoked."""
    token_hash = hash_token(refresh_token_raw)

    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
        )
    )
    db_token = result.scalar_one_or_none()

    if db_token is None:
        return False

    db_token.revoked_at = datetime.now(timezone.utc)
    await db.flush()
    return True


async def register_user(
    db: AsyncSession,
    email: str,
    password: str,
    name: str,
    phone: str | None = None,
    company_id: int | None = None,
    role: UserRole = UserRole.SUB_ACCOUNT,
    parent_id=None,
) -> User:
    """Create a new user with hashed password."""
    hashed_pw = hash_password(password)

    user = User(
        email=email,
        hashed_password=hashed_pw,
        name=name,
        phone=phone,
        company_id=company_id,
        role=role.value,
        parent_id=parent_id,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def change_password(
    db: AsyncSession,
    user: User,
    current_password: str,
    new_password: str,
) -> bool:
    """Change user's own password after verifying current password."""
    if not verify_password(current_password, user.hashed_password):
        return False
    user.hashed_password = hash_password(new_password)
    await db.flush()
    return True


async def cleanup_expired_tokens(db: AsyncSession) -> int:
    """Delete expired and revoked refresh tokens. Returns count deleted."""
    result = await db.execute(
        delete(RefreshToken).where(
            or_(
                RefreshToken.expires_at < datetime.now(timezone.utc),
                RefreshToken.revoked_at.isnot(None),
            )
        ).execution_options(synchronize_session=False)
    )
    await db.flush()
    return result.rowcount

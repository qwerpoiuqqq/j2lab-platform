"""User model - Table 1: users (5-level role hierarchy)."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.refresh_token import RefreshToken


class UserRole(str, Enum):
    """5-level role hierarchy: system_admin > company_admin > order_handler > distributor > sub_account."""

    SYSTEM_ADMIN = "system_admin"
    COMPANY_ADMIN = "company_admin"
    ORDER_HANDLER = "order_handler"
    DISTRIBUTOR = "distributor"
    SUB_ACCOUNT = "sub_account"


# Role hierarchy mapping: higher index = lower privilege
ROLE_HIERARCHY: Dict[UserRole, int] = {
    UserRole.SYSTEM_ADMIN: 0,
    UserRole.COMPANY_ADMIN: 1,
    UserRole.ORDER_HANDLER: 2,
    UserRole.DISTRIBUTOR: 3,
    UserRole.SUB_ACCOUNT: 4,
}


def has_role_or_higher(user_role: UserRole, required_role: UserRole) -> bool:
    """Check if user_role is equal to or higher than required_role in the hierarchy."""
    return ROLE_HIERARCHY[user_role] <= ROLE_HIERARCHY[required_role]


class User(Base):
    """User entity with hierarchical roles and company membership."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20))

    company_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("companies.id", ondelete="SET NULL"),
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=UserRole.SUB_ACCOUNT.value,
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    balance: Mapped[int] = mapped_column(
        Numeric(12, 0),
        default=0,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
    )

    # Relationships
    company: Mapped[Optional["Company"]] = relationship(
        "Company",
        back_populates="users",
        lazy="selectin",
    )
    parent: Mapped[Optional["User"]] = relationship(
        "User",
        remote_side="User.id",
        lazy="selectin",
        foreign_keys=[parent_id],
    )
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        lazy="noload",
    )

    __table_args__ = (
        Index("idx_users_role", "role"),
        Index("idx_users_company_id", "company_id"),
        Index("idx_users_parent_id", "parent_id"),
        Index("idx_users_is_active", "is_active"),
    )

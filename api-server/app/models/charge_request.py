"""ChargeRequest model - user balance top-up / refund requests pending admin approval."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class ChargeRequestType(str, Enum):
    CHARGE = "charge"
    REFUND = "refund"


class ChargeRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ChargeRequest(Base):
    """User-submitted request to charge or refund balance, pending admin approval."""

    __tablename__ = "charge_requests"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    request_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ChargeRequestType.CHARGE.value,
    )
    amount: Mapped[int] = mapped_column(Numeric(12, 0), nullable=False)
    # payment_amount / vat_amount: optional breakdown supplied by requester
    payment_amount: Mapped[Optional[int]] = mapped_column(Numeric(12, 0))
    vat_amount: Mapped[Optional[int]] = mapped_column(Numeric(12, 0))
    reason: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ChargeRequestStatus.PENDING.value,
    )
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
    )
    rejected_reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        lazy="selectin",
    )
    approver: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[approved_by],
        lazy="selectin",
    )

    __table_args__ = (
        Index("idx_charge_requests_user_id", "user_id"),
        Index("idx_charge_requests_status", "status"),
        Index("idx_charge_requests_created_at", "created_at"),
    )

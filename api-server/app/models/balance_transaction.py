"""BalanceTransaction model - Table 14: balance_transactions (ledger)."""

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


class TransactionType(str, Enum):
    """Balance transaction types."""

    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    ORDER_CHARGE = "order_charge"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"


class BalanceTransaction(Base):
    """Balance transaction ledger entry. Source of truth for user balances."""

    __tablename__ = "balance_transactions"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id"),
        nullable=False,
    )
    order_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("orders.id", ondelete="SET NULL"),
    )
    amount: Mapped[int] = mapped_column(
        Numeric(12, 0),
        nullable=False,
    )
    balance_after: Mapped[int] = mapped_column(
        Numeric(12, 0),
        nullable=False,
    )
    transaction_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id"),
    )
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

    __table_args__ = (
        Index("idx_balance_tx_user_id", "user_id"),
        Index("idx_balance_tx_order_id", "order_id"),
        Index("idx_balance_tx_created_at", "created_at"),
    )

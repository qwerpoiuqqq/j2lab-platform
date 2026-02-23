"""PricePolicy model - Table 3: price_policies (tiered pricing)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    Date,
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
    from app.models.product import Product
    from app.models.user import User


class PricePolicy(Base):
    """Price policy for per-user or per-role pricing overrides."""

    __tablename__ = "price_policies"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    role: Mapped[Optional[str]] = mapped_column(String(20))
    unit_price: Mapped[int] = mapped_column(Numeric(12, 0), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="price_policies",
        lazy="noload",
    )
    user: Mapped[Optional["User"]] = relationship(
        "User",
        lazy="noload",
    )

    __table_args__ = (
        Index("idx_price_policies_product_id", "product_id"),
        Index("idx_price_policies_user_id", "user_id"),
    )

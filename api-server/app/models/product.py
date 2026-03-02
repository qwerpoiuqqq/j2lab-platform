"""Product model - Table 2: products (services/offerings)."""

from __future__ import annotations

from datetime import datetime, time
from typing import TYPE_CHECKING, Any, List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.order import OrderItem
    from app.models.price_policy import PricePolicy


class Product(Base):
    """Product / service entity (e.g. traffic campaign, save campaign)."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    form_schema: Mapped[Optional[Any]] = mapped_column(JSON)
    base_price: Mapped[Optional[int]] = mapped_column(Numeric(12, 0))
    cost_price: Mapped[Optional[int]] = mapped_column(Numeric(12, 0))
    reduction_rate: Mapped[Optional[int]] = mapped_column(Integer)  # 0-100%
    min_work_days: Mapped[Optional[int]] = mapped_column(Integer)
    max_work_days: Mapped[Optional[int]] = mapped_column(Integer)
    daily_deadline: Mapped[time] = mapped_column(
        Time,
        nullable=False,
        default=time(18, 0),
    )
    deadline_timezone: Mapped[str] = mapped_column(
        String(30),
        default="Asia/Seoul",
    )
    setup_delay_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
        server_default="30",
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
    price_policies: Mapped[List["PricePolicy"]] = relationship(
        "PricePolicy",
        back_populates="product",
        lazy="noload",
    )
    order_items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="product",
        lazy="noload",
    )

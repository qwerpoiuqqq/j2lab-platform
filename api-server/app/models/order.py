"""Order and OrderItem models - Tables 4 & 5: orders, order_items."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, List, Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.user import User


class OrderStatus(str, Enum):
    """Order status state machine."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    PAYMENT_CONFIRMED = "payment_confirmed"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class PaymentStatus(str, Enum):
    """Payment tracking status."""

    UNPAID = "unpaid"
    CONFIRMED = "confirmed"
    SETTLED = "settled"


class OrderItemStatus(str, Enum):
    """Order item processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AssignmentStatus(str, Enum):
    """Superap account assignment status."""

    PENDING = "pending"
    AUTO_ASSIGNED = "auto_assigned"
    CONFIRMED = "confirmed"
    OVERRIDDEN = "overridden"


# Valid order status transitions
VALID_ORDER_TRANSITIONS = {
    OrderStatus.DRAFT: [OrderStatus.SUBMITTED, OrderStatus.CANCELLED],
    OrderStatus.SUBMITTED: [
        OrderStatus.PAYMENT_CONFIRMED,
        OrderStatus.REJECTED,
        OrderStatus.CANCELLED,
    ],
    OrderStatus.PAYMENT_CONFIRMED: [OrderStatus.PROCESSING],
    OrderStatus.PROCESSING: [OrderStatus.COMPLETED],
    OrderStatus.COMPLETED: [],
    OrderStatus.CANCELLED: [],
    OrderStatus.REJECTED: [],
}


class Order(Base):
    """Order entity representing a customer order with status tracking."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    order_number: Mapped[str] = mapped_column(
        String(30), unique=True, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id"),
        nullable=False,
    )
    company_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("companies.id"),
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=OrderStatus.DRAFT.value,
    )
    payment_status: Mapped[str] = mapped_column(
        String(20),
        default=PaymentStatus.UNPAID.value,
    )
    total_amount: Mapped[int] = mapped_column(
        Numeric(12, 0),
        default=0,
    )
    vat_amount: Mapped[int] = mapped_column(
        Numeric(12, 0),
        default=0,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)
    source: Mapped[str] = mapped_column(
        String(20),
        default="web",
    )
    submitted_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id"),
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
    )
    payment_confirmed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id"),
    )
    payment_confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        lazy="selectin",
    )
    items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="order",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_orders_user_id", "user_id"),
        Index("idx_orders_status", "status"),
        Index("idx_orders_created_at", "created_at"),
    )


class OrderItem(Base):
    """Individual line item within an order."""

    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id"),
        nullable=False,
    )
    row_number: Mapped[Optional[int]] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[int] = mapped_column(Numeric(12, 0), nullable=False)
    subtotal: Mapped[int] = mapped_column(Numeric(12, 0), nullable=False)
    item_data: Mapped[Optional[Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=OrderItemStatus.PENDING.value,
    )
    result_message: Mapped[Optional[str]] = mapped_column(Text)

    # Assignment fields (Phase 1C will connect to superap_accounts)
    assigned_account_id: Mapped[Optional[int]] = mapped_column(Integer)
    assignment_status: Mapped[str] = mapped_column(
        String(20),
        default=AssignmentStatus.PENDING.value,
    )
    assigned_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
    )
    assigned_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id"),
    )

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
    order: Mapped["Order"] = relationship(
        "Order",
        back_populates="items",
        lazy="selectin",
    )
    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="order_items",
        lazy="selectin",
    )

    __table_args__ = (
        Index("idx_order_items_order_id", "order_id"),
        Index("idx_order_items_status", "status"),
    )

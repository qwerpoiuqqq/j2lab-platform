"""Order and OrderItem models - maps to orders/order_items tables.

This model mirrors the tables created by api-server's migrations.
campaign-worker uses these for the campaign expiry auto-complete job.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class Order(Base):
    """Order entity (read/update by campaign-worker)."""

    __tablename__ = "orders"

    id = Column(BigInteger, primary_key=True)
    order_number = Column(String(30), unique=True, nullable=False)
    status = Column(String(20), nullable=False, default="draft")
    completed_at = Column(DateTime(timezone=True))

    # Relationships
    items = relationship("OrderItem", back_populates="order")

    def __repr__(self) -> str:
        return f"<Order(id={self.id}, status='{self.status}')>"


class OrderItem(Base):
    """Individual line item within an order."""

    __tablename__ = "order_items"

    id = Column(BigInteger, primary_key=True)
    order_id = Column(BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), nullable=False, default="pending")

    # Relationships
    order = relationship("Order", back_populates="items")

    def __repr__(self) -> str:
        return f"<OrderItem(id={self.id}, status='{self.status}')>"

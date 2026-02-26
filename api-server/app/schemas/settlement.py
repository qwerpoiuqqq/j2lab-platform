"""Settlement schemas: response models for settlement analysis."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class SettlementRow(BaseModel):
    """Single settlement row (per order item)."""

    order_id: int
    order_number: str
    product_name: str
    user_name: str
    user_role: str
    quantity: int
    unit_price: int
    base_price: int
    subtotal: int
    cost: int
    profit: int
    margin_pct: float
    created_at: datetime

    @field_validator("unit_price", "base_price", "subtotal", "cost", "profit", mode="before")
    @classmethod
    def coerce_numeric(cls, v):
        if isinstance(v, Decimal):
            return int(v)
        return v


class SettlementSummary(BaseModel):
    """Aggregated settlement summary."""

    total_revenue: int
    total_cost: int
    total_profit: int
    avg_margin_pct: float
    order_count: int
    item_count: int

    @field_validator("total_revenue", "total_cost", "total_profit", mode="before")
    @classmethod
    def coerce_numeric(cls, v):
        if isinstance(v, Decimal):
            return int(v)
        return v


class SettlementResponse(BaseModel):
    """Settlement list response with summary."""

    items: list[SettlementRow]
    summary: SettlementSummary
    total: int
    page: int
    size: int
    pages: int


class SettlementSecretRequest(BaseModel):
    """Password-protected detailed settlement request."""

    password: str = Field(..., min_length=1)
    date_from: date | None = None
    date_to: date | None = None


class SettlementSecretResponse(BaseModel):
    """Detailed settlement analysis (13-column secret view)."""

    items: list[SettlementRow]
    summary: SettlementSummary


class SettlementExportParams(BaseModel):
    """Parameters for settlement Excel export."""

    date_from: date | None = None
    date_to: date | None = None

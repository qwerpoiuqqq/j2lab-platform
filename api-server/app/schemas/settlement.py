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
    display_order_number: str
    primary_place_name: str
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


# ---- PHASE 6: Aggregation views ----


class SettlementByHandlerRow(BaseModel):
    """Settlement aggregated by handler (user)."""

    handler_id: str
    handler_name: str
    handler_role: str
    order_count: int
    item_count: int
    total_revenue: int
    total_cost: int
    total_profit: int
    avg_margin_pct: float


class SettlementByCompanyRow(BaseModel):
    """Settlement aggregated by company."""

    company_id: int | None
    company_name: str
    order_count: int
    item_count: int
    total_revenue: int
    total_cost: int
    total_profit: int
    avg_margin_pct: float


class SettlementByDateRow(BaseModel):
    """Settlement aggregated by date (for charts)."""

    date: str
    order_count: int
    item_count: int
    total_revenue: int
    total_cost: int
    total_profit: int


# ---- Daily settlement check (정산 체크) ----


class OrderBrief(BaseModel):
    """Brief order info for daily settlement check."""

    id: int
    place_name: str
    total_quantity: int
    total_amount: int
    status: str
    created_at: datetime

    @field_validator("total_amount", "total_quantity", mode="before")
    @classmethod
    def coerce_numeric(cls, v):
        if isinstance(v, Decimal):
            return int(v)
        return v

    model_config = {"from_attributes": True}


class DailyCheckDistributorRow(BaseModel):
    """Settlement check grouped by distributor."""

    distributor_id: str
    distributor_name: str
    order_count: int
    total_quantity: int
    total_amount: int
    orders: list[OrderBrief]

    @field_validator("total_amount", "total_quantity", mode="before")
    @classmethod
    def coerce_numeric(cls, v):
        if isinstance(v, Decimal):
            return int(v)
        return v


class DailyCheckResponse(BaseModel):
    """Daily settlement check response."""

    date: str
    distributors: list[DailyCheckDistributorRow]
    summary: dict

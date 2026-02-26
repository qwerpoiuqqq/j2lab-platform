"""Order and OrderItem schemas: CRUD request/response models."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.order import OrderStatus


class OrderItemCreate(BaseModel):
    """Schema for creating an order item within an order."""

    product_id: int
    quantity: int = Field(default=1, ge=1)
    item_data: Any = None


class OrderItemResponse(BaseModel):
    """Order item response model."""

    id: int
    order_id: int
    product_id: int
    row_number: int | None = None
    quantity: int
    unit_price: int
    subtotal: int
    item_data: Any = None
    status: str
    result_message: str | None = None
    assigned_account_id: int | None = None
    assignment_status: str
    assigned_at: datetime | None = None
    assigned_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime | None = None

    @field_validator("unit_price", "subtotal", mode="before")
    @classmethod
    def coerce_numeric(cls, v):
        if isinstance(v, Decimal):
            return int(v)
        return v

    model_config = {"from_attributes": True}


class OrderCreate(BaseModel):
    """Schema for creating an order."""

    notes: str | None = None
    source: str = "web"
    items: list[OrderItemCreate] = Field(..., min_length=1)


class OrderUpdate(BaseModel):
    """Schema for updating an order (draft only)."""

    notes: str | None = None


class OrderRejectRequest(BaseModel):
    """Schema for rejecting an order."""

    reason: str = Field(..., min_length=1, max_length=500)


class OrderResponse(BaseModel):
    """Order response model."""

    id: int
    order_number: str
    user_id: uuid.UUID
    company_id: int | None = None
    status: str
    payment_status: str
    total_amount: int
    vat_amount: int
    notes: str | None = None
    source: str
    submitted_by: uuid.UUID | None = None
    submitted_at: datetime | None = None
    payment_confirmed_by: uuid.UUID | None = None
    payment_confirmed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    items: list[OrderItemResponse] = []

    @field_validator("total_amount", "vat_amount", mode="before")
    @classmethod
    def coerce_numeric(cls, v):
        if isinstance(v, Decimal):
            return int(v)
        return v

    model_config = {"from_attributes": True}


class BulkStatusRequest(BaseModel):
    """Schema for bulk status change."""

    order_ids: list[int] = Field(..., min_length=1)
    status: str = Field(..., min_length=1)


class DeadlineUpdateRequest(BaseModel):
    """Schema for updating order deadline."""

    deadline: datetime


class OrderBriefResponse(BaseModel):
    """Brief order info for list responses (without items)."""

    id: int
    order_number: str
    user_id: uuid.UUID
    company_id: int | None = None
    status: str
    payment_status: str
    total_amount: int
    vat_amount: int
    notes: str | None = None
    source: str
    created_at: datetime
    updated_at: datetime | None = None

    @field_validator("total_amount", "vat_amount", mode="before")
    @classmethod
    def coerce_numeric(cls, v):
        if isinstance(v, Decimal):
            return int(v)
        return v

    model_config = {"from_attributes": True}

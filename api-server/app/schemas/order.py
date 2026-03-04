"""Order and OrderItem schemas: CRUD request/response models."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.order import OrderStatus


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _coerce_decimal(v: Any) -> Any:
    """Convert Decimal to int (used by field_validators across multiple schemas)."""
    return int(v) if isinstance(v, Decimal) else v


# ---------------------------------------------------------------------------
# Brief models (must be defined before schemas that reference them)
# ---------------------------------------------------------------------------

class _ProductBrief(BaseModel):
    """Inline product brief for order item responses."""

    id: int
    name: str
    code: str | None = None

    model_config = {"from_attributes": True}


class _UserBrief(BaseModel):
    """Inline user brief for order list."""

    id: uuid.UUID
    name: str
    role: str

    model_config = {"from_attributes": True}


class _CompanyBrief(BaseModel):
    """Inline company brief for order list."""

    id: int
    name: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Create / Update schemas
# ---------------------------------------------------------------------------

class OrderItemCreate(BaseModel):
    """Schema for creating an order item within an order."""

    product_id: int
    quantity: int = Field(default=1, ge=1)
    item_data: Any = None


class OrderCreate(BaseModel):
    """Schema for creating an order."""

    notes: str | None = None
    source: str = "web"
    order_type: Literal["regular", "monthly_guarantee", "managed"] = "regular"
    assigned_account_id: int | None = None
    items: list[OrderItemCreate] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_assigned_account_required(self):
        """managed/monthly_guarantee 주문은 assigned_account_id 필수."""
        if self.order_type in ("managed", "monthly_guarantee"):
            if self.assigned_account_id is None:
                raise ValueError(
                    "관리형/월보장 주문은 배정 계정(assigned_account_id)이 필수입니다."
                )
        return self


class OrderUpdate(BaseModel):
    """Schema for updating an order (draft only)."""

    notes: str | None = None


class OrderRejectRequest(BaseModel):
    """Schema for rejecting an order."""

    reason: str = Field(..., min_length=1, max_length=500)


class OrderHoldRequest(BaseModel):
    """Schema for holding an order (payment_hold)."""

    reason: str = Field(..., min_length=1, max_length=500)


class BulkPaymentConfirmRequest(BaseModel):
    """Schema for bulk payment confirmation."""

    order_ids: list[int] = Field(..., min_length=1)


class BulkHoldRequest(BaseModel):
    """Schema for bulk hold."""

    order_ids: list[int] = Field(..., min_length=1)
    reason: str = Field(..., min_length=1, max_length=500)


class BulkStatusRequest(BaseModel):
    """Schema for bulk status change."""

    order_ids: list[int] = Field(..., min_length=1)
    status: str = Field(..., min_length=1)


class BulkDeleteRequest(BaseModel):
    """Schema for bulk order deletion."""

    order_ids: list[int] = Field(..., min_length=1)


class DeadlineUpdateRequest(BaseModel):
    """Schema for updating order deadline."""

    deadline: datetime


class ExcelUploadPreviewItem(BaseModel):
    row_number: int
    data: dict[str, Any]
    is_valid: bool
    errors: list[str]


class ExcelUploadPreviewResponse(BaseModel):
    items: list[ExcelUploadPreviewItem]
    total: int
    valid_count: int
    error_count: int
    product_id: int
    product_name: str


class ExcelUploadConfirmRequest(BaseModel):
    product_id: int
    row_indices: list[int] = Field(..., min_length=1)
    rows: list[dict[str, Any]]
    notes: str | None = None


class SimplifiedOrderItemCreate(BaseModel):
    """Single item for simplified order."""

    place_url: str
    place_name: str = ""
    start_date: str  # YYYY-MM-DD
    daily_limit: int = Field(..., ge=1)
    duration_days: int = Field(..., ge=1)
    target_keyword: str = ""
    campaign_type: str = "traffic"  # AI recommended, user overridable


class SimplifiedOrderCreate(BaseModel):
    """Simplified order creation: no product/category selection needed."""

    items: list[SimplifiedOrderItemCreate] = Field(..., min_length=1)
    notes: str | None = None
    source: str = "web"


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class OrderItemResponse(BaseModel):
    """Order item response model."""

    id: int
    order_id: int
    product_id: int
    product: _ProductBrief | None = None
    row_number: int | None = None
    quantity: int
    unit_price: int
    subtotal: int
    item_data: Any = None
    status: str
    result_message: str | None = None
    cost_unit_price: int | None = None
    assigned_account_id: int | None = None
    assignment_status: str
    assigned_at: datetime | None = None
    assigned_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime | None = None

    @field_validator("unit_price", "subtotal", mode="before")
    @classmethod
    def coerce_numeric(cls, v: Any) -> Any:
        return _coerce_decimal(v)

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    """Order response model."""

    id: int
    order_number: str
    user_id: uuid.UUID
    company_id: int | None = None
    user: _UserBrief | None = None
    company: _CompanyBrief | None = None
    status: str
    payment_status: str
    order_type: str = "regular"
    total_amount: int
    vat_amount: int
    notes: str | None = None
    source: str
    submitted_by: uuid.UUID | None = None
    submitted_at: datetime | None = None
    payment_confirmed_by: uuid.UUID | None = None
    payment_confirmed_at: datetime | None = None
    hold_reason: str | None = None
    payment_checked_by: uuid.UUID | None = None
    payment_checked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    selection_status: str = "included"
    selected_by: uuid.UUID | None = None
    selected_at: datetime | None = None
    items: list[OrderItemResponse] = []

    @field_validator("total_amount", "vat_amount", mode="before")
    @classmethod
    def coerce_numeric(cls, v: Any) -> Any:
        return _coerce_decimal(v)

    model_config = {"from_attributes": True}


class OrderBriefResponse(BaseModel):
    """Brief order info for list responses (without items)."""

    id: int
    order_number: str
    user_id: uuid.UUID
    company_id: int | None = None
    user: _UserBrief | None = None
    company: _CompanyBrief | None = None
    status: str
    payment_status: str
    order_type: str = "regular"
    total_amount: int
    vat_amount: int
    notes: str | None = None
    source: str
    created_at: datetime
    updated_at: datetime | None = None

    @field_validator("total_amount", "vat_amount", mode="before")
    @classmethod
    def coerce_numeric(cls, v: Any) -> Any:
        return _coerce_decimal(v)

    model_config = {"from_attributes": True}

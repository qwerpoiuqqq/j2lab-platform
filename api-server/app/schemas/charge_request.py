"""ChargeRequest schemas: request/response models."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class ChargeRequestCreate(BaseModel):
    """Body for submitting a new charge / refund request."""

    amount: int = Field(..., gt=0, description="Amount to charge or refund (positive)")
    request_type: str = Field(default="charge", description="'charge' or 'refund'")
    reason: str | None = None


class ChargeRequestReject(BaseModel):
    """Body for rejecting a charge request."""

    reason: str | None = None


class ChargeRequestResponse(BaseModel):
    """Charge request response model."""

    id: int
    user_id: uuid.UUID
    user_name: str | None = None
    user_login_id: str | None = None
    request_type: str
    amount: int
    payment_amount: int | None = None
    vat_amount: int | None = None
    status: str
    approved_by: uuid.UUID | None = None
    approved_at: datetime | None = None
    rejected_reason: str | None = None
    reason: str | None = None
    created_at: datetime

    @field_validator("amount", "payment_amount", "vat_amount", mode="before")
    @classmethod
    def coerce_numeric(cls, v):
        if isinstance(v, Decimal):
            return int(v)
        return v

    model_config = {"from_attributes": True}


class ChargeRequestListResponse(BaseModel):
    """Paginated charge request list."""

    items: list[ChargeRequestResponse]
    total: int


class ChargeSummaryResponse(BaseModel):
    """Summary of pending charge requests."""

    pending_count: int
    pending_total: int

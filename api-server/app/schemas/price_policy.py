"""PricePolicy schemas: CRUD request/response models."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class PricePolicyCreate(BaseModel):
    """Schema for creating a price policy."""

    product_id: int
    user_id: uuid.UUID | None = None
    role: str | None = None
    unit_price: int = Field(..., ge=0)
    effective_from: date
    effective_to: date | None = None


class PricePolicyUpdate(BaseModel):
    """Schema for updating a price policy."""

    unit_price: int | None = Field(None, ge=0)
    effective_to: date | None = None


class PricePolicyResponse(BaseModel):
    """Price policy response model."""

    id: int
    product_id: int
    user_id: uuid.UUID | None = None
    role: str | None = None
    unit_price: int
    effective_from: date
    effective_to: date | None = None
    created_at: datetime

    @field_validator("unit_price", mode="before")
    @classmethod
    def coerce_unit_price(cls, v):
        if isinstance(v, Decimal):
            return int(v)
        return v

    model_config = {"from_attributes": True}

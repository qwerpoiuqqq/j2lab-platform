"""Product schemas: CRUD request/response models."""

from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ProductCreate(BaseModel):
    """Schema for creating a product."""

    name: str = Field(..., min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    category: str | None = Field(None, max_length=100)
    description: str | None = None
    form_schema: Any = None
    base_price: int | None = None
    cost_price: int | None = None
    reduction_rate: int | None = Field(None, ge=0, le=100)
    min_work_days: int | None = None
    max_work_days: int | None = None
    min_daily_limit: int | None = None
    daily_deadline: time = time(18, 0)
    deadline_timezone: str = "Asia/Seoul"
    setup_delay_minutes: int = 30
    is_active: bool = True


class ProductUpdate(BaseModel):
    """Schema for updating a product (all fields optional)."""

    name: str | None = Field(None, min_length=1, max_length=200)
    code: str | None = Field(None, min_length=1, max_length=50)
    category: str | None = Field(None, max_length=100)
    description: str | None = None
    form_schema: Any = None
    base_price: int | None = None
    cost_price: int | None = None
    reduction_rate: int | None = Field(None, ge=0, le=100)
    min_work_days: int | None = None
    max_work_days: int | None = None
    min_daily_limit: int | None = None
    daily_deadline: time | None = None
    deadline_timezone: str | None = None
    setup_delay_minutes: int | None = None
    is_active: bool | None = None


class ProductResponse(BaseModel):
    """Product response model."""

    id: int
    name: str
    code: str | None = None
    category: str | None = None
    description: str | None = None
    form_schema: Any = None
    base_price: int | None = None
    cost_price: int | None = None
    reduction_rate: int | None = None
    min_work_days: int | None = None
    max_work_days: int | None = None
    min_daily_limit: int | None = None
    daily_deadline: time
    deadline_timezone: str
    setup_delay_minutes: int = 30
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None

    @field_validator("base_price", "cost_price", mode="before")
    @classmethod
    def coerce_numeric(cls, v):
        if isinstance(v, Decimal):
            return int(v)
        return v

    model_config = {"from_attributes": True}


class ProductResponseWithWarnings(ProductResponse):
    """Product response with pipeline validation warnings."""

    pipeline_warnings: list[str] = []


class ProductBriefResponse(BaseModel):
    """Brief product info for nested responses."""

    id: int
    name: str
    code: str | None = None
    base_price: int | None = None

    @field_validator("base_price", mode="before")
    @classmethod
    def coerce_base_price(cls, v):
        if isinstance(v, Decimal):
            return int(v)
        return v

    model_config = {"from_attributes": True}

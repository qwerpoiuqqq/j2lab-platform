"""NetworkPreset schemas: request/response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NetworkPresetCreate(BaseModel):
    """Schema for creating a network preset."""

    company_id: int
    campaign_type: str = Field(..., min_length=1, max_length=50)
    tier_order: int = Field(..., ge=1)
    name: str = Field(..., min_length=1, max_length=100)
    media_config: dict[str, Any] = Field(default_factory=dict)
    handler_user_id: str | None = None
    cost_price: int = 0
    extension_threshold: int = Field(default=10000, ge=0)
    description: str | None = None
    is_active: bool = True


class NetworkPresetUpdate(BaseModel):
    """Schema for updating a network preset."""

    name: str | None = Field(None, min_length=1, max_length=100)
    tier_order: int | None = Field(None, ge=1)
    media_config: dict[str, Any] | None = None
    handler_user_id: str | None = None
    cost_price: int | None = None
    extension_threshold: int | None = Field(default=None, ge=0)
    description: str | None = None
    is_active: bool | None = None


class NetworkPresetResponse(BaseModel):
    """Network preset response model."""

    id: int
    company_id: int
    campaign_type: str
    tier_order: int
    name: str
    media_config: dict[str, Any] | None = None
    handler_user_id: str | None = None
    cost_price: int | None = 0
    extension_threshold: int = 10000
    description: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}

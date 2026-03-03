"""SuperapAccount schemas: request/response models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SuperapAccountCreate(BaseModel):
    """Schema for creating a superap account."""

    user_id_superap: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, description="Plain text, will be encrypted")
    agency_name: str | None = Field(None, max_length=100)
    company_id: int | None = None
    network_preset_id: int | None = None
    unit_cost_traffic: int = 21
    unit_cost_save: int = 31
    assignment_order: int = 0
    is_active: bool = True


class SuperapAccountUpdate(BaseModel):
    """Schema for updating a superap account."""

    password: str | None = Field(None, min_length=1, description="New password (will be encrypted)")
    agency_name: str | None = None
    network_preset_id: int | None = None
    unit_cost_traffic: int | None = None
    unit_cost_save: int | None = None
    assignment_order: int | None = None
    is_active: bool | None = None


class SuperapAccountResponse(BaseModel):
    """Superap account response model (no password exposed)."""

    id: int
    user_id_superap: str
    agency_name: str | None = None
    company_id: int | None = None
    company_name: str | None = None
    network_preset_id: int | None = None
    unit_cost_traffic: int
    unit_cost_save: int
    assignment_order: int
    is_active: bool
    campaign_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}

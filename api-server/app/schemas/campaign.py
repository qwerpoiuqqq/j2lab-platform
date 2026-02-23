"""Campaign schemas: request/response models."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class CampaignCreate(BaseModel):
    """Schema for creating a campaign."""

    order_item_id: int | None = None
    place_id: int | None = None
    place_url: str = Field(..., min_length=1)
    place_name: str = ""
    campaign_type: str = Field(..., pattern="^(traffic|save|landmark)$")
    start_date: date
    end_date: date
    daily_limit: int = Field(..., ge=1)
    total_limit: int | None = None
    agency_name: str | None = None
    superap_account_id: int | None = None
    network_preset_id: int | None = None
    company_id: int | None = None


class CampaignUpdate(BaseModel):
    """Schema for updating a campaign (partial)."""

    status: str | None = None
    campaign_code: str | None = None
    daily_limit: int | None = Field(None, ge=1)
    total_limit: int | None = None
    registration_step: str | None = None
    registration_message: str | None = None
    landmark_name: str | None = None
    step_count: int | None = None
    module_context: Any = None


class CampaignResponse(BaseModel):
    """Campaign response model."""

    id: int
    campaign_code: str | None = None
    superap_account_id: int | None = None
    order_item_id: int | None = None
    place_id: int | None = None
    extraction_job_id: int | None = None
    agency_name: str | None = None
    place_name: str
    place_url: str
    campaign_type: str
    registered_at: datetime | None = None
    start_date: date
    end_date: date
    daily_limit: int
    total_limit: int | None = None
    current_conversions: int
    status: str
    registration_step: str | None = None
    registration_message: str | None = None
    extend_target_id: int | None = None
    network_preset_id: int | None = None
    company_id: int | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class CampaignKeywordPoolResponse(BaseModel):
    """Campaign keyword pool entry."""

    id: int
    campaign_id: int
    keyword: str
    is_used: bool
    used_at: datetime | None = None
    round_number: int

    model_config = {"from_attributes": True}


class CampaignKeywordAddRequest(BaseModel):
    """Request to add keywords to a campaign."""

    keywords: list[str] = Field(..., min_length=1)
    round_number: int = 1


class CampaignCallbackRequest(BaseModel):
    """Callback request from campaign-worker."""

    status: str = Field(..., description="active, completed, or failed")
    campaign_code: str | None = None
    error_message: str | None = None
    registration_step: str | None = None

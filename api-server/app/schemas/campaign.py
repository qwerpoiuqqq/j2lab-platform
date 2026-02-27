"""Campaign schemas: request/response models."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.models.campaign import CampaignStatus


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
    total_limit: int | None = Field(None, ge=1)
    agency_name: str | None = None
    superap_account_id: int | None = None
    network_preset_id: int | None = None
    company_id: int | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        """Ensure end_date >= start_date."""
        if self.end_date < self.start_date:
            raise ValueError("end_date must be >= start_date")
        return self


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

    @model_validator(mode="after")
    def validate_status(self):
        """Ensure status is a valid CampaignStatus value if provided."""
        if self.status is not None:
            valid_values = [s.value for s in CampaignStatus]
            if self.status not in valid_values:
                raise ValueError(
                    f"Invalid campaign status '{self.status}'. "
                    f"Valid values: {valid_values}"
                )
        return self


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
    managed_by: uuid.UUID | None = None
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
    round_number: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_keywords(self):
        """Validate individual keyword constraints."""
        for i, kw in enumerate(self.keywords):
            if not kw or not kw.strip():
                raise ValueError(
                    f"Keyword at index {i} is empty or whitespace-only"
                )
            if len(kw) > 255:
                raise ValueError(
                    f"Keyword at index {i} exceeds 255 characters "
                    f"(length={len(kw)})"
                )
        return self


class ExtendCampaignRequest(BaseModel):
    """Request to extend an active campaign."""

    new_end_date: date
    additional_total: int = Field(..., ge=1)
    new_daily_limit: int | None = Field(None, ge=1)


class RegistrationProgressResponse(BaseModel):
    """Response for registration progress query."""

    items: list[dict[str, Any]]


class CampaignCallbackRequest(BaseModel):
    """Callback request from campaign-worker."""

    status: str = Field(
        ...,
        pattern="^(active|completed|extended|failed)$",
        description="active, completed, extended, or failed",
    )
    campaign_code: str | None = None
    error_message: str | None = None
    registration_step: str | None = None

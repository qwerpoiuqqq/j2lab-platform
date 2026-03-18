"""CampaignTemplate schemas: request/response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CampaignTemplateCreate(BaseModel):
    """Schema for creating a campaign template."""

    type_name: str = Field(..., min_length=1, max_length=50)
    code: str | None = Field(None, max_length=50, description="Auto-generated from type_name if not provided")
    description_template: str = Field(..., min_length=1)
    hint_text: str = Field(..., min_length=1)
    campaign_type_selection: str | None = None
    links: list[Any] | None = None
    hashtag: str | None = None
    image_url_200x600: str | None = None
    image_url_720x780: str | None = None
    conversion_text_template: str | None = None
    steps_start: str | None = None
    modules: list[Any] | None = None
    default_redirect_config: dict[str, Any] | None = None
    is_active: bool = True


class CampaignTemplateUpdate(BaseModel):
    """Schema for updating a campaign template."""

    code: str | None = Field(None, max_length=50)
    description_template: str | None = None
    hint_text: str | None = None
    campaign_type_selection: str | None = None
    links: list[Any] | None = None
    hashtag: str | None = None
    image_url_200x600: str | None = None
    image_url_720x780: str | None = None
    conversion_text_template: str | None = None
    steps_start: str | None = None
    modules: list[Any] | None = None
    default_redirect_config: dict[str, Any] | None = None
    is_active: bool | None = None


class CampaignTemplateResponse(BaseModel):
    """Campaign template response model."""

    id: int
    code: str
    type_name: str
    description_template: str
    hint_text: str
    campaign_type_selection: str | None = None
    links: list[Any] | None = None
    hashtag: str | None = None
    image_url_200x600: str | None = None
    image_url_720x780: str | None = None
    conversion_text_template: str | None = None
    steps_start: str | None = None
    modules: list[Any] | None = None
    default_redirect_config: dict[str, Any] | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}

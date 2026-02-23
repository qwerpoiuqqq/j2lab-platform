"""Place schemas: request/response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PlaceCreate(BaseModel):
    """Schema for creating/upserting a place."""

    id: int = Field(..., description="Naver Place ID")
    name: str = Field(..., min_length=1, max_length=200)
    place_type: str = Field(default="place", max_length=20)
    category: str | None = None
    main_category: str | None = None
    city: str | None = None
    si: str | None = None
    gu: str | None = None
    dong: str | None = None
    major_area: str | None = None
    road_address: str | None = None
    jibun_address: str | None = None
    stations: Any = None
    phone: str | None = None
    virtual_phone: str | None = None
    business_hours: str | None = None
    introduction: str | None = None
    naver_url: str | None = None
    keywords: Any = None
    conveniences: Any = None
    micro_reviews: Any = None
    review_menu_keywords: Any = None
    review_theme_keywords: Any = None
    voted_keywords: Any = None
    payment_info: Any = None
    seat_items: Any = None
    specialties: Any = None
    menus: Any = None
    medical_subjects: Any = None
    discovered_regions: Any = None
    has_booking: bool = False
    booking_type: str | None = None
    booking_hub_id: str | None = None
    booking_url: str | None = None


class PlaceUpdate(BaseModel):
    """Schema for updating a place (all fields optional)."""

    name: str | None = Field(None, min_length=1, max_length=200)
    place_type: str | None = None
    category: str | None = None
    main_category: str | None = None
    city: str | None = None
    si: str | None = None
    gu: str | None = None
    dong: str | None = None
    major_area: str | None = None
    road_address: str | None = None
    jibun_address: str | None = None
    naver_url: str | None = None


class PlaceResponse(BaseModel):
    """Place response model."""

    id: int
    name: str
    place_type: str
    category: str | None = None
    main_category: str | None = None
    city: str | None = None
    si: str | None = None
    gu: str | None = None
    dong: str | None = None
    major_area: str | None = None
    road_address: str | None = None
    jibun_address: str | None = None
    stations: Any = None
    phone: str | None = None
    naver_url: str | None = None
    has_booking: bool = False
    last_scraped_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PlaceBriefResponse(BaseModel):
    """Brief place info for nested responses."""

    id: int
    name: str
    place_type: str
    gu: str | None = None
    major_area: str | None = None

    model_config = {"from_attributes": True}

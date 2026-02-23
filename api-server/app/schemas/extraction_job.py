"""ExtractionJob schemas: request/response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ExtractionJobCreate(BaseModel):
    """Schema for creating an extraction job."""

    naver_url: str = Field(..., min_length=1)
    order_item_id: int | None = None
    target_count: int = Field(default=100, ge=1, le=500)
    max_rank: int = Field(default=50, ge=1, le=100)
    min_rank: int = Field(default=1, ge=1)
    name_keyword_ratio: float = Field(default=0.30, ge=0.0, le=1.0)


class ExtractionJobResponse(BaseModel):
    """Extraction job response model."""

    id: int
    order_item_id: int | None = None
    place_id: int | None = None
    naver_url: str
    target_count: int
    max_rank: int
    min_rank: int
    name_keyword_ratio: float
    status: str
    place_name: str | None = None
    result_count: int
    results: Any = None
    error_message: str | None = None
    proxy_slot: int | None = None
    worker_id: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class ExtractionCallbackRequest(BaseModel):
    """Callback request from keyword-worker."""

    status: str = Field(..., description="completed or failed")
    result_count: int | None = None
    place_id: int | None = None
    place_name: str | None = None
    error_message: str | None = None

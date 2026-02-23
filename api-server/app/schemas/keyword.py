"""Keyword schemas: request/response models."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class KeywordResponse(BaseModel):
    """Keyword response model."""

    id: int
    place_id: int
    keyword: str
    keyword_type: str | None = None
    search_query: str | None = None
    current_rank: int | None = None
    current_map_type: str | None = None
    last_checked_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class KeywordRankHistoryResponse(BaseModel):
    """Keyword rank history entry."""

    id: int
    keyword_id: int
    rank_position: int | None = None
    map_type: str | None = None
    recorded_date: date
    created_at: datetime

    model_config = {"from_attributes": True}

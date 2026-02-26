"""Notice schemas: CRUD request/response models."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class NoticeCreate(BaseModel):
    """Schema for creating a notice."""

    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    is_pinned: bool = False


class NoticeUpdate(BaseModel):
    """Schema for updating a notice."""

    title: str | None = Field(None, min_length=1, max_length=200)
    content: str | None = Field(None, min_length=1)
    is_pinned: bool | None = None
    is_active: bool | None = None


class NoticeResponse(BaseModel):
    """Notice response model."""

    id: int
    title: str
    content: str
    author_id: uuid.UUID | None = None
    is_pinned: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None
    author_name: str | None = None

    model_config = {"from_attributes": True}

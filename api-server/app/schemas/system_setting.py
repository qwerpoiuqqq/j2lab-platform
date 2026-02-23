"""SystemSetting schemas: CRUD request/response models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SystemSettingCreate(BaseModel):
    """Schema for creating a system setting."""

    key: str = Field(..., min_length=1, max_length=100)
    value: Any
    description: str | None = None


class SystemSettingUpdate(BaseModel):
    """Schema for updating a system setting value."""

    value: Any
    description: str | None = None


class SystemSettingResponse(BaseModel):
    """System setting response model."""

    key: str
    value: Any
    description: str | None = None
    updated_by: uuid.UUID | None = None
    updated_at: datetime

    model_config = {"from_attributes": True}

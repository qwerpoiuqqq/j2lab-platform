"""Company schemas: CRUD request/response models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CompanyCreate(BaseModel):
    """Schema for creating a company."""

    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=50)
    is_active: bool = True


class CompanyUpdate(BaseModel):
    """Schema for updating a company (all fields optional)."""

    name: str | None = Field(None, min_length=1, max_length=100)
    code: str | None = Field(None, min_length=1, max_length=50)
    is_active: bool | None = None


class CompanyResponse(BaseModel):
    """Company response model."""

    id: int
    name: str
    code: str
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}

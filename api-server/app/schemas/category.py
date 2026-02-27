"""Category schemas: CRUD request/response models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CategoryCreate(BaseModel):
    """Schema for creating a category."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    icon: str | None = Field(None, max_length=50)
    sort_order: int = 0
    is_active: bool = True


class CategoryUpdate(BaseModel):
    """Schema for updating a category."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    icon: str | None = Field(None, max_length=50)
    sort_order: int | None = None
    is_active: bool | None = None


class CategoryResponse(BaseModel):
    """Category response model."""

    id: int
    name: str
    description: str | None = None
    icon: str | None = None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class CategoryReorderItem(BaseModel):
    """Single item in a reorder request."""

    id: int
    sort_order: int


class CategoryReorderRequest(BaseModel):
    """Request body for reordering categories."""

    items: list[CategoryReorderItem] = Field(..., min_length=1)

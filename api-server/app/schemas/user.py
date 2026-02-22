"""User schemas: CRUD request/response models."""

from __future__ import annotations

import uuid
from datetime import datetime

from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import UserRole


class UserCreate(BaseModel):
    """Schema for creating a user."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=1, max_length=50)
    phone: str | None = Field(None, max_length=20)
    company_id: int | None = None
    role: UserRole = UserRole.SUB_ACCOUNT
    parent_id: uuid.UUID | None = None


class UserUpdate(BaseModel):
    """Schema for updating a user (all fields optional)."""

    email: EmailStr | None = None
    password: str | None = Field(None, min_length=8, max_length=128)
    name: str | None = Field(None, min_length=1, max_length=50)
    phone: str | None = Field(None, max_length=20)
    company_id: int | None = None
    role: UserRole | None = None
    parent_id: uuid.UUID | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    """User response model (no password)."""

    id: uuid.UUID
    email: str
    name: str
    phone: str | None = None
    company_id: int | None = None
    role: str
    parent_id: uuid.UUID | None = None
    balance: int = 0
    is_active: bool = True
    created_at: datetime
    updated_at: datetime | None = None

    @field_validator("balance", mode="before")
    @classmethod
    def coerce_balance_to_int(cls, v):
        """Coerce Decimal (from PostgreSQL Numeric) to int."""
        if isinstance(v, Decimal):
            return int(v)
        return v

    model_config = {"from_attributes": True}


class UserBriefResponse(BaseModel):
    """Brief user info for nested responses."""

    id: uuid.UUID
    email: str
    name: str
    role: str

    model_config = {"from_attributes": True}


class UserTreeNode(BaseModel):
    """User tree node for hierarchical display."""

    id: uuid.UUID
    email: str
    name: str
    role: str
    is_active: bool
    children: list["UserTreeNode"] = []

    model_config = {"from_attributes": True}

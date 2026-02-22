"""Balance schemas: transaction request/response models."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.models.balance_transaction import TransactionType


class DepositRequest(BaseModel):
    """Schema for deposit (charge) balance."""

    user_id: uuid.UUID
    amount: int = Field(..., gt=0, description="Amount to deposit (positive)")
    description: str | None = None


class WithdrawRequest(BaseModel):
    """Schema for withdraw (deduct) balance."""

    user_id: uuid.UUID
    amount: int = Field(..., gt=0, description="Amount to withdraw (positive)")
    description: str | None = None


class BalanceResponse(BaseModel):
    """User balance info."""

    user_id: uuid.UUID
    balance: int

    @field_validator("balance", mode="before")
    @classmethod
    def coerce_balance(cls, v):
        if isinstance(v, Decimal):
            return int(v)
        return v


class BalanceTransactionResponse(BaseModel):
    """Balance transaction response model."""

    id: int
    user_id: uuid.UUID
    order_id: int | None = None
    amount: int
    balance_after: int
    transaction_type: str
    description: str | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime

    @field_validator("amount", "balance_after", mode="before")
    @classmethod
    def coerce_numeric(cls, v):
        if isinstance(v, Decimal):
            return int(v)
        return v

    model_config = {"from_attributes": True}

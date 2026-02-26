"""Notification schemas: response models."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    """Single notification response."""

    id: int
    user_id: uuid.UUID
    type: str
    title: str
    message: str
    related_id: int | None = None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    """Notification list with unread count."""

    items: list[NotificationResponse]
    total: int
    page: int
    size: int
    pages: int
    unread_count: int

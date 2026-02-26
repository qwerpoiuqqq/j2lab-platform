"""Notifications router: list, mark-read for current user."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.notification import NotificationListResponse, NotificationResponse
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/", response_model=NotificationListResponse)
async def list_notifications(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List notifications for the current user with unread count."""
    offset = (page - 1) * size
    items, total, unread_count = await notification_service.get_notifications(
        db, user_id=current_user.id, skip=offset, limit=size,
    )
    pages = (total + size - 1) // size if size > 0 else 0
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in items],
        total=total,
        page=page,
        size=size,
        pages=pages,
        unread_count=unread_count,
    )


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Mark a single notification as read."""
    notification = await notification_service.mark_as_read(
        db, notification_id=notification_id, user_id=current_user.id,
    )
    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )
    return notification


@router.post("/read-all", response_model=MessageResponse)
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Mark all notifications as read for the current user."""
    count = await notification_service.mark_all_as_read(db, user_id=current_user.id)
    return MessageResponse(message=f"Marked {count} notifications as read")

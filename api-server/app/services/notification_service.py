"""Notification service: CRUD + read-state management."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification


async def get_notifications(
    db: AsyncSession,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[Notification], int, int]:
    """Get paginated notifications for a user.

    Returns (items, total_count, unread_count).
    """
    base = select(Notification).where(Notification.user_id == user_id)
    count_base = select(func.count()).select_from(Notification).where(
        Notification.user_id == user_id
    )

    query = base.order_by(Notification.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    items = list(result.scalars().all())

    total = (await db.execute(count_base)).scalar_one()

    unread_count = (
        await db.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)
        )
    ).scalar_one()

    return items, total, unread_count


async def mark_as_read(
    db: AsyncSession,
    notification_id: int,
    user_id: uuid.UUID,
) -> Notification | None:
    """Mark a single notification as read. Returns the notification or None."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        return None

    notification.is_read = True
    await db.flush()
    await db.refresh(notification)
    return notification


async def mark_all_as_read(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> int:
    """Mark all unread notifications as read for a user. Returns count updated."""
    stmt = (
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read == False)
        .values(is_read=True)
    )
    result = await db.execute(stmt)
    await db.flush()
    return result.rowcount


async def create_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    type: str,
    title: str,
    message: str,
    related_id: int | None = None,
) -> Notification:
    """Create a new notification for a user."""
    notification = Notification(
        user_id=user_id,
        type=type,
        title=title,
        message=message,
        related_id=related_id,
    )
    db.add(notification)
    await db.flush()
    await db.refresh(notification)
    return notification

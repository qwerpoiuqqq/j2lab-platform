"""Notification service: CRUD + read-state management + event helpers."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification

logger = logging.getLogger(__name__)


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


# ============================================================
# Event-based notification helpers
# ============================================================


async def _get_order_owner_id(db: AsyncSession, order) -> uuid.UUID | None:
    """Get the user_id of the order owner (distributor or direct user)."""
    from app.models.user import User

    # If the order user has a parent (sub_account), notify the parent (distributor)
    user_result = await db.execute(
        select(User).where(User.id == order.user_id)
    )
    user = user_result.scalar_one_or_none()
    if user and user.parent_id:
        return user.parent_id
    return order.user_id


async def notify_payment_confirmed(db: AsyncSession, order, confirmed_by) -> None:
    """Notify the distributor/user that payment has been confirmed."""
    target_id = await _get_order_owner_id(db, order)
    if not target_id:
        return
    order_num = getattr(order, "order_number", str(order.id))
    await create_notification(
        db,
        user_id=target_id,
        type="settlement",
        title=f"[입금 확인] 주문 {order_num}",
        message=f"주문 {order_num}의 입금이 확인되었습니다.",
        related_id=order.id,
    )


async def notify_payment_held(db: AsyncSession, order, reason: str) -> None:
    """Notify the distributor/user that payment has been held."""
    target_id = await _get_order_owner_id(db, order)
    if not target_id:
        return
    order_num = getattr(order, "order_number", str(order.id))
    await create_notification(
        db,
        user_id=target_id,
        type="settlement",
        title=f"[보류] 주문 {order_num}",
        message=f"주문 {order_num}이(가) 보류되었습니다. 사유: {reason}",
        related_id=order.id,
    )


async def notify_payment_rejected(db: AsyncSession, order, reason: str) -> None:
    """Notify the distributor/user that payment has been rejected."""
    target_id = await _get_order_owner_id(db, order)
    if not target_id:
        return
    order_num = getattr(order, "order_number", str(order.id))
    await create_notification(
        db,
        user_id=target_id,
        type="settlement",
        title=f"[반려] 주문 {order_num}",
        message=f"주문 {order_num}이(가) 반려되었습니다. 사유: {reason}",
        related_id=order.id,
    )


async def notify_campaign_activated(db: AsyncSession, campaign) -> None:
    """Notify handler that a campaign has been activated."""
    from app.models.user import User

    # Notify system admins + the campaign's managed_by user
    notify_ids: set[uuid.UUID] = set()
    if hasattr(campaign, "managed_by") and campaign.managed_by:
        notify_ids.add(campaign.managed_by)

    admin_result = await db.execute(
        select(User.id).where(User.role == "system_admin", User.is_active.is_(True))
    )
    for row in admin_result:
        notify_ids.add(row[0])

    place_name = getattr(campaign, "place_name", "")
    code = getattr(campaign, "campaign_code", "") or ""
    for uid in notify_ids:
        await create_notification(
            db,
            user_id=uid,
            type="campaign",
            title=f"[캠페인 활성화] {place_name}",
            message=f"캠페인 {code}이(가) 활성화되었습니다. ({place_name})",
            related_id=campaign.id,
        )


async def notify_campaign_failed(db: AsyncSession, campaign, error_message: str) -> None:
    """Notify handler that a campaign registration has failed."""
    from app.models.user import User

    notify_ids: set[uuid.UUID] = set()
    if hasattr(campaign, "managed_by") and campaign.managed_by:
        notify_ids.add(campaign.managed_by)

    admin_result = await db.execute(
        select(User.id).where(User.role == "system_admin", User.is_active.is_(True))
    )
    for row in admin_result:
        notify_ids.add(row[0])

    place_name = getattr(campaign, "place_name", "")
    for uid in notify_ids:
        await create_notification(
            db,
            user_id=uid,
            type="campaign",
            title=f"[등록 실패] {place_name}",
            message=f"캠페인 등록에 실패했습니다: {error_message}",
            related_id=campaign.id,
        )


async def notify_conversion_threshold(db: AsyncSession, campaign) -> None:
    """Notify handler that conversion threshold has been exceeded."""
    from app.models.user import User

    notify_ids: set[uuid.UUID] = set()
    if hasattr(campaign, "managed_by") and campaign.managed_by:
        notify_ids.add(campaign.managed_by)

    admin_result = await db.execute(
        select(User.id).where(User.role == "system_admin", User.is_active.is_(True))
    )
    for row in admin_result:
        notify_ids.add(row[0])

    place_name = getattr(campaign, "place_name", "")
    conversions = getattr(campaign, "current_conversions", 0)
    for uid in notify_ids:
        await create_notification(
            db,
            user_id=uid,
            type="campaign",
            title=f"[전환수 초과] {place_name}",
            message=f"캠페인의 전환수({conversions})가 임계값을 초과했습니다.",
            related_id=campaign.id,
        )

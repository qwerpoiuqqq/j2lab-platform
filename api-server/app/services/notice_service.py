"""Notice service: CRUD operations for notices."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notice import Notice
from app.schemas.notice import NoticeCreate, NoticeUpdate


async def get_notices(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    active_only: bool = True,
) -> tuple[list[Notice], int]:
    """Get paginated list of notices. Pinned notices come first."""
    query = select(Notice)
    count_query = select(func.count()).select_from(Notice)

    if active_only:
        query = query.where(Notice.is_active == True)
        count_query = count_query.where(Notice.is_active == True)

    query = (
        query
        .order_by(Notice.is_pinned.desc(), Notice.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(query)
    items = list(result.scalars().all())

    total = (await db.execute(count_query)).scalar_one()

    return items, total


async def get_notice_by_id(
    db: AsyncSession,
    notice_id: int,
) -> Notice | None:
    """Get a single notice by ID."""
    result = await db.execute(
        select(Notice).where(Notice.id == notice_id)
    )
    return result.scalar_one_or_none()


async def create_notice(
    db: AsyncSession,
    data: NoticeCreate,
    author_id: uuid.UUID,
) -> Notice:
    """Create a new notice."""
    notice = Notice(
        title=data.title,
        content=data.content,
        author_id=author_id,
        is_pinned=data.is_pinned,
    )
    db.add(notice)
    await db.flush()
    await db.refresh(notice)
    return notice


async def update_notice(
    db: AsyncSession,
    notice: Notice,
    data: NoticeUpdate,
) -> Notice:
    """Update an existing notice with partial data."""
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(notice, key, value)
    await db.flush()
    await db.refresh(notice)
    return notice


async def delete_notice(
    db: AsyncSession,
    notice: Notice,
) -> None:
    """Delete a notice."""
    await db.delete(notice)
    await db.flush()

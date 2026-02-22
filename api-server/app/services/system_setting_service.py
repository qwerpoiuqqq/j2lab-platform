"""SystemSetting service: CRUD for runtime configuration."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_setting import SystemSetting
from app.schemas.system_setting import SystemSettingCreate, SystemSettingUpdate


async def get_all_settings(
    db: AsyncSession,
) -> list[SystemSetting]:
    """Get all system settings."""
    result = await db.execute(
        select(SystemSetting).order_by(SystemSetting.key)
    )
    return list(result.scalars().all())


async def get_setting_by_key(
    db: AsyncSession,
    key: str,
) -> SystemSetting | None:
    """Get a single system setting by key."""
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == key)
    )
    return result.scalar_one_or_none()


async def create_setting(
    db: AsyncSession,
    data: SystemSettingCreate,
    updated_by: uuid.UUID | None = None,
) -> SystemSetting:
    """Create a new system setting."""
    setting = SystemSetting(
        key=data.key,
        value=data.value,
        description=data.description,
        updated_by=updated_by,
    )
    db.add(setting)
    await db.flush()
    await db.refresh(setting)
    return setting


async def upsert_setting(
    db: AsyncSession,
    key: str,
    value: Any,
    description: str | None = None,
    updated_by: uuid.UUID | None = None,
) -> SystemSetting:
    """Create or update a system setting."""
    setting = await get_setting_by_key(db, key)
    if setting is None:
        setting = SystemSetting(
            key=key,
            value=value,
            description=description,
            updated_by=updated_by,
        )
        db.add(setting)
    else:
        setting.value = value
        if description is not None:
            setting.description = description
        setting.updated_by = updated_by

    await db.flush()
    await db.refresh(setting)
    return setting


async def delete_setting(
    db: AsyncSession,
    setting: SystemSetting,
) -> None:
    """Delete a system setting."""
    await db.delete(setting)
    await db.flush()

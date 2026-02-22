"""System Settings router: CRUD for runtime configuration (system_admin only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import RoleChecker
from app.models.user import User, UserRole
from app.schemas.system_setting import (
    SystemSettingResponse,
    SystemSettingUpdate,
)
from app.services import system_setting_service

router = APIRouter(prefix="/settings", tags=["settings"])

system_admin_checker = RoleChecker([UserRole.SYSTEM_ADMIN])


@router.get("/", response_model=list[SystemSettingResponse])
async def list_settings(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(system_admin_checker),
):
    """Get all system settings (system_admin only)."""
    settings = await system_setting_service.get_all_settings(db)
    return [SystemSettingResponse.model_validate(s) for s in settings]


@router.get("/{key}", response_model=SystemSettingResponse)
async def get_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(system_admin_checker),
):
    """Get a single system setting by key (system_admin only)."""
    setting = await system_setting_service.get_setting_by_key(db, key)
    if setting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{key}' not found",
        )
    return setting


@router.put("/{key}", response_model=SystemSettingResponse)
async def upsert_setting(
    key: str,
    body: SystemSettingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(system_admin_checker),
):
    """Create or update a system setting (system_admin only)."""
    setting = await system_setting_service.upsert_setting(
        db,
        key=key,
        value=body.value,
        description=body.description,
        updated_by=current_user.id,
    )
    return setting


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(system_admin_checker),
):
    """Delete a system setting (system_admin only)."""
    setting = await system_setting_service.get_setting_by_key(db, key)
    if setting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{key}' not found",
        )
    await system_setting_service.delete_setting(db, setting)

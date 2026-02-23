"""Network presets router: CRUD for network preset management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import RoleChecker
from app.models.user import User, UserRole
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.network_preset import (
    NetworkPresetCreate,
    NetworkPresetResponse,
    NetworkPresetUpdate,
)
from app.services import network_preset_service

router = APIRouter(prefix="/network-presets", tags=["network-presets"])

admin_checker = RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN])
system_admin_checker = RoleChecker([UserRole.SYSTEM_ADMIN])


@router.get("/", response_model=PaginatedResponse[NetworkPresetResponse])
async def list_presets(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=100),
    company_id: int | None = None,
    campaign_type: str | None = None,
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_checker),
):
    """List network presets (company_admin sees own company only)."""
    pagination = PaginationParams(page=page, size=size)

    # Scope to company for non-system_admin
    effective_company_id = company_id
    if UserRole(current_user.role) == UserRole.COMPANY_ADMIN:
        effective_company_id = current_user.company_id

    presets, total = await network_preset_service.get_presets(
        db,
        company_id=effective_company_id,
        campaign_type=campaign_type,
        is_active=is_active,
        skip=pagination.offset,
        limit=pagination.size,
    )
    return PaginatedResponse.create(
        items=[NetworkPresetResponse.model_validate(p) for p in presets],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.post(
    "/",
    response_model=NetworkPresetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_preset(
    body: NetworkPresetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_checker),
):
    """Create a new network preset."""
    # Company_admin can only create for their own company
    if (
        UserRole(current_user.role) == UserRole.COMPANY_ADMIN
        and body.company_id != current_user.company_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create preset for another company",
        )

    try:
        preset = await network_preset_service.create_preset(db, body)
    except Exception as e:
        # Handle unique constraint violation
        if "uq_network_presets_company_type_tier" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Network preset with tier_order={body.tier_order} "
                    f"already exists for this company/campaign_type"
                ),
            )
        raise
    return preset


@router.patch("/{preset_id}", response_model=NetworkPresetResponse)
async def update_preset(
    preset_id: int,
    body: NetworkPresetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_checker),
):
    """Update a network preset."""
    preset = await network_preset_service.get_preset_by_id(db, preset_id)
    if preset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Network preset not found",
        )

    # Company_admin scope check
    if (
        UserRole(current_user.role) == UserRole.COMPANY_ADMIN
        and preset.company_id != current_user.company_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify preset of another company",
        )

    updated = await network_preset_service.update_preset(db, preset, body)
    return updated


@router.delete(
    "/{preset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_preset(
    preset_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(system_admin_checker),
):
    """Delete a network preset (system_admin only)."""
    preset = await network_preset_service.get_preset_by_id(db, preset_id)
    if preset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Network preset not found",
        )
    await network_preset_service.delete_preset(db, preset)

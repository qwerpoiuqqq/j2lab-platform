"""Network preset service: CRUD operations for network presets."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign
from app.models.network_preset import NetworkPreset
from app.schemas.network_preset import NetworkPresetCreate, NetworkPresetUpdate


async def get_presets(
    db: AsyncSession,
    company_id: int | None = None,
    campaign_type: str | None = None,
    is_active: bool | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[NetworkPreset], int]:
    """Get paginated list of network presets."""
    query = select(NetworkPreset)
    count_query = select(func.count()).select_from(NetworkPreset)

    if company_id is not None:
        query = query.where(NetworkPreset.company_id == company_id)
        count_query = count_query.where(NetworkPreset.company_id == company_id)
    if campaign_type:
        query = query.where(NetworkPreset.campaign_type == campaign_type)
        count_query = count_query.where(
            NetworkPreset.campaign_type == campaign_type
        )
    if is_active is not None:
        query = query.where(NetworkPreset.is_active == is_active)
        count_query = count_query.where(NetworkPreset.is_active == is_active)

    query = query.order_by(
        NetworkPreset.company_id, NetworkPreset.campaign_type, NetworkPreset.tier_order
    ).offset(skip).limit(limit)

    result = await db.execute(query)
    presets = list(result.scalars().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    return presets, total


async def get_preset_by_id(
    db: AsyncSession, preset_id: int
) -> NetworkPreset | None:
    """Get a single network preset by ID."""
    result = await db.execute(
        select(NetworkPreset).where(NetworkPreset.id == preset_id)
    )
    return result.scalar_one_or_none()


async def create_preset(
    db: AsyncSession, data: NetworkPresetCreate
) -> NetworkPreset:
    """Create a new network preset."""
    preset = NetworkPreset(
        company_id=data.company_id,
        campaign_type=data.campaign_type,
        tier_order=data.tier_order,
        name=data.name,
        media_config=data.media_config,
        handler_user_id=data.handler_user_id,
        cost_price=data.cost_price,
        extension_threshold=data.extension_threshold,
        description=data.description,
        is_active=data.is_active,
    )
    db.add(preset)
    await db.flush()
    await db.refresh(preset)
    return preset


async def update_preset(
    db: AsyncSession, preset: NetworkPreset, data: NetworkPresetUpdate
) -> NetworkPreset:
    """Update an existing network preset."""
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(preset, key, value)
    await db.flush()
    await db.refresh(preset)
    return preset


async def delete_preset(db: AsyncSession, preset: NetworkPreset) -> None:
    """Delete a network preset. Raises 409 if connected campaigns exist."""
    campaign_count_result = await db.execute(
        select(func.count(Campaign.id)).where(
            Campaign.network_preset_id == preset.id
        )
    )
    campaign_count = campaign_count_result.scalar_one()

    if campaign_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete: {campaign_count} campaign(s) are using this network preset",
        )

    await db.delete(preset)
    await db.flush()

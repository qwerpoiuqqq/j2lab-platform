"""Campaign template service: CRUD operations."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign_template import CampaignTemplate
from app.schemas.campaign_template import CampaignTemplateUpdate


async def get_templates(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 50,
    is_active: bool | None = None,
) -> tuple[list[CampaignTemplate], int]:
    """Get paginated list of campaign templates."""
    query = select(CampaignTemplate)
    count_query = select(func.count()).select_from(CampaignTemplate)

    if is_active is not None:
        query = query.where(CampaignTemplate.is_active == is_active)
        count_query = count_query.where(CampaignTemplate.is_active == is_active)

    query = query.order_by(CampaignTemplate.id).offset(skip).limit(limit)

    result = await db.execute(query)
    templates = list(result.scalars().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    return templates, total


async def get_template_by_id(
    db: AsyncSession, template_id: int
) -> CampaignTemplate | None:
    """Get a single template by ID."""
    result = await db.execute(
        select(CampaignTemplate).where(CampaignTemplate.id == template_id)
    )
    return result.scalar_one_or_none()


async def get_template_by_code(
    db: AsyncSession, code: str
) -> CampaignTemplate | None:
    """Get a template by code (traffic/save/landmark)."""
    result = await db.execute(
        select(CampaignTemplate).where(CampaignTemplate.code == code)
    )
    return result.scalar_one_or_none()


async def update_template(
    db: AsyncSession, template: CampaignTemplate, data: CampaignTemplateUpdate
) -> CampaignTemplate:
    """Update an existing campaign template."""
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(template, key, value)
    await db.flush()
    await db.refresh(template)
    return template

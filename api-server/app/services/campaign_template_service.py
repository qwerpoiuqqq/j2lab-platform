"""Campaign template service: CRUD operations."""

from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign_template import CampaignTemplate
from app.schemas.campaign_template import CampaignTemplateCreate, CampaignTemplateUpdate


def _generate_code(type_name: str) -> str:
    """Generate a URL-safe code from type_name (e.g. '트래픽' -> 'traffic')."""
    known_map = {
        "트래픽": "traffic",
        "저장하기": "save",
        "랜드마크": "landmark",
        "길찾기": "directions",
    }
    for korean, english in known_map.items():
        if korean in type_name:
            return english
    # Fallback: slugify
    code = re.sub(r"\s+", "_", type_name.strip())
    code = re.sub(r"[^a-zA-Z0-9가-힣_]", "", code)
    return code[:50].lower() or "template"


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


async def create_template(
    db: AsyncSession, data: CampaignTemplateCreate
) -> CampaignTemplate:
    """Create a new campaign template."""
    code = data.code or _generate_code(data.type_name)

    template = CampaignTemplate(
        code=code,
        type_name=data.type_name,
        description_template=data.description_template,
        hint_text=data.hint_text,
        campaign_type_selection=data.campaign_type_selection,
        links=data.links or [],
        hashtag=data.hashtag,
        image_url_200x600=data.image_url_200x600,
        image_url_720x780=data.image_url_720x780,
        conversion_text_template=data.conversion_text_template,
        steps_start=data.steps_start,
        modules=data.modules or [],
        is_active=data.is_active,
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)
    return template


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


async def delete_template(
    db: AsyncSession, template: CampaignTemplate
) -> None:
    """Delete a campaign template."""
    await db.delete(template)
    await db.flush()

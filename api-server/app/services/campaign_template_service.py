"""Campaign template service: CRUD operations."""

from __future__ import annotations

import logging

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign
from app.models.campaign_template import CampaignTemplate
from app.schemas.campaign_template import CampaignTemplateCreate, CampaignTemplateUpdate
from app.utils.text import slugify

logger = logging.getLogger(__name__)

_KNOWN_TYPE_MAP = {
    "스마트 트래픽": "smart_traffic",
    "스마트 저장하기": "smart_save",
    "트래픽": "smart_traffic",
    "저장하기": "smart_save",
}


def _generate_code(type_name: str) -> str:
    """Generate a URL-safe code from type_name (e.g. '트래픽' -> 'traffic')."""
    for korean, english in _KNOWN_TYPE_MAP.items():
        if korean in type_name:
            return english
    return slugify(type_name, fallback="template")


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
    """Update an existing campaign template.

    If default_redirect_config changes, propagate to all active campaigns
    that match this template's code or type_name.
    """
    update_data = data.model_dump(exclude_unset=True)

    # Check if redirect_config is being changed
    new_redirect_config = update_data.get("default_redirect_config")
    config_changed = (
        new_redirect_config is not None
        and new_redirect_config != template.default_redirect_config
    )

    for key, value in update_data.items():
        setattr(template, key, value)
    await db.flush()
    await db.refresh(template)

    # Propagate redirect_config to active campaigns
    if config_changed and new_redirect_config:
        propagated = await propagate_redirect_config(db, template)
        logger.info(
            "Template %s redirect_config propagated to %d active campaigns",
            template.code, propagated,
        )

    return template


async def propagate_redirect_config(
    db: AsyncSession, template: CampaignTemplate
) -> int:
    """Propagate template's redirect_config to all active campaigns matching this template."""
    active_statuses = [
        "active", "daily_exhausted", "pending_keyword_change",
        "registering", "queued", "pending",
    ]
    result = await db.execute(
        update(Campaign)
        .where(
            Campaign.campaign_type.in_([template.code, template.type_name]),
            Campaign.status.in_(active_statuses),
        )
        .values(redirect_config=template.default_redirect_config)
    )
    return result.rowcount


async def delete_template(
    db: AsyncSession, template: CampaignTemplate
) -> None:
    """Delete a campaign template."""
    await db.delete(template)
    await db.flush()

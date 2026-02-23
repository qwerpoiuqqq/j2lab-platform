"""Campaign service: CRUD + status management.

Actual registration is done by campaign-worker (Phase 3).
This service manages the campaign records and keyword pool.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign, CampaignStatus
from app.models.campaign_keyword_pool import CampaignKeywordPool
from app.schemas.campaign import CampaignCreate, CampaignUpdate


async def get_campaigns(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    status: str | None = None,
    company_id: int | None = None,
    place_id: int | None = None,
    campaign_type: str | None = None,
) -> tuple[list[Campaign], int]:
    """Get paginated list of campaigns."""
    query = select(Campaign)
    count_query = select(func.count()).select_from(Campaign)

    if status:
        query = query.where(Campaign.status == status)
        count_query = count_query.where(Campaign.status == status)
    if company_id is not None:
        query = query.where(Campaign.company_id == company_id)
        count_query = count_query.where(Campaign.company_id == company_id)
    if place_id is not None:
        query = query.where(Campaign.place_id == place_id)
        count_query = count_query.where(Campaign.place_id == place_id)
    if campaign_type:
        query = query.where(Campaign.campaign_type == campaign_type)
        count_query = count_query.where(
            Campaign.campaign_type == campaign_type
        )

    query = query.order_by(Campaign.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    campaigns = list(result.scalars().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    return campaigns, total


async def get_campaign_by_id(
    db: AsyncSession, campaign_id: int
) -> Campaign | None:
    """Get a single campaign by ID."""
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    return result.scalar_one_or_none()


async def create_campaign(
    db: AsyncSession, data: CampaignCreate
) -> Campaign:
    """Create a new campaign."""
    campaign = Campaign(
        order_item_id=data.order_item_id,
        place_id=data.place_id,
        place_url=data.place_url,
        place_name=data.place_name,
        campaign_type=data.campaign_type,
        start_date=data.start_date,
        end_date=data.end_date,
        daily_limit=data.daily_limit,
        total_limit=data.total_limit,
        agency_name=data.agency_name,
        superap_account_id=data.superap_account_id,
        network_preset_id=data.network_preset_id,
        company_id=data.company_id,
        status=CampaignStatus.PENDING.value,
    )
    db.add(campaign)
    await db.flush()
    await db.refresh(campaign)
    return campaign


async def update_campaign(
    db: AsyncSession, campaign: Campaign, data: CampaignUpdate
) -> Campaign:
    """Update a campaign with partial data."""
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(campaign, key, value)
    await db.flush()
    await db.refresh(campaign)
    return campaign


async def get_keyword_pool(
    db: AsyncSession,
    campaign_id: int,
    skip: int = 0,
    limit: int = 200,
    is_used: bool | None = None,
) -> tuple[list[CampaignKeywordPool], int]:
    """Get keywords in a campaign's rotation pool."""
    query = select(CampaignKeywordPool).where(
        CampaignKeywordPool.campaign_id == campaign_id
    )
    count_query = (
        select(func.count())
        .select_from(CampaignKeywordPool)
        .where(CampaignKeywordPool.campaign_id == campaign_id)
    )

    if is_used is not None:
        query = query.where(CampaignKeywordPool.is_used == is_used)
        count_query = count_query.where(
            CampaignKeywordPool.is_used == is_used
        )

    query = query.order_by(CampaignKeywordPool.id).offset(skip).limit(limit)

    result = await db.execute(query)
    keywords = list(result.scalars().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    return keywords, total


async def add_keywords_to_pool(
    db: AsyncSession,
    campaign_id: int,
    keywords: list[str],
    round_number: int = 1,
) -> int:
    """Add keywords to a campaign's rotation pool.

    Returns the count of newly added keywords (skips duplicates).
    Uses a single batch query to check existing keywords instead of N+1 queries.
    """
    if not keywords:
        return 0

    # Batch check: fetch all existing keywords for this campaign in one query
    existing_result = await db.execute(
        select(CampaignKeywordPool.keyword).where(
            CampaignKeywordPool.campaign_id == campaign_id,
            CampaignKeywordPool.keyword.in_(keywords),
        )
    )
    existing_keywords = {row[0] for row in existing_result.all()}

    added = 0
    for kw in keywords:
        if kw not in existing_keywords:
            pool_entry = CampaignKeywordPool(
                campaign_id=campaign_id,
                keyword=kw,
                round_number=round_number,
            )
            db.add(pool_entry)
            added += 1

    if added > 0:
        await db.flush()

    return added


async def handle_campaign_callback(
    db: AsyncSession,
    campaign: Campaign,
    status: str,
    campaign_code: str | None = None,
    error_message: str | None = None,
    registration_step: str | None = None,
) -> Campaign:
    """Handle callback from campaign-worker."""
    now = datetime.now(timezone.utc)

    if status == "active":
        campaign.status = CampaignStatus.ACTIVE.value
        campaign.campaign_code = campaign_code
        campaign.registered_at = now
        campaign.registration_step = "completed"
    elif status == "completed":
        campaign.status = CampaignStatus.COMPLETED.value
    elif status == "extended":
        # Extension: campaign-worker already updated the DB directly.
        # This callback is informational -- no status change needed.
        campaign.registration_message = f"Extended at {now.isoformat()}"
    elif status == "failed":
        campaign.status = CampaignStatus.FAILED.value
        campaign.registration_message = error_message
        campaign.registration_step = registration_step or "failed"
    else:
        raise ValueError(f"Invalid callback status: {status}")

    await db.flush()
    await db.refresh(campaign)
    return campaign

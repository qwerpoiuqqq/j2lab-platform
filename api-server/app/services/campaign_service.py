"""Campaign service: CRUD + status management.

Actual registration is done by campaign-worker (Phase 3).
This service manages the campaign records and keyword pool.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign, CampaignStatus
from app.models.campaign_keyword_pool import CampaignKeywordPool
from app.models.order import OrderItem
from app.schemas.campaign import CampaignCreate, CampaignUpdate


async def get_campaigns(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    status: str | None = None,
    company_id: int | None = None,
    place_id: int | None = None,
    campaign_type: str | None = None,
    managed_by: object | None = None,
    account_id: int | None = None,
    search: str | None = None,
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
    if managed_by is not None:
        query = query.where(Campaign.managed_by == managed_by)
        count_query = count_query.where(Campaign.managed_by == managed_by)
    if account_id is not None:
        query = query.where(Campaign.superap_account_id == account_id)
        count_query = count_query.where(Campaign.superap_account_id == account_id)
    if search:
        search_filter = or_(
            Campaign.place_name.ilike(f"%{search}%"),
            Campaign.campaign_code.ilike(f"%{search}%"),
            Campaign.agency_name.ilike(f"%{search}%"),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

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


async def get_campaign_by_code(
    db: AsyncSession, code: str
) -> Campaign | None:
    """Get a campaign by campaign_code."""
    result = await db.execute(
        select(Campaign).where(Campaign.campaign_code == code)
    )
    return result.scalar_one_or_none()


async def delete_campaign(db: AsyncSession, campaign: Campaign) -> None:
    """Delete a campaign. Prevents deletion of active campaigns.

    Clears FK references from pipeline_states before deleting.
    """
    if campaign.status in ("active", "pending_keyword_change", "registering"):
        raise ValueError(
            f"활성 상태({campaign.status})인 캠페인은 삭제할 수 없습니다. 먼저 중지하세요."
        )
    # Clear FK references from pipeline_states to avoid IntegrityError
    from sqlalchemy import update
    from app.models.pipeline_state import PipelineState
    await db.execute(
        update(PipelineState)
        .where(PipelineState.campaign_id == campaign.id)
        .values(campaign_id=None)
    )
    await db.delete(campaign)
    await db.flush()


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
        campaign_code=data.campaign_code,
        start_date=data.start_date,
        end_date=data.end_date,
        daily_limit=data.daily_limit,
        total_limit=data.total_limit,
        agency_name=data.agency_name,
        superap_account_id=data.superap_account_id,
        network_preset_id=data.network_preset_id,
        company_id=data.company_id,
        original_keywords=data.original_keywords,
        managed_by=data.managed_by,
        status=CampaignStatus.PENDING.value,
    )
    db.add(campaign)
    await db.flush()
    await db.refresh(campaign)
    return campaign


async def update_campaign(
    db: AsyncSession, campaign: Campaign, data: CampaignUpdate
) -> Campaign:
    """Update a campaign with partial data.

    When daily_limit or total_limit changes, sync the linked OrderItem's item_data
    so that the original (pre-margin) values recorded there remain the source of truth
    for billing, while also updating original_daily_limit / original_total_limit on
    the campaign to reflect the new intent.
    """
    update_data = data.model_dump(exclude_unset=True)
    limit_changed = "daily_limit" in update_data or "total_limit" in update_data

    for key, value in update_data.items():
        setattr(campaign, key, value)

    # Sync connected OrderItem when limits are directly modified
    if limit_changed and campaign.order_item_id:
        oi_result = await db.execute(
            select(OrderItem).where(OrderItem.id == campaign.order_item_id)
        )
        order_item = oi_result.scalar_one_or_none()
        if order_item is not None:
            item_data = dict(order_item.item_data or {})
            if "daily_limit" in update_data:
                item_data["daily_limit"] = update_data["daily_limit"]
            if "total_limit" in update_data:
                item_data["total_limit"] = update_data["total_limit"]
            order_item.item_data = item_data

            # Also update original limits on campaign to keep them in sync
            # (direct edit bypasses margin — treat new value as the intended original)
            if "daily_limit" in update_data:
                campaign.original_daily_limit = update_data["daily_limit"]
            if "total_limit" in update_data:
                campaign.original_total_limit = update_data["total_limit"]

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

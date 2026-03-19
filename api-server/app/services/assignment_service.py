"""Assignment service: auto-assignment algorithm (core business logic).

Implements the 3-step assignment algorithm from INTEGRATION_PLAN:

Step 1: Extension Check
  - Same place_id with recent campaign (end_date within 7 days)
  - Uses network_preset.extension_threshold (fallback 10,000)
  - If total_limit combined < threshold -> extend (same account, same network)
  - If >= threshold -> new setup (next network)

Step 2: Network Selection (for new setups)
  - Find unused network_presets for this place_id + campaign_type
  - Select the one with lowest tier_order

Step 3: Account Selection
  - From the selected network_preset, pick active account
  - Ordered by assignment_order ASC

If all networks exhausted: suggest campaign type change.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import httpx
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign
from app.models.network_preset import NetworkPreset
from app.models.order import OrderItem, AssignmentStatus
from app.models.superap_account import SuperapAccount
from app.schemas.assignment import (
    AssignmentResult,
    CampaignBrief,
    NetworkOption,
    PlaceRecommendation,
    PlaceRecommendationV2,
    TypeRecommendation,
)
from app.services import superap_account_service


async def auto_assign(
    db: AsyncSession,
    order_item: OrderItem,
    campaign_type: str,
    place_id: int,
    company_id: int,
    total_limit: int | None = None,
    handler_user_id: uuid.UUID | None = None,
) -> AssignmentResult:
    """Run the auto-assignment algorithm for a single order item."""
    result = AssignmentResult(order_item_id=order_item.id)

    # Step 1: Extension Check
    extension = await _check_extension(
        db, place_id=place_id, campaign_type=campaign_type, new_total=total_limit
    )

    if extension is not None:
        existing_campaign, is_extend = extension
        if is_extend:
            # Extend: use same account and network
            result.is_extension = True
            result.extend_target_campaign_id = existing_campaign.id
            result.assigned_account_id = existing_campaign.superap_account_id
            result.network_preset_id = existing_campaign.network_preset_id
            result.campaign_type = campaign_type

            # Load names for response
            if existing_campaign.superap_account_id:
                account = await db.execute(
                    select(SuperapAccount).where(
                        SuperapAccount.id == existing_campaign.superap_account_id
                    )
                )
                acc = account.scalar_one_or_none()
                if acc:
                    result.assigned_account_name = acc.user_id_superap
            if existing_campaign.network_preset_id:
                preset = await db.execute(
                    select(NetworkPreset).where(
                        NetworkPreset.id == existing_campaign.network_preset_id
                    )
                )
                np = preset.scalar_one_or_none()
                if np:
                    result.network_preset_name = np.name

            # Apply assignment to order item
            await _apply_assignment(db, order_item, result)
            return result
        # else: not extendable (total >= 10,000), fall through to new setup

    # Step 2: Network Selection (담당자 전용 프리셋 우선)
    network_preset = await _select_network(
        db,
        place_id=place_id,
        campaign_type=campaign_type,
        company_id=company_id,
        handler_user_id=handler_user_id,
    )

    if network_preset is None:
        # All networks exhausted — provide a specific Korean message
        opposite_type = "save" if campaign_type == "traffic" else "traffic"
        type_label = "트래픽" if campaign_type == "traffic" else "저장하기"
        result.suggestion = (
            f"회사에 '{type_label}' 타입 네트워크 프리셋이 설정되어 있지 않거나 모두 소진되었습니다. "
            f"네트워크 설정을 확인하거나 '{opposite_type}' 타입으로 변경을 고려하세요."
        )
        result.campaign_type = campaign_type
        return result

    result.network_preset_id = network_preset.id
    result.network_preset_name = network_preset.name
    result.campaign_type = campaign_type

    # Step 3: Account Selection
    account = await _select_account(db, network_preset_id=network_preset.id)

    if account is None:
        result.error = (
            f"네트워크 '{network_preset.name}'에 활성 계정이 없습니다. "
            "superap 계정을 추가하거나 기존 계정을 활성화해 주세요."
        )
        return result

    result.assigned_account_id = account.id
    result.assigned_account_name = account.user_id_superap

    # Apply assignment to order item
    await _apply_assignment(db, order_item, result)
    return result


async def get_recommendation(
    db: AsyncSession,
    place_id: int,
    campaign_type: str,
    company_id: int,
) -> PlaceRecommendation:
    """Get AI recommendation for a place (read-only, no DB writes).

    Used at order entry time to show the user what the system recommends.
    """
    # Check extension possibility
    extension = await _check_extension(
        db, place_id=place_id, campaign_type=campaign_type, new_total=None
    )

    existing_campaigns: list[CampaignBrief] = []
    is_existing = False
    recommended_action = "new"
    recommended_network = None

    if extension is not None:
        existing_campaign, is_extend = extension
        is_existing = True
        recommended_action = "extend" if is_extend else "new"

        # Get campaign history for this place
        history = await get_place_network_history(db, place_id, limit=5)
        for c in history:
            existing_campaigns.append(CampaignBrief(
                campaign_id=c.id,
                campaign_type=c.campaign_type,
                status=c.status,
                total_limit=c.total_limit,
                start_date=str(c.start_date) if c.start_date else "",
                end_date=str(c.end_date) if c.end_date else "",
            ))
    else:
        # Check if this place has ANY campaigns (even older ones)
        all_history = await get_place_network_history(db, place_id, limit=5)
        if all_history:
            is_existing = True
            for c in all_history:
                existing_campaigns.append(CampaignBrief(
                    campaign_id=c.id,
                    campaign_type=c.campaign_type,
                    status=c.status,
                    total_limit=c.total_limit,
                    start_date=str(c.start_date) if c.start_date else "",
                    end_date=str(c.end_date) if c.end_date else "",
                ))

    # Get recommended network
    network = await _select_network(
        db, place_id=place_id, campaign_type=campaign_type, company_id=company_id,
    )
    network_name = network.name if network else None

    return PlaceRecommendation(
        place_id=place_id,
        is_existing=is_existing,
        existing_campaigns=existing_campaigns,
        recommended_network=network_name,
        recommended_action=recommended_action,
    )


async def _get_extension_threshold_for_campaign(
    db: AsyncSession,
    campaign: Campaign,
) -> int:
    """Get extension threshold from campaign's network preset, fallback 10000."""
    if campaign.network_preset_id:
        result = await db.execute(
            select(NetworkPreset.extension_threshold).where(
                NetworkPreset.id == campaign.network_preset_id
            )
        )
        value = result.scalar_one_or_none()
        if value is not None:
            try:
                return int(value)
            except (ValueError, TypeError):
                pass
    return 10000


async def _check_extension(
    db: AsyncSession,
    place_id: int,
    campaign_type: str,
    new_total: int | None = None,
) -> tuple[Campaign, bool] | None:
    """Step 1: Check if this should be an extension of an existing campaign."""
    today = date.today()
    seven_days_ago = today - timedelta(days=7)

    result = await db.execute(
        select(Campaign)
        .where(
            and_(
                Campaign.place_id == place_id,
                Campaign.campaign_type == campaign_type,
                Campaign.end_date >= seven_days_ago,
                Campaign.end_date <= today,
                Campaign.status.in_(["active", "completed", "expired"]),
            )
        )
        .order_by(Campaign.end_date.desc())
        .limit(1)
    )
    existing = result.scalar_one_or_none()

    if existing is None:
        return None

    # If incoming total is unknown, default to "new" to avoid incorrect extension.
    if new_total is None:
        return (existing, False)

    existing_total = existing.total_limit or 0
    combined = existing_total + new_total

    threshold = await _get_extension_threshold_for_campaign(db, existing)
    if combined < threshold:
        return (existing, True)  # Extend
    else:
        return (existing, False)  # New setup needed


async def _select_network(
    db: AsyncSession,
    place_id: int,
    campaign_type: str,
    company_id: int,
    handler_user_id: uuid.UUID | None = None,
) -> NetworkPreset | None:
    """Step 2: Select unused network preset with lowest tier_order.

    Priority:
    1. handler_user_id 전용 프리셋이 있으면 우선 사용
    2. 없으면 일반 프리셋 (handler_user_id IS NULL) 사용

    Only counts successful campaigns (not cancelled/failed) as "used".
    """
    # PHASE 0 fix: only count successful campaigns as used
    used_presets_result = await db.execute(
        select(Campaign.network_preset_id)
        .where(
            and_(
                Campaign.place_id == place_id,
                Campaign.campaign_type == campaign_type,
                Campaign.network_preset_id.isnot(None),
                Campaign.status.in_(["active", "completed", "paused", "expired"]),
            )
        )
        .distinct()
    )
    used_preset_ids = [row[0] for row in used_presets_result.all()]

    # 담당자 전용 프리셋 우선 탐색
    if handler_user_id is not None:
        handler_query = (
            select(NetworkPreset)
            .where(
                and_(
                    NetworkPreset.company_id == company_id,
                    NetworkPreset.campaign_type == campaign_type,
                    NetworkPreset.handler_user_id == handler_user_id,
                    NetworkPreset.is_active == True,  # noqa: E712
                )
            )
            .order_by(NetworkPreset.tier_order.asc())
        )
        if used_preset_ids:
            handler_query = handler_query.where(
                NetworkPreset.id.notin_(used_preset_ids)
            )
        result = await db.execute(handler_query.limit(1))
        preset = result.scalar_one_or_none()
        if preset is not None:
            return preset

    # 일반 프리셋 (handler_user_id IS NULL)
    query = (
        select(NetworkPreset)
        .where(
            and_(
                NetworkPreset.company_id == company_id,
                NetworkPreset.campaign_type == campaign_type,
                NetworkPreset.handler_user_id.is_(None),
                NetworkPreset.is_active == True,  # noqa: E712
            )
        )
        .order_by(NetworkPreset.tier_order.asc())
    )

    if used_preset_ids:
        query = query.where(NetworkPreset.id.notin_(used_preset_ids))

    result = await db.execute(query.limit(1))
    return result.scalar_one_or_none()


async def _select_account(
    db: AsyncSession,
    network_preset_id: int,
) -> SuperapAccount | None:
    """Step 3: Select account from the network preset by assignment_order."""
    from app.core.config import settings
    from sqlalchemy import func as sa_func

    active_count_subquery = (
        select(sa_func.count(Campaign.id))
        .where(
            Campaign.superap_account_id == SuperapAccount.id,
            Campaign.status.in_(["active", "paused", "registering"]),
        )
        .correlate(SuperapAccount)
        .scalar_subquery()
    )

    result = await db.execute(
        select(SuperapAccount)
        .where(
            and_(
                SuperapAccount.network_preset_id == network_preset_id,
                SuperapAccount.is_active == True,  # noqa: E712
                active_count_subquery < settings.MAX_CAMPAIGNS_PER_ACCOUNT,
            )
        )
        .order_by(SuperapAccount.assignment_order.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _apply_assignment(
    db: AsyncSession,
    order_item: OrderItem,
    result: AssignmentResult,
) -> None:
    """Apply the assignment result to the order item and record cost."""
    if result.assigned_account_id:
        order_item.assigned_account_id = result.assigned_account_id
        order_item.assignment_status = AssignmentStatus.AUTO_ASSIGNED.value
        order_item.assigned_at = datetime.now(timezone.utc)

        # PHASE 0: Record unit_cost snapshot from the assigned account
        acc = await superap_account_service.get_account_by_id(db, result.assigned_account_id)
        if acc:
            campaign_type = result.campaign_type or "traffic"
            order_item.cost_unit_price = superap_account_service.resolve_unit_cost(acc, campaign_type)

        await db.flush()


async def confirm_assignment(
    db: AsyncSession,
    order_item: OrderItem,
    confirmed_by: uuid.UUID,
) -> OrderItem:
    """Confirm an auto-assigned account (company_admin action)."""
    if order_item.assignment_status != AssignmentStatus.AUTO_ASSIGNED.value:
        raise ValueError(
            f"Cannot confirm assignment in '{order_item.assignment_status}' status. "
            "Only auto_assigned items can be confirmed."
        )
    order_item.assignment_status = AssignmentStatus.CONFIRMED.value
    order_item.assigned_by = confirmed_by

    # PHASE 0: Also record cost if not already set
    if order_item.cost_unit_price is None and order_item.assigned_account_id:
        acc = await superap_account_service.get_account_by_id(db, order_item.assigned_account_id)
        if acc:
            item_data = order_item.item_data or {}
            campaign_type = item_data.get("campaign_type", "traffic")
            order_item.cost_unit_price = superap_account_service.resolve_unit_cost(acc, campaign_type)

    await db.flush()
    await db.refresh(order_item)
    return order_item


async def override_assignment(
    db: AsyncSession,
    order_item: OrderItem,
    account_id: int,
    confirmed_by: uuid.UUID,
    network_preset_id: int | None = None,
) -> OrderItem:
    """Override the assigned account (company_admin manual change)."""
    order_item.assigned_account_id = account_id
    order_item.assignment_status = AssignmentStatus.OVERRIDDEN.value
    order_item.assigned_by = confirmed_by
    order_item.assigned_at = datetime.now(timezone.utc)

    # PHASE 0: Record cost from new account
    acc = await superap_account_service.get_account_by_id(db, account_id)
    if acc:
        item_data = order_item.item_data or {}
        campaign_type = item_data.get("campaign_type", "traffic")
        order_item.cost_unit_price = superap_account_service.resolve_unit_cost(acc, campaign_type)

    await db.flush()
    await db.refresh(order_item)
    return order_item


async def get_assignment_queue(
    db: AsyncSession,
    company_id: int | None = None,
    assignment_status: str | None = None,
    order_item_id: int | None = None,
    skip: int = 0,
    limit: int = 50,
    handler_user_ids: list | None = None,
) -> list[OrderItem]:
    """Get order items pending assignment or awaiting confirmation."""
    from app.models.order import Order

    query = (
        select(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .where(
            # 입금확인된 주문만 배정 대기열에 포함 (취소/반려 제외)
            Order.status.in_([
                "payment_confirmed",
                "processing",
            ]),
        )
    )

    # When a specific assignment_status is given, use it as the sole filter;
    # otherwise default to showing PENDING + AUTO_ASSIGNED items.
    if assignment_status:
        query = query.where(OrderItem.assignment_status == assignment_status)
    else:
        query = query.where(
            OrderItem.assignment_status.in_([
                AssignmentStatus.PENDING.value,
                AssignmentStatus.AUTO_ASSIGNED.value,
            ])
        )

    if company_id is not None:
        query = query.where(Order.company_id == company_id)
    if handler_user_ids is not None:
        query = query.where(Order.user_id.in_(handler_user_ids))
    if order_item_id is not None:
        query = query.where(OrderItem.id == order_item_id)

    query = query.order_by(OrderItem.created_at.asc()).offset(skip).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().unique().all())


async def get_assignment_queue_enriched(
    db: AsyncSession,
    company_id: int | None = None,
    assignment_status: str | None = None,
    order_item_id: int | None = None,
    skip: int = 0,
    limit: int = 50,
    handler_user_ids: list | None = None,
) -> list[dict]:
    """Get enriched assignment queue with AI recommendation info."""
    from app.models.order import Order
    from app.models.place import Place

    items = await get_assignment_queue(
        db, company_id=company_id, assignment_status=assignment_status,
        order_item_id=order_item_id, skip=skip, limit=limit,
        handler_user_ids=handler_user_ids,
    )

    enriched = []
    for item in items:
        order = await db.get(Order, item.order_id)
        place = await db.get(Place, item.place_id) if item.place_id else None
        account = (
            await db.get(SuperapAccount, item.assigned_account_id)
            if item.assigned_account_id
            else None
        )

        # PHASE 4: Get AI recommendation
        ai_recommendation = "new"
        extend_target_campaign_id = None
        extend_target_info = None

        item_data = item.item_data or {}
        campaign_type = item_data.get("campaign_type", "traffic")

        if item.place_id and order and order.company_id:
            extension = await _check_extension(
                db, place_id=item.place_id,
                campaign_type=campaign_type,
                new_total=item_data.get("total_limit"),
            )
            if extension is not None:
                existing_campaign, is_extend = extension
                if is_extend:
                    ai_recommendation = "extend"
                    extend_target_campaign_id = existing_campaign.id
                    extend_target_info = {
                        "campaign_id": existing_campaign.id,
                        "campaign_type": existing_campaign.campaign_type,
                        "status": existing_campaign.status,
                        "total_limit": existing_campaign.total_limit,
                        "start_date": str(existing_campaign.start_date) if existing_campaign.start_date else None,
                        "end_date": str(existing_campaign.end_date) if existing_campaign.end_date else None,
                    }

        enriched.append({
            "order_item_id": item.id,
            "order_id": item.order_id,
            "order_number": order.order_number if order else None,
            "company_name": order.company.name if order and order.company else None,
            "place_name": place.name if place else item_data.get("place_name"),
            "place_id": item.place_id,
            "campaign_type": campaign_type,
            "assignment_status": item.assignment_status,
            "assigned_account_id": item.assigned_account_id,
            "assigned_account_name": account.user_id_superap if account else None,
            "ai_recommendation": ai_recommendation,
            "extend_target_campaign_id": extend_target_campaign_id,
            "extend_target_info": extend_target_info,
        })

    return enriched


async def get_place_network_history(
    db: AsyncSession,
    place_id: int,
    limit: int = 100,
) -> list[Campaign]:
    """Get network usage history for a place (all campaign types)."""
    result = await db.execute(
        select(Campaign)
        .where(
            and_(
                Campaign.place_id == place_id,
                Campaign.network_preset_id.isnot(None),
            )
        )
        .order_by(Campaign.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# ---- Bidirectional recommendation (V2) ----


async def _get_available_networks(
    db: AsyncSession,
    place_id: int,
    campaign_type: str,
    company_id: int,
) -> tuple[int, list[NetworkOption]]:
    """Get remaining unused network presets for a place+campaign_type.

    Returns (count, list_of_network_options).
    """
    used_presets_result = await db.execute(
        select(Campaign.network_preset_id)
        .where(
            and_(
                Campaign.place_id == place_id,
                Campaign.campaign_type == campaign_type,
                Campaign.network_preset_id.isnot(None),
                Campaign.status.in_(["active", "completed", "paused", "expired"]),
            )
        )
        .distinct()
    )
    used_preset_ids = [row[0] for row in used_presets_result.all()]

    query = (
        select(NetworkPreset)
        .where(
            and_(
                NetworkPreset.company_id == company_id,
                NetworkPreset.campaign_type == campaign_type,
                NetworkPreset.is_active == True,  # noqa: E712
            )
        )
        .order_by(NetworkPreset.tier_order.asc())
    )
    if used_preset_ids:
        query = query.where(NetworkPreset.id.notin_(used_preset_ids))

    result = await db.execute(query)
    presets = list(result.scalars().all())
    network_options = [
        NetworkOption(id=p.id, name=p.name, tier_order=p.tier_order)
        for p in presets
    ]
    return len(presets), network_options


async def _build_type_recommendation(
    db: AsyncSession,
    place_id: int,
    campaign_type: str,
    company_id: int,
) -> TypeRecommendation:
    """Build a TypeRecommendation for one campaign type."""
    extension = await _check_extension(
        db, place_id=place_id, campaign_type=campaign_type, new_total=None
    )

    existing_campaigns: list[CampaignBrief] = []
    is_existing = False
    recommended_action = "new"

    if extension is not None:
        existing_campaign, is_extend = extension
        is_existing = True
        recommended_action = "extend" if is_extend else "new"

    # Fetch campaign history for this type
    history_result = await db.execute(
        select(Campaign)
        .where(
            and_(
                Campaign.place_id == place_id,
                Campaign.campaign_type == campaign_type,
                Campaign.network_preset_id.isnot(None),
            )
        )
        .order_by(Campaign.created_at.desc())
        .limit(5)
    )
    history = list(history_result.scalars().all())
    if history:
        is_existing = True
        for c in history:
            existing_campaigns.append(CampaignBrief(
                campaign_id=c.id,
                campaign_type=c.campaign_type,
                status=c.status,
                total_limit=c.total_limit,
                start_date=str(c.start_date) if c.start_date else "",
                end_date=str(c.end_date) if c.end_date else "",
            ))

    network = await _select_network(
        db, place_id=place_id, campaign_type=campaign_type, company_id=company_id,
    )
    network_name = network.name if network else None
    available_count, network_options = await _get_available_networks(
        db, place_id, campaign_type, company_id
    )

    return TypeRecommendation(
        campaign_type=campaign_type,
        is_existing=is_existing,
        existing_campaigns=existing_campaigns,
        recommended_network=network_name,
        recommended_action=recommended_action,
        available_networks=available_count,
        available_network_list=network_options,
    )


def _determine_recommended_type(
    traffic_rec: TypeRecommendation,
    save_rec: TypeRecommendation,
) -> tuple[str, str]:
    """Determine which campaign type to recommend and why.

    Returns (recommended_type, reason).
    """
    # 1. If one type can extend, prefer that
    if traffic_rec.recommended_action == "extend" and save_rec.recommended_action != "extend":
        return "traffic", "기존 트래픽 캠페인 연장 가능"
    if save_rec.recommended_action == "extend" and traffic_rec.recommended_action != "extend":
        return "save", "기존 저장 캠페인 연장 가능"
    if traffic_rec.recommended_action == "extend" and save_rec.recommended_action == "extend":
        return "traffic", "트래픽/저장 모두 연장 가능, 트래픽 우선"

    # 2. If one type has networks exhausted, recommend the other
    if traffic_rec.available_networks == 0 and save_rec.available_networks > 0:
        return "save", "트래픽 네트워크 소진, 저장 추천"
    if save_rec.available_networks == 0 and traffic_rec.available_networks > 0:
        return "traffic", "저장 네트워크 소진, 트래픽 추천"

    # 3. New place: default to traffic (lower tier_order priority)
    if not traffic_rec.is_existing and not save_rec.is_existing:
        return "traffic", "신규 플레이스, 트래픽 우선 추천"

    # 4. Default: traffic
    return "traffic", "트래픽 기본 추천"


async def _fetch_place_name_lightweight(place_id: int) -> str | None:
    """Fetch place name via keyword-worker's Playwright-based scraper."""
    from app.core.config import settings

    try:
        url = f"{settings.KEYWORD_WORKER_URL}/internal/place-name/{place_id}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("place_name")
    except Exception:
        pass
    return None


async def get_recommendation_both(
    db: AsyncSession,
    place_id: int,
    company_id: int,
) -> PlaceRecommendationV2:
    """Get bidirectional AI recommendation for a place (both traffic and save)."""
    from app.models.place import Place

    traffic_rec = await _build_type_recommendation(db, place_id, "traffic", company_id)
    save_rec = await _build_type_recommendation(db, place_id, "save", company_id)

    is_existing = traffic_rec.is_existing or save_rec.is_existing
    recommended_type, reason = _determine_recommended_type(traffic_rec, save_rec)

    # Resolve place_name: DB first, then lightweight fetch
    place_name: str | None = None
    place = await db.get(Place, place_id)
    if place and place.name:
        place_name = place.name
    else:
        place_name = await _fetch_place_name_lightweight(place_id)

    return PlaceRecommendationV2(
        place_id=place_id,
        place_name=place_name,
        is_existing=is_existing,
        recommended_campaign_type=recommended_type,
        recommendation_reason=reason,
        traffic=traffic_rec,
        save=save_rec,
    )

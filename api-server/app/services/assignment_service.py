"""Assignment service: auto-assignment algorithm (core business logic).

Implements the 3-step assignment algorithm from INTEGRATION_PLAN:

Step 1: Extension Check
  - Same place_id with recent campaign (end_date within 7 days)
  - If total_limit combined < 10,000 -> extend (same account, same network)
  - If >= 10,000 -> new setup (next network)

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

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign
from app.models.network_preset import NetworkPreset
from app.models.order import OrderItem, AssignmentStatus
from app.models.superap_account import SuperapAccount
from app.schemas.assignment import AssignmentResult


async def auto_assign(
    db: AsyncSession,
    order_item: OrderItem,
    campaign_type: str,
    place_id: int,
    company_id: int,
    total_limit: int | None = None,
) -> AssignmentResult:
    """Run the auto-assignment algorithm for a single order item.

    Args:
        db: Database session
        order_item: The order item to assign
        campaign_type: 'traffic' or 'save'
        place_id: Naver Place ID
        company_id: Company ID for network preset lookup
        total_limit: Total limit for the new campaign (for extension check)

    Returns:
        AssignmentResult with assignment details or suggestion
    """
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

    # Step 2: Network Selection
    network_preset = await _select_network(
        db,
        place_id=place_id,
        campaign_type=campaign_type,
        company_id=company_id,
    )

    if network_preset is None:
        # All networks exhausted
        opposite_type = "save" if campaign_type == "traffic" else "traffic"
        result.suggestion = (
            f"All {campaign_type} networks exhausted for this place. "
            f"Consider using '{opposite_type}' campaign type instead."
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
            f"No active accounts found for network preset '{network_preset.name}'"
        )
        return result

    result.assigned_account_id = account.id
    result.assigned_account_name = account.user_id_superap

    # Apply assignment to order item
    await _apply_assignment(db, order_item, result)
    return result


async def _check_extension(
    db: AsyncSession,
    place_id: int,
    campaign_type: str,
    new_total: int | None = None,
) -> tuple[Campaign, bool] | None:
    """Step 1: Check if this should be an extension of an existing campaign.

    Returns:
        (existing_campaign, should_extend) or None if no recent campaign exists.
        should_extend is True if total < 10,000, False if >= 10,000.
    """
    today = date.today()
    seven_days_ago = today - timedelta(days=7)

    # Find recent campaigns for same place + type
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

    # Check total limit threshold
    existing_total = existing.total_limit or 0
    combined = existing_total + (new_total or 0)

    if combined < 10000:
        return (existing, True)  # Extend
    else:
        return (existing, False)  # New setup needed


async def _select_network(
    db: AsyncSession,
    place_id: int,
    campaign_type: str,
    company_id: int,
) -> NetworkPreset | None:
    """Step 2: Select unused network preset with lowest tier_order.

    Checks which network_presets have already been used for this place_id +
    campaign_type, and picks the next unused one.
    """
    # Get network presets already used for this place + campaign_type
    used_presets_result = await db.execute(
        select(Campaign.network_preset_id)
        .where(
            and_(
                Campaign.place_id == place_id,
                Campaign.campaign_type == campaign_type,
                Campaign.network_preset_id.isnot(None),
            )
        )
        .distinct()
    )
    used_preset_ids = [row[0] for row in used_presets_result.all()]

    # Find unused presets for this company + campaign_type
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

    result = await db.execute(query.limit(1))
    return result.scalar_one_or_none()


async def _select_account(
    db: AsyncSession,
    network_preset_id: int,
) -> SuperapAccount | None:
    """Step 3: Select account from the network preset by assignment_order."""
    result = await db.execute(
        select(SuperapAccount)
        .where(
            and_(
                SuperapAccount.network_preset_id == network_preset_id,
                SuperapAccount.is_active == True,  # noqa: E712
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
    """Apply the assignment result to the order item."""
    if result.assigned_account_id:
        order_item.assigned_account_id = result.assigned_account_id
        order_item.assignment_status = AssignmentStatus.AUTO_ASSIGNED.value
        order_item.assigned_at = datetime.now(timezone.utc)
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
    await db.flush()
    await db.refresh(order_item)
    return order_item


async def get_assignment_queue(
    db: AsyncSession,
    company_id: int | None = None,
    assignment_status: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[OrderItem]:
    """Get order items pending assignment or awaiting confirmation."""
    from app.models.order import Order

    query = (
        select(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .where(
            OrderItem.assignment_status.in_([
                AssignmentStatus.PENDING.value,
                AssignmentStatus.AUTO_ASSIGNED.value,
            ])
        )
    )

    if company_id is not None:
        query = query.where(Order.company_id == company_id)
    if assignment_status:
        query = query.where(OrderItem.assignment_status == assignment_status)

    query = query.order_by(OrderItem.created_at.asc()).offset(skip).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().unique().all())


async def get_place_network_history(
    db: AsyncSession,
    place_id: int,
    limit: int = 100,
) -> list[Campaign]:
    """Get network usage history for a place (all campaign types).

    Limited to prevent unbounded result sets.
    """
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

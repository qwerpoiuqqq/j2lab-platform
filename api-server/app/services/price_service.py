"""Price service: price determination logic with tiered priority.

Priority:
1. User-specific price (user_id match, within effective date range)
2. Role-specific price (role match, within effective date range)
3. Product base price (product.base_price)
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.price_policy import PricePolicy
from app.models.product import Product
from app.schemas.price_policy import PricePolicyCreate, PricePolicyUpdate


async def get_effective_price(
    db: AsyncSession,
    product: Product,
    user_id: uuid.UUID | None,
    user_role: str,
    campaign_type: str | None = None,
    as_of: date | None = None,
) -> int:
    """Determine the effective unit price for a user on a product.

    Priority:
    1. User-specific price policy
    2. Role-specific price policy
    3. Product base price

    Returns the resolved unit price.
    """
    if as_of is None:
        as_of = date.today()

    # 1. User-specific price (skip if no user_id)
    if user_id is not None:
        if campaign_type is not None:
            result = await db.execute(
                select(PricePolicy)
                .where(
                    PricePolicy.product_id == product.id,
                    PricePolicy.user_id == user_id,
                    PricePolicy.campaign_type == campaign_type,
                    PricePolicy.effective_from <= as_of,
                    (PricePolicy.effective_to.is_(None)) | (PricePolicy.effective_to >= as_of),
                )
                .order_by(PricePolicy.created_at.desc())
                .limit(1)
            )
            user_policy = result.scalar_one_or_none()
            if user_policy is not None:
                return int(user_policy.unit_price)

        result = await db.execute(
            select(PricePolicy)
            .where(
                PricePolicy.product_id == product.id,
                PricePolicy.user_id == user_id,
                PricePolicy.campaign_type.is_(None),
                PricePolicy.effective_from <= as_of,
                (PricePolicy.effective_to.is_(None)) | (PricePolicy.effective_to >= as_of),
            )
            .order_by(PricePolicy.created_at.desc())
            .limit(1)
        )
        user_policy = result.scalar_one_or_none()
        if user_policy is not None:
            return int(user_policy.unit_price)

    # 2. Role-specific price
    if campaign_type is not None:
        result = await db.execute(
            select(PricePolicy)
            .where(
                PricePolicy.product_id == product.id,
                PricePolicy.user_id.is_(None),
                PricePolicy.role == user_role,
                PricePolicy.campaign_type == campaign_type,
                PricePolicy.effective_from <= as_of,
                (PricePolicy.effective_to.is_(None)) | (PricePolicy.effective_to >= as_of),
            )
            .order_by(PricePolicy.created_at.desc())
            .limit(1)
        )
        role_policy = result.scalar_one_or_none()
        if role_policy is not None:
            return int(role_policy.unit_price)

    result = await db.execute(
        select(PricePolicy)
        .where(
            PricePolicy.product_id == product.id,
            PricePolicy.user_id.is_(None),
            PricePolicy.role == user_role,
            PricePolicy.campaign_type.is_(None),
            PricePolicy.effective_from <= as_of,
            (PricePolicy.effective_to.is_(None)) | (PricePolicy.effective_to >= as_of),
        )
        .order_by(PricePolicy.created_at.desc())
        .limit(1)
    )
    role_policy = result.scalar_one_or_none()
    if role_policy is not None:
        return int(role_policy.unit_price)

    # 3. Product base price
    if product.base_price is not None:
        return int(product.base_price)

    raise ValueError(f"상품 '{product.name}'에 가격이 설정되지 않았습니다.")


def apply_reduction(unit_price: int, quantity: int, product: Product) -> int:
    """Apply volume reduction rate to subtotal.

    Returns the reduced subtotal.
    """
    subtotal = unit_price * quantity
    if product.reduction_rate and product.reduction_rate > 0 and quantity > 1:
        discount = subtotal * product.reduction_rate / 100
        return int(subtotal - discount)
    return subtotal


async def get_price_policies(
    db: AsyncSession,
    product_id: int | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[PricePolicy], int]:
    """Get paginated list of price policies."""
    from sqlalchemy import func as sqlfunc

    query = select(PricePolicy)
    count_query = select(sqlfunc.count()).select_from(PricePolicy)

    if product_id is not None:
        query = query.where(PricePolicy.product_id == product_id)
        count_query = count_query.where(PricePolicy.product_id == product_id)

    query = query.order_by(PricePolicy.id.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    policies = list(result.scalars().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    return policies, total


async def get_price_policy_by_id(
    db: AsyncSession,
    policy_id: int,
) -> PricePolicy | None:
    """Get a single price policy by ID."""
    result = await db.execute(
        select(PricePolicy).where(PricePolicy.id == policy_id)
    )
    return result.scalar_one_or_none()


async def create_price_policy(
    db: AsyncSession,
    data: PricePolicyCreate,
) -> PricePolicy:
    """Create or update a price policy (upsert by product+user+campaign_type)."""
    # Check for existing policy with same key
    query = select(PricePolicy).where(
        PricePolicy.product_id == data.product_id,
    )
    if data.user_id:
        query = query.where(PricePolicy.user_id == data.user_id)
    else:
        query = query.where(PricePolicy.user_id.is_(None))
    if data.campaign_type:
        query = query.where(PricePolicy.campaign_type == data.campaign_type)
    else:
        query = query.where(PricePolicy.campaign_type.is_(None))
    if data.role and not data.user_id:
        query = query.where(PricePolicy.role == data.role)

    result = await db.execute(query.order_by(PricePolicy.created_at.desc()).limit(1))
    existing = result.scalar_one_or_none()

    if existing:
        existing.unit_price = data.unit_price
        existing.effective_from = data.effective_from
        existing.effective_to = data.effective_to
        await db.flush()
        await db.refresh(existing)
        return existing

    policy = PricePolicy(
        product_id=data.product_id,
        user_id=data.user_id,
        role=data.role,
        campaign_type=data.campaign_type,
        unit_price=data.unit_price,
        effective_from=data.effective_from,
        effective_to=data.effective_to,
    )
    db.add(policy)
    await db.flush()
    await db.refresh(policy)
    return policy


async def update_price_policy(
    db: AsyncSession,
    policy: PricePolicy,
    data: PricePolicyUpdate,
) -> PricePolicy:
    """Update an existing price policy."""
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(policy, key, value)
    await db.flush()
    await db.refresh(policy)
    return policy


async def delete_price_policy(
    db: AsyncSession,
    policy: PricePolicy,
) -> None:
    """Delete a price policy."""
    await db.delete(policy)
    await db.flush()

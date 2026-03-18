"""Superap account service: CRUD with AES encryption."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign
from app.models.company import Company
from app.models.superap_account import SuperapAccount
from app.schemas.superap_account import SuperapAccountCreate, SuperapAccountUpdate
from app.utils.crypto import encrypt_password


def resolve_unit_cost(account: SuperapAccount, campaign_type: str = "traffic") -> int:
    """Return the appropriate unit cost from an account based on campaign_type."""
    if campaign_type == "save":
        return account.unit_cost_save
    return account.unit_cost_traffic


async def get_accounts(
    db: AsyncSession,
    company_id: int | None = None,
    network_preset_id: int | None = None,
    is_active: bool | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[dict], int]:
    """Get paginated list of superap accounts with campaign_count."""
    # Subquery for campaign count per account
    campaign_count_sq = (
        select(func.count())
        .where(Campaign.superap_account_id == SuperapAccount.id)
        .correlate(SuperapAccount)
        .scalar_subquery()
        .label("campaign_count")
    )

    query = (
        select(SuperapAccount, campaign_count_sq, Company.name.label("company_name"))
        .outerjoin(Company, SuperapAccount.company_id == Company.id)
    )
    count_query = select(func.count()).select_from(SuperapAccount)

    if company_id is not None:
        query = query.where(SuperapAccount.company_id == company_id)
        count_query = count_query.where(SuperapAccount.company_id == company_id)
    if network_preset_id is not None:
        query = query.where(
            SuperapAccount.network_preset_id == network_preset_id
        )
        count_query = count_query.where(
            SuperapAccount.network_preset_id == network_preset_id
        )
    if is_active is not None:
        query = query.where(SuperapAccount.is_active == is_active)
        count_query = count_query.where(SuperapAccount.is_active == is_active)

    query = query.order_by(
        SuperapAccount.assignment_order, SuperapAccount.id
    ).offset(skip).limit(limit)

    result = await db.execute(query)
    rows = result.all()

    # Build dicts with campaign_count attached
    accounts = []
    for row in rows:
        account = row[0]
        campaign_count = row[1] or 0
        company_name = row[2]
        # Create a dict-like object that from_attributes can read
        account.campaign_count = campaign_count  # type: ignore[attr-defined]
        account.company_name = company_name  # type: ignore[attr-defined]
        accounts.append(account)

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    return accounts, total


async def get_account_by_id(
    db: AsyncSession, account_id: int
) -> SuperapAccount | None:
    """Get a single account by ID."""
    result = await db.execute(
        select(SuperapAccount).where(SuperapAccount.id == account_id)
    )
    return result.scalar_one_or_none()


async def get_account_by_login_id(
    db: AsyncSession, user_id_superap: str
) -> SuperapAccount | None:
    """Get an account by superap login ID."""
    result = await db.execute(
        select(SuperapAccount).where(
            SuperapAccount.user_id_superap == user_id_superap
        )
    )
    return result.scalar_one_or_none()


async def create_account(
    db: AsyncSession, data: SuperapAccountCreate
) -> SuperapAccount:
    """Create a new superap account with encrypted password."""
    account = SuperapAccount(
        user_id_superap=data.user_id_superap,
        password_encrypted=encrypt_password(data.password),
        company_id=data.company_id,
        network_preset_id=data.network_preset_id,
        unit_cost_traffic=data.unit_cost_traffic,
        unit_cost_save=data.unit_cost_save,
        assignment_order=data.assignment_order,
        is_active=data.is_active,
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)
    return account


async def update_account(
    db: AsyncSession, account: SuperapAccount, data: SuperapAccountUpdate
) -> SuperapAccount:
    """Update an existing superap account."""
    update_data = data.model_dump(exclude_unset=True)

    # Handle password separately (needs encryption)
    if "password" in update_data:
        password = update_data.pop("password")
        if password is not None:
            account.password_encrypted = encrypt_password(password)

    for key, value in update_data.items():
        setattr(account, key, value)

    await db.flush()
    await db.refresh(account)
    return account


async def delete_account(db: AsyncSession, account: SuperapAccount) -> None:
    """Delete a superap account. Checks for connected campaigns first."""
    result = await db.execute(
        select(func.count()).select_from(Campaign).where(
            Campaign.superap_account_id == account.id,
            Campaign.status.in_(["active", "registering", "pending_keyword_change"]),
        )
    )
    active_count = result.scalar() or 0
    if active_count > 0:
        raise ValueError(
            f"이 계정에 활성 캠페인 {active_count}개가 연결되어 있어 삭제할 수 없습니다."
        )
    await db.delete(account)
    await db.flush()

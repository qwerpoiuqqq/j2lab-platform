"""Superap account service: CRUD with AES encryption."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.superap_account import SuperapAccount
from app.schemas.superap_account import SuperapAccountCreate, SuperapAccountUpdate
from app.utils.crypto import encrypt_password


async def get_accounts(
    db: AsyncSession,
    company_id: int | None = None,
    network_preset_id: int | None = None,
    is_active: bool | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[SuperapAccount], int]:
    """Get paginated list of superap accounts."""
    query = select(SuperapAccount)
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
    accounts = list(result.scalars().all())

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
        agency_name=data.agency_name,
        company_id=data.company_id,
        network_preset_id=data.network_preset_id,
        unit_cost=data.unit_cost,
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
    """Delete a superap account."""
    await db.delete(account)
    await db.flush()

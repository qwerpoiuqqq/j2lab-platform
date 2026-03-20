"""Balance service: ledger operations with concurrency safety.

Uses SELECT FOR UPDATE to prevent race conditions on user balance.
balance_transactions is the source of truth; users.balance is a cache.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import CompileError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.balance_transaction import BalanceTransaction, TransactionType
from app.models.user import User, UserRole


async def get_balance(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> int:
    """Get the current balance for a user."""
    result = await db.execute(
        select(User.balance).where(User.id == user_id)
    )
    balance = result.scalar_one_or_none()
    if balance is None:
        return 0
    return int(balance)


async def get_effective_balance_owner(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> User:
    """Resolve the actual balance owner for a requesting user."""
    user = await _lock_user_balance(db, user_id)
    if user.role == UserRole.SUB_ACCOUNT.value and user.parent_id is not None:
        parent = await _lock_user_balance(db, user.parent_id)
        return parent
    return user


async def ensure_sufficient_order_balance(
    db: AsyncSession,
    user_id: uuid.UUID,
    amount: int,
) -> User:
    """Ensure the effective balance owner has enough balance for the order."""
    owner = await get_effective_balance_owner(db, user_id)
    current_balance = int(owner.balance) if owner.balance else 0
    if current_balance < amount:
        raise ValueError(
            f"Insufficient balance for order: current={current_balance}, required={amount}"
        )
    return owner


async def get_transactions(
    db: AsyncSession,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[BalanceTransaction], int]:
    """Get paginated list of balance transactions for a user."""
    query = (
        select(BalanceTransaction)
        .where(BalanceTransaction.user_id == user_id)
        .order_by(BalanceTransaction.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    count_query = (
        select(func.count())
        .select_from(BalanceTransaction)
        .where(BalanceTransaction.user_id == user_id)
    )

    result = await db.execute(query)
    transactions = list(result.scalars().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    return transactions, total


async def _lock_user_balance(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> User:
    """Lock user row for balance update (SELECT FOR UPDATE).

    For SQLite (tests), we skip the FOR UPDATE since SQLite doesn't support it.
    """
    try:
        # Try with FOR UPDATE (PostgreSQL)
        result = await db.execute(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
        )
    except (CompileError, OperationalError, NotImplementedError):
        # Fallback for SQLite (which doesn't support FOR UPDATE)
        result = await db.execute(
            select(User).where(User.id == user_id)
        )

    user = result.scalar_one_or_none()
    if user is None:
        raise ValueError(f"User {user_id} not found")
    return user


async def deposit(
    db: AsyncSession,
    user_id: uuid.UUID,
    amount: int,
    description: str | None = None,
    created_by: uuid.UUID | None = None,
) -> BalanceTransaction:
    """Deposit (charge) balance for a user.

    Concurrency-safe using SELECT FOR UPDATE.
    """
    if amount <= 0:
        raise ValueError("Deposit amount must be positive")

    user = await _lock_user_balance(db, user_id)
    current_balance = int(user.balance) if user.balance else 0
    new_balance = current_balance + amount

    # Update user balance cache
    user.balance = new_balance
    await db.flush()

    # Create transaction record
    tx = BalanceTransaction(
        user_id=user_id,
        amount=amount,
        balance_after=new_balance,
        transaction_type=TransactionType.DEPOSIT.value,
        description=description or "Balance deposit",
        created_by=created_by,
    )
    db.add(tx)
    await db.flush()
    await db.refresh(tx)
    return tx


async def withdraw(
    db: AsyncSession,
    user_id: uuid.UUID,
    amount: int,
    description: str | None = None,
    created_by: uuid.UUID | None = None,
) -> BalanceTransaction:
    """Withdraw (deduct) balance from a user.

    Concurrency-safe using SELECT FOR UPDATE.
    """
    if amount <= 0:
        raise ValueError("Withdrawal amount must be positive")

    user = await _lock_user_balance(db, user_id)
    current_balance = int(user.balance) if user.balance else 0

    if current_balance < amount:
        raise ValueError(
            f"Insufficient balance: current={current_balance}, requested={amount}"
        )

    new_balance = current_balance - amount

    # Update user balance cache
    user.balance = new_balance
    await db.flush()

    # Create transaction record
    tx = BalanceTransaction(
        user_id=user_id,
        amount=-amount,
        balance_after=new_balance,
        transaction_type=TransactionType.WITHDRAWAL.value,
        description=description or "Balance withdrawal",
        created_by=created_by,
    )
    db.add(tx)
    await db.flush()
    await db.refresh(tx)
    return tx


async def charge_for_order(
    db: AsyncSession,
    user_id: uuid.UUID,
    order_id: int,
    amount: int,
    created_by: uuid.UUID | None = None,
) -> BalanceTransaction:
    """Deduct balance for an order payment.

    Concurrency-safe using SELECT FOR UPDATE.
    """
    if amount <= 0:
        raise ValueError("Charge amount must be positive")

    user = await ensure_sufficient_order_balance(db, user_id, amount)
    current_balance = int(user.balance) if user.balance else 0

    new_balance = current_balance - amount

    # Update user balance cache
    user.balance = new_balance
    await db.flush()

    # Create transaction record
    tx = BalanceTransaction(
        user_id=user_id,
        order_id=order_id,
        amount=-amount,
        balance_after=new_balance,
        transaction_type=TransactionType.ORDER_CHARGE.value,
        description=f"Order #{order_id} payment",
        created_by=created_by,
    )
    db.add(tx)
    await db.flush()
    await db.refresh(tx)
    return tx


async def refund_for_order(
    db: AsyncSession,
    user_id: uuid.UUID,
    order_id: int,
    amount: int,
    created_by: uuid.UUID | None = None,
) -> BalanceTransaction:
    """Refund balance for a cancelled order.

    Concurrency-safe using SELECT FOR UPDATE.
    """
    if amount <= 0:
        raise ValueError("Refund amount must be positive")

    user = await _lock_user_balance(db, user_id)
    current_balance = int(user.balance) if user.balance else 0
    new_balance = current_balance + amount

    # Update user balance cache
    user.balance = new_balance
    await db.flush()

    # Create transaction record
    tx = BalanceTransaction(
        user_id=user_id,
        order_id=order_id,
        amount=amount,
        balance_after=new_balance,
        transaction_type=TransactionType.REFUND.value,
        description=f"Order #{order_id} refund",
        created_by=created_by,
    )
    db.add(tx)
    await db.flush()
    await db.refresh(tx)
    return tx

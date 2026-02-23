"""Order service: CRUD + state machine transitions for orders.

State machine:
  draft -> submitted (distributor confirms sub_account order)
  submitted -> payment_confirmed (company_admin confirms payment)
  submitted -> rejected (company_admin rejects)
  payment_confirmed -> processing (auto, pipeline starts)
  draft, submitted -> cancelled
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import (
    Order,
    OrderItem,
    OrderStatus,
    PaymentStatus,
    VALID_ORDER_TRANSITIONS,
)
from app.models.product import Product
from app.models.user import User, UserRole
from app.schemas.order import OrderCreate, OrderItemCreate
from app.services import balance_service, price_service


def _generate_order_number() -> str:
    """Generate a unique order number: ORD-YYYYMMDD-XXXX (random suffix)."""
    import secrets

    today = date.today().strftime("%Y%m%d")
    suffix = secrets.token_hex(2).upper()  # 4-char hex
    return f"ORD-{today}-{suffix}"


def _can_transition(current: OrderStatus, target: OrderStatus) -> bool:
    """Check if the status transition is valid."""
    return target in VALID_ORDER_TRANSITIONS.get(current, [])


async def get_orders(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    status: str | None = None,
    current_user: User | None = None,
) -> tuple[list[Order], int]:
    """Get paginated list of orders with role-based filtering.

    - system_admin: sees all orders
    - company_admin, order_handler: sees orders in the same company
    - distributor: sees own + sub_account orders
    - sub_account: sees only own orders
    """
    query = select(Order)
    count_query = select(func.count()).select_from(Order)

    # Role-based scope
    if current_user:
        user_role = UserRole(current_user.role)
        if user_role in (UserRole.COMPANY_ADMIN, UserRole.ORDER_HANDLER):
            query = query.where(Order.company_id == current_user.company_id)
            count_query = count_query.where(
                Order.company_id == current_user.company_id
            )
        elif user_role == UserRole.DISTRIBUTOR:
            # distributor sees own orders + sub_account orders
            sub_query = select(User.id).where(User.parent_id == current_user.id)
            query = query.where(
                (Order.user_id == current_user.id) | Order.user_id.in_(sub_query)
            )
            count_query = count_query.where(
                (Order.user_id == current_user.id) | Order.user_id.in_(sub_query)
            )
        elif user_role == UserRole.SUB_ACCOUNT:
            query = query.where(Order.user_id == current_user.id)
            count_query = count_query.where(Order.user_id == current_user.id)
        # system_admin: no filtering

    if status is not None:
        query = query.where(Order.status == status)
        count_query = count_query.where(Order.status == status)

    query = query.order_by(Order.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    orders = list(result.scalars().unique().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    return orders, total


async def get_order_by_id(
    db: AsyncSession,
    order_id: int,
) -> Order | None:
    """Get a single order by ID with items loaded."""
    result = await db.execute(
        select(Order).where(Order.id == order_id)
    )
    return result.scalar_one_or_none()


def can_view_order(viewer: User, order: Order) -> bool:
    """Check if viewer has permission to view an order.

    - system_admin: can view any
    - company_admin, order_handler: same company
    - distributor: own + sub_account orders
    - sub_account: own orders only
    """
    viewer_role = UserRole(viewer.role)

    if viewer_role == UserRole.SYSTEM_ADMIN:
        return True
    if viewer_role in (UserRole.COMPANY_ADMIN, UserRole.ORDER_HANDLER):
        return viewer.company_id == order.company_id
    if viewer_role == UserRole.DISTRIBUTOR:
        return order.user_id == viewer.id or (
            hasattr(order, "user") and order.user and order.user.parent_id == viewer.id
        )
    if viewer_role == UserRole.SUB_ACCOUNT:
        return order.user_id == viewer.id
    return False


async def create_order(
    db: AsyncSession,
    data: OrderCreate,
    current_user: User,
) -> Order:
    """Create a new order with items.

    Resolves prices for each item using the price service.
    """
    order = Order(
        order_number=_generate_order_number(),
        user_id=current_user.id,
        company_id=current_user.company_id,
        status=OrderStatus.DRAFT.value,
        payment_status=PaymentStatus.UNPAID.value,
        notes=data.notes,
        source=data.source,
    )
    db.add(order)
    await db.flush()

    total_amount = 0

    for idx, item_data in enumerate(data.items, start=1):
        # Resolve product
        product_result = await db.execute(
            select(Product).where(Product.id == item_data.product_id)
        )
        product = product_result.scalar_one_or_none()
        if product is None:
            raise ValueError(f"Product with id {item_data.product_id} not found")
        if not product.is_active:
            raise ValueError(f"Product '{product.name}' is not active")

        # Resolve price
        unit_price = await price_service.get_effective_price(
            db,
            product=product,
            user_id=current_user.id,
            user_role=current_user.role,
        )
        subtotal = unit_price * item_data.quantity

        order_item = OrderItem(
            order_id=order.id,
            product_id=item_data.product_id,
            row_number=idx,
            quantity=item_data.quantity,
            unit_price=unit_price,
            subtotal=subtotal,
            item_data=item_data.item_data,
        )
        db.add(order_item)
        total_amount += subtotal

    # Calculate VAT (10%)
    vat_amount = int(total_amount * 0.1)
    order.total_amount = total_amount
    order.vat_amount = vat_amount

    await db.flush()
    await db.refresh(order)
    return order


async def update_order(
    db: AsyncSession,
    order: Order,
    notes: str | None = None,
) -> Order:
    """Update an order (only while in draft status)."""
    if order.status != OrderStatus.DRAFT.value:
        raise ValueError("Can only update orders in draft status")

    if notes is not None:
        order.notes = notes

    await db.flush()
    await db.refresh(order)
    return order


async def submit_order(
    db: AsyncSession,
    order: Order,
    submitted_by: User,
) -> Order:
    """Submit an order: draft -> submitted.

    Typically done by the distributor confirming a sub_account's order.
    """
    current_status = OrderStatus(order.status)
    if not _can_transition(current_status, OrderStatus.SUBMITTED):
        raise ValueError(
            f"Cannot submit order in '{order.status}' status. "
            "Only draft orders can be submitted."
        )

    order.status = OrderStatus.SUBMITTED.value
    order.submitted_by = submitted_by.id
    order.submitted_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(order)
    return order


async def confirm_payment(
    db: AsyncSession,
    order: Order,
    confirmed_by: User,
) -> Order:
    """Confirm payment: submitted -> payment_confirmed.

    Deducts balance from the order's user.
    """
    current_status = OrderStatus(order.status)
    if not _can_transition(current_status, OrderStatus.PAYMENT_CONFIRMED):
        raise ValueError(
            f"Cannot confirm payment for order in '{order.status}' status. "
            "Only submitted orders can have payment confirmed."
        )

    total = int(order.total_amount) if order.total_amount else 0

    # Deduct balance from the order's user
    if total > 0:
        await balance_service.charge_for_order(
            db,
            user_id=order.user_id,
            order_id=order.id,
            amount=total,
            created_by=confirmed_by.id,
        )

    order.status = OrderStatus.PAYMENT_CONFIRMED.value
    order.payment_status = PaymentStatus.CONFIRMED.value
    order.payment_confirmed_by = confirmed_by.id
    order.payment_confirmed_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(order)
    return order


async def reject_order(
    db: AsyncSession,
    order: Order,
    reason: str,
) -> Order:
    """Reject an order: submitted -> rejected."""
    current_status = OrderStatus(order.status)
    if not _can_transition(current_status, OrderStatus.REJECTED):
        raise ValueError(
            f"Cannot reject order in '{order.status}' status. "
            "Only submitted orders can be rejected."
        )

    order.status = OrderStatus.REJECTED.value
    order.notes = (order.notes or "") + f"\n[Reject reason]: {reason}"

    await db.flush()
    await db.refresh(order)
    return order


async def cancel_order(
    db: AsyncSession,
    order: Order,
    cancelled_by: User,
) -> Order:
    """Cancel an order: draft/submitted -> cancelled.

    If payment was confirmed, refund the balance.
    """
    current_status = OrderStatus(order.status)
    if not _can_transition(current_status, OrderStatus.CANCELLED):
        raise ValueError(
            f"Cannot cancel order in '{order.status}' status. "
            "Only draft or submitted orders can be cancelled."
        )

    # If payment was already confirmed (edge case: should not happen per flow),
    # refund. In normal flow, cancel is only allowed for draft/submitted.
    order.status = OrderStatus.CANCELLED.value

    await db.flush()
    await db.refresh(order)
    return order

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


def validate_item_data(product: Product, item_data: dict | None) -> list[str]:
    """Validate item_data against product.form_schema.
    Returns list of error messages (empty = valid).
    """
    import re

    errors = []
    schema = product.form_schema
    if not schema or not isinstance(schema, list):
        return errors

    data = item_data or {}

    for field in schema:
        if not isinstance(field, dict):
            continue
        name = field.get("name", "")
        field_type = field.get("type", "text")
        required = field.get("required", False)
        value = data.get(name)

        if required and (value is None or str(value).strip() == ""):
            errors.append(f"필드 '{name}'은(는) 필수입니다.")
            continue

        if value is None or str(value).strip() == "":
            continue

        if field_type == "url":
            val_str = str(value)
            if not (val_str.startswith("http://") or val_str.startswith("https://")):
                errors.append(f"필드 '{name}': 유효한 URL이 아닙니다.")
        elif field_type == "number":
            try:
                float(value)
            except (ValueError, TypeError):
                errors.append(f"필드 '{name}': 숫자를 입력해야 합니다.")
        elif field_type == "date":
            val_str = str(value)
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", val_str):
                errors.append(f"필드 '{name}': 날짜 형식(YYYY-MM-DD)이어야 합니다.")

    return errors


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
    search: str | None = None,
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

    if search:
        search_pattern = f"%{search}%"
        search_filter = (
            Order.order_number.ilike(search_pattern)
            | Order.user.has(User.name.ilike(search_pattern))
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

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
    from app.core.config import settings
    if len(data.items) > settings.ORDER_MAX_ITEMS:
        raise ValueError(f"최대 {settings.ORDER_MAX_ITEMS}건까지 접수 가능합니다.")

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

        # Validate item_data against form_schema
        validation_errors = validate_item_data(product, item_data.item_data)
        if validation_errors:
            raise ValueError(
                f"Item {idx} validation failed: {'; '.join(validation_errors)}"
            )

        # Resolve price
        unit_price = await price_service.get_effective_price(
            db,
            product=product,
            user_id=current_user.id,
            user_role=current_user.role,
        )
        subtotal = price_service.apply_reduction(unit_price, item_data.quantity, product)

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

    # Auto-calculate deadline from product's max_work_days
    if data.items:
        first_product_id = data.items[0].product_id
        prod_result = await db.execute(
            select(Product).where(Product.id == first_product_id)
        )
        prod = prod_result.scalar_one_or_none()
        if prod and prod.max_work_days:
            from datetime import timedelta
            order.completed_at = datetime.now(timezone.utc) + timedelta(days=prod.max_work_days)

    await db.flush()
    await db.refresh(order)
    return order


async def create_order_from_excel(
    db: AsyncSession,
    product_id: int,
    rows: list[dict],
    current_user: User,
    notes: str | None = None,
) -> Order:
    """Create an order from validated Excel rows."""
    from app.core.config import settings
    if len(rows) > settings.ORDER_MAX_ITEMS:
        raise ValueError(f"최대 {settings.ORDER_MAX_ITEMS}건까지 접수 가능합니다.")

    product_result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    product = product_result.scalar_one_or_none()
    if product is None:
        raise ValueError(f"Product {product_id} not found")
    if not product.is_active:
        raise ValueError(f"Product '{product.name}' is not active")

    order = Order(
        order_number=_generate_order_number(),
        user_id=current_user.id,
        company_id=current_user.company_id,
        status=OrderStatus.DRAFT.value,
        payment_status=PaymentStatus.UNPAID.value,
        notes=notes,
        source="excel",
    )
    db.add(order)
    await db.flush()

    total_amount = 0
    for idx, row_data in enumerate(rows, start=1):
        try:
            quantity = max(1, int(float(row_data.get("quantity", 1) or 1)))
        except (ValueError, TypeError):
            quantity = 1
        unit_price = await price_service.get_effective_price(
            db, product=product, user_id=current_user.id, user_role=current_user.role,
        )
        subtotal = price_service.apply_reduction(unit_price, quantity, product)
        order_item = OrderItem(
            order_id=order.id,
            product_id=product_id,
            row_number=idx,
            quantity=quantity,
            unit_price=unit_price,
            subtotal=subtotal,
            item_data=row_data,
        )
        db.add(order_item)
        total_amount += subtotal

    vat_amount = int(total_amount * 0.1)
    order.total_amount = total_amount
    order.vat_amount = vat_amount

    if product.max_work_days:
        from datetime import timedelta
        order.completed_at = datetime.now(timezone.utc) + timedelta(days=product.max_work_days)

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


async def transition_order_status(
    db: AsyncSession,
    order: Order,
    target_status_str: str,
    actor: User,
) -> Order:
    """Generic status transition for bulk operations."""
    try:
        target = OrderStatus(target_status_str)
    except ValueError:
        raise ValueError(f"Invalid status: {target_status_str}")

    current = OrderStatus(order.status)
    if not _can_transition(current, target):
        raise ValueError(
            f"Cannot transition from '{order.status}' to '{target_status_str}'"
        )

    order.status = target.value
    await db.flush()
    await db.refresh(order)
    return order


async def update_deadline(
    db: AsyncSession,
    order: Order,
    deadline: datetime,
) -> Order:
    """Update the completed_at (deadline) field on an order."""
    order.completed_at = deadline
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

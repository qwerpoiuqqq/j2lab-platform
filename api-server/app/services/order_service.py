"""Order service: CRUD + state machine transitions for orders.

State machine:
  draft -> submitted (distributor confirms sub_account order)
  submitted -> payment_confirmed (company_admin confirms payment)
  submitted -> payment_hold (company_admin holds for review)
  submitted -> rejected (company_admin rejects)
  payment_hold -> submitted (company_admin releases hold)
  payment_hold -> payment_confirmed (company_admin confirms after hold)
  payment_confirmed -> processing (auto, pipeline starts)
  draft, submitted -> cancelled
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import (
    AssignmentStatus,
    Order,
    OrderItem,
    OrderStatus,
    OrderType,
    PaymentStatus,
    VALID_ORDER_TRANSITIONS,
)
from app.models.product import Product
from app.models.user import User, UserRole
from app.schemas.order import OrderCreate, OrderItemCreate, SimplifiedOrderCreate
from app.services import price_service, superap_account_service


def validate_item_data(product: Product, item_data: dict | None) -> list[str]:
    """Validate item_data against product.form_schema.
    Returns list of error messages (empty = valid).
    Supports both old format ({fields: [{key, ...}]}) and new format ([{name, ...}]).
    """
    import re

    errors = []
    schema = product.form_schema
    if not schema:
        return errors

    # Normalize schema: old format {fields: [...]} → [...]
    if isinstance(schema, dict):
        schema = schema.get("fields", [])
    if not isinstance(schema, list):
        return errors

    data = item_data or {}

    for field in schema:
        if not isinstance(field, dict):
            continue
        # Support both 'name' (new) and 'key' (old) field identifiers
        name = field.get("name") or field.get("key", "")
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

    # Constraints validation against product limits
    data = item_data or {}

    daily_limit = data.get("daily_limit")
    duration_days = data.get("duration_days")

    if daily_limit is not None and product.min_daily_limit is not None:
        try:
            if int(daily_limit) < product.min_daily_limit:
                errors.append(
                    f"일 작업량은 최소 {product.min_daily_limit} 이상이어야 합니다"
                )
        except (ValueError, TypeError):
            pass

    if duration_days is not None and product.min_work_days is not None:
        try:
            if int(duration_days) < product.min_work_days:
                errors.append(
                    f"작업 기간은 최소 {product.min_work_days}일 이상이어야 합니다"
                )
        except (ValueError, TypeError):
            pass

    if duration_days is not None and product.max_work_days is not None:
        try:
            if int(duration_days) > product.max_work_days:
                errors.append(
                    f"작업 기간은 최대 {product.max_work_days}일 이하여야 합니다"
                )
        except (ValueError, TypeError):
            pass

    return errors


async def _generate_order_number(db: AsyncSession) -> str:
    """Generate a sequential order number: ORD-YYYYMMDD-NNN."""
    today_str = date.today().strftime("%Y%m%d")
    prefix = f"ORD-{today_str}-"

    # 오늘 날짜의 마지막 주문번호 조회
    result = await db.execute(
        select(func.max(Order.order_number)).where(
            Order.order_number.like(f"{prefix}%")
        )
    )
    last_number = result.scalar_one_or_none()

    if last_number:
        try:
            last_seq = int(last_number.split("-")[-1])
            next_seq = last_seq + 1
        except (ValueError, IndexError):
            next_seq = 1
    else:
        next_seq = 1

    return f"{prefix}{next_seq:03d}"


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
    order_type: str | None = None,
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
        if user_role == UserRole.COMPANY_ADMIN:
            query = query.where(Order.company_id == current_user.company_id)
            count_query = count_query.where(
                Order.company_id == current_user.company_id
            )
        elif user_role == UserRole.ORDER_HANDLER:
            from app.services.user_service import get_line_user_ids
            line_ids = await get_line_user_ids(db, current_user.id)
            query = query.where(Order.user_id.in_(line_ids))
            count_query = count_query.where(Order.user_id.in_(line_ids))
        elif user_role == UserRole.DISTRIBUTOR:
            # distributor sees own orders (all statuses)
            # + sub_account orders (submitted 이상만 — draft는 제출 전이므로 숨김)
            sub_query = select(User.id).where(User.parent_id == current_user.id)
            query = query.where(
                (Order.user_id == current_user.id)
                | (
                    Order.user_id.in_(sub_query)
                    & (Order.status != OrderStatus.DRAFT.value)
                )
            )
            count_query = count_query.where(
                (Order.user_id == current_user.id)
                | (
                    Order.user_id.in_(sub_query)
                    & (Order.status != OrderStatus.DRAFT.value)
                )
            )
        elif user_role == UserRole.SUB_ACCOUNT:
            query = query.where(Order.user_id == current_user.id)
            count_query = count_query.where(Order.user_id == current_user.id)
        # system_admin: no filtering

    if status is not None:
        query = query.where(Order.status == status)
        count_query = count_query.where(Order.status == status)

    if order_type is not None:
        types = [t.strip() for t in order_type.split(",")]
        query = query.where(Order.order_type.in_(types))
        count_query = count_query.where(Order.order_type.in_(types))

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

    # Determine selection_status: sub_account orders start as pending
    user_role = UserRole(current_user.role)
    initial_selection = "pending" if user_role == UserRole.SUB_ACCOUNT else "included"

    # Determine if this is a no-revenue order type
    is_no_revenue = data.order_type in (OrderType.MONTHLY_GUARANTEE.value, OrderType.MANAGED.value)

    # Validate assigned_account_id for no-revenue orders
    assigned_account = None
    if is_no_revenue and data.assigned_account_id:
        assigned_account = await superap_account_service.get_account_by_id(db, data.assigned_account_id)
        if assigned_account is None:
            raise ValueError(f"SuperapAccount {data.assigned_account_id} not found")
        if not assigned_account.is_active:
            raise ValueError(f"SuperapAccount '{assigned_account.user_id_superap}' is not active")

    order = Order(
        order_number=await _generate_order_number(db),
        user_id=current_user.id,
        company_id=current_user.company_id,
        status=OrderStatus.DRAFT.value,
        payment_status=PaymentStatus.UNPAID.value,
        order_type=data.order_type,
        notes=data.notes,
        source=data.source,
        selection_status=initial_selection,
    )
    db.add(order)
    await db.flush()

    total_amount = 0
    product_cache: dict[int, Product] = {}

    for idx, item_data in enumerate(data.items, start=1):
        # Resolve product (with cache to avoid duplicate queries)
        if item_data.product_id not in product_cache:
            product_result = await db.execute(
                select(Product).where(Product.id == item_data.product_id)
            )
            product = product_result.scalar_one_or_none()
            if product is None:
                raise ValueError(f"Product with id {item_data.product_id} not found")
            if not product.is_active:
                raise ValueError(f"Product '{product.name}' is not active")
            product_cache[item_data.product_id] = product
        product = product_cache[item_data.product_id]

        # Validate item_data against form_schema
        validation_errors = validate_item_data(product, item_data.item_data)
        if validation_errors:
            raise ValueError(
                f"Item {idx} validation failed: {'; '.join(validation_errors)}"
            )

        # Resolve price — no-revenue types get unit_price=0
        if is_no_revenue:
            unit_price = 0
            subtotal = 0
        else:
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

        # Manual account assignment for no-revenue orders
        if is_no_revenue and assigned_account is not None:
            order_item.assigned_account_id = assigned_account.id
            order_item.assignment_status = AssignmentStatus.CONFIRMED.value
            order_item.assigned_at = datetime.now(timezone.utc)
            # Select cost based on campaign_type from item_data
            _idata = item_data.item_data if isinstance(item_data.item_data, dict) else {}
            order_item.cost_unit_price = superap_account_service.resolve_unit_cost(
                assigned_account, _idata.get("campaign_type", "traffic")
            )

        db.add(order_item)
        total_amount += subtotal

    # Calculate VAT (10%) — no-revenue types stay 0
    vat_amount = int(total_amount * 0.1)
    order.total_amount = total_amount
    order.vat_amount = vat_amount

    # Auto-calculate deadline from product's max_work_days (reuse cached product)
    if data.items:
        first_product = product_cache.get(data.items[0].product_id)
        if first_product and first_product.max_work_days:

            order.completed_at = datetime.now(timezone.utc) + timedelta(days=first_product.max_work_days)

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

    # Determine selection_status: sub_account orders start as pending
    user_role = UserRole(current_user.role)
    initial_selection = "pending" if user_role == UserRole.SUB_ACCOUNT else "included"

    order = Order(
        order_number=await _generate_order_number(db),
        user_id=current_user.id,
        company_id=current_user.company_id,
        status=OrderStatus.DRAFT.value,
        payment_status=PaymentStatus.UNPAID.value,
        notes=notes,
        source="excel",
        selection_status=initial_selection,
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
    Only included orders can be submitted.
    """
    current_status = OrderStatus(order.status)
    if not _can_transition(current_status, OrderStatus.SUBMITTED):
        raise ValueError(
            f"Cannot submit order in '{order.status}' status. "
            "Only draft orders can be submitted."
        )

    # Distributor selection check: excluded orders cannot be submitted
    if order.selection_status == "excluded":
        raise ValueError("제외된 접수건은 제출할 수 없습니다.")

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
    """Confirm payment: submitted -> payment_confirmed."""
    current_status = OrderStatus(order.status)
    if not _can_transition(current_status, OrderStatus.PAYMENT_CONFIRMED):
        raise ValueError(
            f"Cannot confirm payment for order in '{order.status}' status. "
            "Only submitted orders can have payment confirmed."
        )

    # Deduct balance for regular orders before finalizing payment confirmation.
    if order.order_type == OrderType.REGULAR.value:
        charge_amount = int(order.total_amount or 0)
        if charge_amount > 0:
            from app.services import balance_service

            await balance_service.charge_for_order(
                db,
                user_id=order.user_id,
                order_id=order.id,
                amount=charge_amount,
                created_by=confirmed_by.id,
            )

    order.status = OrderStatus.PAYMENT_CONFIRMED.value
    order.payment_status = PaymentStatus.CONFIRMED.value
    order.payment_confirmed_by = confirmed_by.id
    order.payment_confirmed_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(order)

    # Send notification (best-effort)
    try:
        from app.services import notification_service
        await notification_service.notify_payment_confirmed(db, order, confirmed_by)
    except Exception:
        pass

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
    order.reject_reason = reason
    order.notes = (order.notes or "") + f"\n[Reject reason]: {reason}"

    # Cascade: cancel all related order items (배정 대기열에서 제외)
    items_result = await db.execute(
        select(OrderItem).where(OrderItem.order_id == order.id)
    )
    for item in items_result.scalars().all():
        item.status = "cancelled"

    await db.flush()
    await db.refresh(order)

    # Send notification (best-effort)
    try:
        from app.services import notification_service
        await notification_service.notify_payment_rejected(db, order, reason)
    except Exception:
        pass

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

    # Cascade: cancel all related order items
    items_result = await db.execute(
        select(OrderItem).where(OrderItem.order_id == order.id)
    )
    for item in items_result.scalars().all():
        item.status = "cancelled"

    await db.flush()
    await db.refresh(order)
    return order


# ---- Payment hold ----


async def hold_order(
    db: AsyncSession,
    order: Order,
    reason: str,
    actor: User,
) -> Order:
    """Hold an order: submitted/payment_hold -> payment_hold.

    Sets hold_reason and tracks who checked it.
    """
    current_status = OrderStatus(order.status)
    if not _can_transition(current_status, OrderStatus.PAYMENT_HOLD):
        raise ValueError(
            f"Cannot hold order in '{order.status}' status. "
            "Only submitted or payment_hold orders can be held."
        )

    order.status = OrderStatus.PAYMENT_HOLD.value
    order.hold_reason = reason
    order.payment_checked_by = actor.id
    order.payment_checked_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(order)

    # Send notification (best-effort)
    try:
        from app.services import notification_service
        await notification_service.notify_payment_held(db, order, reason)
    except Exception:
        pass

    return order


async def release_hold(
    db: AsyncSession,
    order: Order,
    actor: User,
) -> Order:
    """Release hold: payment_hold -> submitted.

    Clears hold_reason and resets to submitted.
    """
    current_status = OrderStatus(order.status)
    if current_status != OrderStatus.PAYMENT_HOLD:
        raise ValueError(
            f"Cannot release hold for order in '{order.status}' status. "
            "Only payment_hold orders can be released."
        )

    order.status = OrderStatus.SUBMITTED.value
    order.hold_reason = None

    await db.flush()
    await db.refresh(order)
    return order


# ---- Distributor order selection ----


async def set_selection_status(
    db: AsyncSession,
    order: Order,
    status: str,  # "included" | "excluded"
    actor: User,
) -> Order:
    """Set the selection_status of an order (distributor action)."""
    if status not in ("included", "excluded"):
        raise ValueError(f"Invalid selection status: {status}")
    if order.selection_status not in ("pending", "included", "excluded"):
        raise ValueError(f"Cannot change selection_status from '{order.selection_status}'")

    order.selection_status = status
    order.selected_by = actor.id
    order.selected_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(order)
    return order


async def _find_default_product(
    db: AsyncSession,
    campaign_type: str,
) -> Product:
    """Find the default active product for a campaign type.

    Maps campaign_type to category name:
      "traffic" → "트래픽"
      "save" → "저장"
    Falls back to any active product in the matching category.
    """
    type_to_category = {
        "traffic": "트래픽",
        "save": "저장",
    }
    category_name = type_to_category.get(campaign_type)

    if category_name:
        result = await db.execute(
            select(Product).where(
                Product.category == category_name,
                Product.is_active == True,  # noqa: E712
            ).order_by(Product.id.asc()).limit(1)
        )
        product = result.scalar_one_or_none()
        if product:
            return product

    # Fallback: find by form_schema campaign_type default
    result = await db.execute(
        select(Product).where(
            Product.is_active == True,  # noqa: E712
        ).order_by(Product.id.asc())
    )
    products = list(result.scalars().all())
    for p in products:
        if p.form_schema and isinstance(p.form_schema, list):
            for field in p.form_schema:
                if isinstance(field, dict) and field.get("name") == "campaign_type":
                    if field.get("default") == campaign_type:
                        return p

    raise ValueError(
        f"'{campaign_type}' 타입에 해당하는 활성 상품을 찾을 수 없습니다."
    )


async def create_simplified_order(
    db: AsyncSession,
    data: SimplifiedOrderCreate,
    current_user: User,
) -> Order:
    """Create an order from simplified input (5 fields per item).

    Automatically matches product by campaign_type, calculates quantity,
    and builds item_data for pipeline compatibility.
    """
    from app.core.config import settings

    if len(data.items) > settings.ORDER_MAX_ITEMS:
        raise ValueError(f"최대 {settings.ORDER_MAX_ITEMS}건까지 접수 가능합니다.")

    # Determine selection_status: sub_account orders start as pending
    user_role = UserRole(current_user.role)
    initial_selection = "pending" if user_role == UserRole.SUB_ACCOUNT else "included"

    order = Order(
        order_number=await _generate_order_number(db),
        user_id=current_user.id,
        company_id=current_user.company_id,
        status=OrderStatus.DRAFT.value,
        payment_status=PaymentStatus.UNPAID.value,
        notes=data.notes,
        source=data.source,
        selection_status=initial_selection,
    )
    db.add(order)
    await db.flush()

    total_amount = 0
    product_cache: dict[str, Product] = {}

    for idx, item in enumerate(data.items, start=1):
        # Auto-match product by campaign_type
        if item.campaign_type not in product_cache:
            product_cache[item.campaign_type] = await _find_default_product(
                db, item.campaign_type
            )
        product = product_cache[item.campaign_type]

        total_limit = item.daily_limit * item.duration_days

        # Calculate end_date
        try:
            start_dt = date.fromisoformat(item.start_date)
            end_dt = start_dt + timedelta(days=item.duration_days)
            end_date = end_dt.isoformat()
        except (ValueError, TypeError):
            end_date = ""

        # Build item_data compatible with pipeline_orchestrator
        item_data = {
            "place_url": item.place_url,
            "place_name": item.place_name or "",
            "campaign_type": item.campaign_type,
            "daily_limit": item.daily_limit,
            "duration_days": item.duration_days,
            "total_limit": total_limit,
            "start_date": item.start_date,
            "end_date": end_date,
            "target_keyword": item.target_keyword,
        }

        # Resolve price
        unit_price = await price_service.get_effective_price(
            db,
            product=product,
            user_id=current_user.id,
            user_role=current_user.role,
        )
        subtotal = price_service.apply_reduction(unit_price, total_limit, product)

        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            row_number=idx,
            quantity=total_limit,
            unit_price=unit_price,
            subtotal=subtotal,
            item_data=item_data,
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


DELETABLE_STATUSES = {
    OrderStatus.DRAFT.value,
    OrderStatus.CANCELLED.value,
    OrderStatus.REJECTED.value,
}


async def delete_order(
    db: AsyncSession,
    order: Order,
    actor: User | None = None,
) -> None:
    """Delete an order permanently.

    Only orders in draft/cancelled/rejected status can be deleted.
    Cascading deletes handle order_items, pipeline_states, pipeline_logs.
    Campaign.order_item_id and ExtractionJob.order_item_id are SET NULL.
    BalanceTransaction.order_id is SET NULL.
    """
    is_system_admin = bool(actor and actor.role == UserRole.SYSTEM_ADMIN.value)

    if not is_system_admin and order.status not in DELETABLE_STATUSES:
        raise ValueError(
            f"'{order.status}' 상태의 주문은 삭제할 수 없습니다. "
            "임시저장, 취소, 반려 상태의 주문만 삭제 가능합니다."
        )

    await db.delete(order)
    await db.flush()


async def get_sub_account_pending_orders(
    db: AsyncSession,
    distributor: User,
    skip: int = 0,
    limit: int = 50,
) -> list[Order]:
    """Get pending sub-account orders for a distributor."""
    user_role = UserRole(distributor.role)

    if user_role == UserRole.SYSTEM_ADMIN:
        # system_admin sees all pending orders
        query = (
            select(Order)
            .where(Order.selection_status == "pending")
            .order_by(Order.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
    else:
        # distributor sees only sub-account orders
        sub_query = select(User.id).where(User.parent_id == distributor.id)
        query = (
            select(Order)
            .where(
                Order.user_id.in_(sub_query),
                Order.selection_status == "pending",
            )
            .order_by(Order.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

    result = await db.execute(query)
    return list(result.scalars().unique().all())

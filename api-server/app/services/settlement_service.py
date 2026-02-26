"""Settlement service: revenue/profit analysis from orders + order_items."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product
from app.models.user import User
from app.schemas.settlement import SettlementRow, SettlementSummary


async def get_settlement_data(
    db: AsyncSession,
    date_from: date | None = None,
    date_to: date | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[SettlementRow], SettlementSummary, int]:
    """Get settlement data from completed/payment_confirmed orders.

    Calculates profit = unit_price * quantity - base_price * quantity per item.
    Returns (rows, summary, total_count).
    """
    # Base filter: only confirmed/completed/processing orders
    settled_statuses = [
        OrderStatus.PAYMENT_CONFIRMED.value,
        OrderStatus.PROCESSING.value,
        OrderStatus.COMPLETED.value,
    ]

    base_filter = Order.status.in_(settled_statuses)
    filters = [base_filter]

    if date_from is not None:
        filters.append(Order.created_at >= date_from)
    if date_to is not None:
        from datetime import datetime, time, timezone
        end_of_day = datetime.combine(date_to, time.max, tzinfo=timezone.utc)
        filters.append(Order.created_at <= end_of_day)

    # Count total items
    count_stmt = (
        select(func.count())
        .select_from(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .where(*filters)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    # Fetch items with joins
    stmt = (
        select(OrderItem, Order, Product, User)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Product, OrderItem.product_id == Product.id)
        .join(User, Order.user_id == User.id)
        .where(*filters)
        .order_by(Order.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows_raw = result.all()

    rows: list[SettlementRow] = []
    for item, order, product, user in rows_raw:
        unit_price = int(item.unit_price) if item.unit_price else 0
        base_price = int(product.base_price) if product.base_price else 0
        quantity = item.quantity or 1
        subtotal = unit_price * quantity
        cost = base_price * quantity
        profit = subtotal - cost
        margin_pct = round((profit / subtotal * 100) if subtotal > 0 else 0.0, 2)

        rows.append(SettlementRow(
            order_id=order.id,
            order_number=order.order_number,
            product_name=product.name,
            user_name=user.name,
            user_role=user.role,
            quantity=quantity,
            unit_price=unit_price,
            base_price=base_price,
            subtotal=subtotal,
            cost=cost,
            profit=profit,
            margin_pct=margin_pct,
            created_at=order.created_at,
        ))

    # Summary: compute over ALL matching items (not just the page)
    summary = await _compute_summary(db, filters)

    return rows, summary, total


async def _compute_summary(
    db: AsyncSession,
    filters: list,
) -> SettlementSummary:
    """Compute aggregated summary stats over filtered settlement data."""
    stmt = (
        select(
            func.count(OrderItem.id).label("item_count"),
            func.count(func.distinct(Order.id)).label("order_count"),
            func.coalesce(func.sum(OrderItem.subtotal), 0).label("total_revenue"),
        )
        .select_from(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .where(*filters)
    )
    result = (await db.execute(stmt)).one()
    item_count = result.item_count
    order_count = result.order_count
    total_revenue = int(result.total_revenue)

    # Cost calculation requires base_price from product
    cost_stmt = (
        select(
            func.coalesce(
                func.sum(Product.base_price * OrderItem.quantity), 0
            ).label("total_cost"),
        )
        .select_from(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Product, OrderItem.product_id == Product.id)
        .where(*filters)
    )
    cost_result = (await db.execute(cost_stmt)).one()
    total_cost = int(cost_result.total_cost)

    total_profit = total_revenue - total_cost
    avg_margin = round((total_profit / total_revenue * 100) if total_revenue > 0 else 0.0, 2)

    return SettlementSummary(
        total_revenue=total_revenue,
        total_cost=total_cost,
        total_profit=total_profit,
        avg_margin_pct=avg_margin,
        order_count=order_count,
        item_count=item_count,
    )

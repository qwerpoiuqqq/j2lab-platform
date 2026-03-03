"""Settlement service: revenue/profit analysis from orders + order_items.

PHASE 0: Cost calculation uses SuperapAccount.unit_cost_traffic/unit_cost_save (via cost_unit_price snapshot)
         instead of Product.base_price.
PHASE 6: Added by-handler, by-company, by-date aggregation views.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product
from app.models.superap_account import SuperapAccount
from app.models.user import User
from app.schemas.settlement import (
    SettlementRow,
    SettlementSummary,
    SettlementByHandlerRow,
    SettlementByCompanyRow,
    SettlementByDateRow,
    OrderBrief,
    DailyCheckDistributorRow,
    DailyCheckResponse,
)


def _base_filters(
    date_from: date | None = None,
    date_to: date | None = None,
    company_id: int | None = None,
    handler_user_ids: list | None = None,
    order_type: str | None = None,
) -> list:
    """Build common settlement filters with optional company/handler scope."""
    settled_statuses = [
        OrderStatus.PAYMENT_CONFIRMED.value,
        OrderStatus.PROCESSING.value,
        OrderStatus.COMPLETED.value,
    ]
    filters = [Order.status.in_(settled_statuses)]

    if date_from is not None:
        filters.append(Order.created_at >= date_from)
    if date_to is not None:
        from datetime import datetime, time, timezone

        end_of_day = datetime.combine(date_to, time.max, tzinfo=timezone.utc)
        filters.append(Order.created_at <= end_of_day)

    if company_id is not None:
        filters.append(Order.company_id == company_id)
    if handler_user_ids is not None:
        filters.append(Order.user_id.in_(handler_user_ids))

    if order_type is not None:
        types = [t.strip() for t in order_type.split(",")]
        filters.append(Order.order_type.in_(types))

    return filters


def _calc_cost(item: OrderItem, product: Product) -> int:
    """Calculate cost with 3-tier priority (PHASE 0 fix).

    Priority:
    1. cost_unit_price (snapshot at assignment time) * quantity
    2. Product.base_price * quantity (fallback)
    """
    quantity = item.quantity or 1
    if item.cost_unit_price is not None:
        return int(item.cost_unit_price) * quantity
    return int(product.base_price or 0) * quantity


async def get_settlement_data(
    db: AsyncSession,
    date_from: date | None = None,
    date_to: date | None = None,
    skip: int = 0,
    limit: int = 50,
    company_id: int | None = None,
    handler_user_ids: list | None = None,
    order_type: str | None = None,
) -> tuple[list[SettlementRow], SettlementSummary, int]:
    """Get settlement data with corrected cost calculation."""
    filters = _base_filters(date_from, date_to, company_id=company_id, handler_user_ids=handler_user_ids, order_type=order_type)

    # Count
    count_stmt = (
        select(func.count())
        .select_from(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .where(*filters)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    # Fetch items
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
        quantity = item.quantity or 1
        subtotal = unit_price * quantity
        cost = _calc_cost(item, product)
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
            base_price=int(product.base_price) if product.base_price else 0,
            subtotal=subtotal,
            cost=cost,
            profit=profit,
            margin_pct=margin_pct,
            created_at=order.created_at,
        ))

    summary = await _compute_summary(db, filters)
    return rows, summary, total


async def _compute_summary(
    db: AsyncSession,
    filters: list,
) -> SettlementSummary:
    """Compute aggregated summary with corrected cost (PHASE 0)."""
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

    # Cost: use cost_unit_price when available, else base_price
    cost_expr = case(
        (
            OrderItem.cost_unit_price.isnot(None),
            OrderItem.cost_unit_price * OrderItem.quantity,
        ),
        else_=Product.base_price * OrderItem.quantity,
    )
    cost_stmt = (
        select(func.coalesce(func.sum(cost_expr), 0).label("total_cost"))
        .select_from(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Product, OrderItem.product_id == Product.id)
        .where(*filters)
    )
    cost_result = (await db.execute(cost_stmt)).one()
    total_cost = int(cost_result.total_cost)

    total_profit = total_revenue - total_cost
    avg_margin = round(
        (total_profit / total_revenue * 100) if total_revenue > 0 else 0.0, 2
    )

    return SettlementSummary(
        total_revenue=total_revenue,
        total_cost=total_cost,
        total_profit=total_profit,
        avg_margin_pct=avg_margin,
        order_count=order_count,
        item_count=item_count,
    )


# ---- PHASE 6: New aggregation views ----


async def get_settlement_by_handler(
    db: AsyncSession,
    date_from: date | None = None,
    date_to: date | None = None,
    company_id: int | None = None,
    handler_user_ids: list | None = None,
    order_type: str | None = None,
) -> list[SettlementByHandlerRow]:
    """Aggregate settlements by responsible order_handler.

    Resolves the handler for each order by tracing the parent chain:
    - order_handler → self
    - distributor → parent (= order_handler)
    - sub_account → parent.parent (= order_handler via distributor)
    """
    from sqlalchemy.orm import aliased

    filters = _base_filters(date_from, date_to, company_id=company_id, handler_user_ids=handler_user_ids, order_type=order_type)

    cost_expr = case(
        (
            OrderItem.cost_unit_price.isnot(None),
            OrderItem.cost_unit_price * OrderItem.quantity,
        ),
        else_=Product.base_price * OrderItem.quantity,
    )

    # Aliases for parent chain traversal
    OrderUser = aliased(User, name="order_user")       # 주문자
    ParentUser = aliased(User, name="parent_user")     # 주문자의 parent
    GrandparentUser = aliased(User, name="gp_user")    # 주문자의 parent.parent

    # Resolve handler_id: trace up to order_handler level
    handler_id_expr = case(
        (OrderUser.role == "order_handler", OrderUser.id),
        (OrderUser.role == "distributor", OrderUser.parent_id),
        (OrderUser.role == "sub_account", ParentUser.parent_id),
        else_=OrderUser.id,  # fallback (company_admin 등)
    )

    handler_name_expr = case(
        (OrderUser.role == "order_handler", OrderUser.name),
        (OrderUser.role == "distributor", ParentUser.name),
        (OrderUser.role == "sub_account", GrandparentUser.name),
        else_=OrderUser.name,
    )

    stmt = (
        select(
            handler_id_expr.label("handler_id"),
            handler_name_expr.label("handler_name"),
            func.count(func.distinct(Order.id)).label("order_count"),
            func.count(OrderItem.id).label("item_count"),
            func.coalesce(func.sum(OrderItem.subtotal), 0).label("total_revenue"),
            func.coalesce(func.sum(cost_expr), 0).label("total_cost"),
        )
        .select_from(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Product, OrderItem.product_id == Product.id)
        .join(OrderUser, Order.user_id == OrderUser.id)
        .outerjoin(ParentUser, OrderUser.parent_id == ParentUser.id)
        .outerjoin(GrandparentUser, ParentUser.parent_id == GrandparentUser.id)
        .where(*filters)
        .group_by(handler_id_expr, handler_name_expr)
        .order_by(func.sum(OrderItem.subtotal).desc())
    )

    result = await db.execute(stmt)
    rows = []
    for row in result.all():
        revenue = int(row.total_revenue)
        cost = int(row.total_cost)
        profit = revenue - cost
        margin = round((profit / revenue * 100) if revenue > 0 else 0.0, 2)
        rows.append(SettlementByHandlerRow(
            handler_id=str(row.handler_id) if row.handler_id else "unknown",
            handler_name=row.handler_name or "미지정",
            handler_role="order_handler",
            order_count=row.order_count,
            item_count=row.item_count,
            total_revenue=revenue,
            total_cost=cost,
            total_profit=profit,
            avg_margin_pct=margin,
        ))
    return rows


async def get_settlement_by_company(
    db: AsyncSession,
    date_from: date | None = None,
    date_to: date | None = None,
    company_id: int | None = None,
    handler_user_ids: list | None = None,
    order_type: str | None = None,
) -> list[SettlementByCompanyRow]:
    """Aggregate settlements by company."""
    from app.models.company import Company

    filters = _base_filters(date_from, date_to, company_id=company_id, handler_user_ids=handler_user_ids, order_type=order_type)

    cost_expr = case(
        (
            OrderItem.cost_unit_price.isnot(None),
            OrderItem.cost_unit_price * OrderItem.quantity,
        ),
        else_=Product.base_price * OrderItem.quantity,
    )

    stmt = (
        select(
            Company.id.label("company_id"),
            Company.name.label("company_name"),
            func.count(func.distinct(Order.id)).label("order_count"),
            func.count(OrderItem.id).label("item_count"),
            func.coalesce(func.sum(OrderItem.subtotal), 0).label("total_revenue"),
            func.coalesce(func.sum(cost_expr), 0).label("total_cost"),
        )
        .select_from(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Product, OrderItem.product_id == Product.id)
        .outerjoin(Company, Order.company_id == Company.id)
        .where(*filters)
        .group_by(Company.id, Company.name)
        .order_by(func.sum(OrderItem.subtotal).desc())
    )

    result = await db.execute(stmt)
    rows = []
    for row in result.all():
        revenue = int(row.total_revenue)
        cost = int(row.total_cost)
        profit = revenue - cost
        margin = round((profit / revenue * 100) if revenue > 0 else 0.0, 2)
        rows.append(SettlementByCompanyRow(
            company_id=row.company_id,
            company_name=row.company_name or "미지정",
            order_count=row.order_count,
            item_count=row.item_count,
            total_revenue=revenue,
            total_cost=cost,
            total_profit=profit,
            avg_margin_pct=margin,
        ))
    return rows


async def get_settlement_by_date(
    db: AsyncSession,
    date_from: date | None = None,
    date_to: date | None = None,
    company_id: int | None = None,
    handler_user_ids: list | None = None,
    order_type: str | None = None,
) -> list[SettlementByDateRow]:
    """Aggregate settlements by date (for chart data)."""
    filters = _base_filters(date_from, date_to, company_id=company_id, handler_user_ids=handler_user_ids, order_type=order_type)

    cost_expr = case(
        (
            OrderItem.cost_unit_price.isnot(None),
            OrderItem.cost_unit_price * OrderItem.quantity,
        ),
        else_=Product.base_price * OrderItem.quantity,
    )

    date_col = func.date(Order.created_at).label("order_date")

    stmt = (
        select(
            date_col,
            func.count(func.distinct(Order.id)).label("order_count"),
            func.count(OrderItem.id).label("item_count"),
            func.coalesce(func.sum(OrderItem.subtotal), 0).label("total_revenue"),
            func.coalesce(func.sum(cost_expr), 0).label("total_cost"),
        )
        .select_from(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Product, OrderItem.product_id == Product.id)
        .where(*filters)
        .group_by(date_col)
        .order_by(date_col.asc())
    )

    result = await db.execute(stmt)
    rows = []
    for row in result.all():
        revenue = int(row.total_revenue)
        cost = int(row.total_cost)
        profit = revenue - cost
        rows.append(SettlementByDateRow(
            date=str(row.order_date),
            order_count=row.order_count,
            item_count=row.item_count,
            total_revenue=revenue,
            total_cost=cost,
            total_profit=profit,
        ))
    return rows


# ---- Daily settlement check (정산 체크) ----


async def get_daily_settlement_check(
    db: AsyncSession,
    check_date: date,
    company_id: int | None = None,
    handler_user_ids: list | None = None,
) -> DailyCheckResponse:
    """Get daily settlement check view: submitted + payment_hold orders grouped by distributor.

    Returns orders that need payment checking for the given date,
    grouped by the distributor (parent of the order's user).
    order_handler sees only their line's orders via handler_user_ids.
    """
    from datetime import datetime, time, timezone as tz
    from sqlalchemy.orm import aliased

    start_of_day = datetime.combine(check_date, time.min, tzinfo=tz.utc)
    end_of_day = datetime.combine(check_date, time.max, tzinfo=tz.utc)

    check_statuses = [
        OrderStatus.SUBMITTED.value,
        OrderStatus.PAYMENT_HOLD.value,
    ]

    filters = [
        Order.status.in_(check_statuses),
        Order.created_at >= start_of_day,
        Order.created_at <= end_of_day,
    ]
    if company_id is not None:
        filters.append(Order.company_id == company_id)
    if handler_user_ids is not None:
        filters.append(Order.user_id.in_(handler_user_ids))

    # Fetch orders with their user info
    OrderUser = aliased(User, name="order_user")
    ParentUser = aliased(User, name="parent_user")

    stmt = (
        select(Order, OrderUser, ParentUser)
        .join(OrderUser, Order.user_id == OrderUser.id)
        .outerjoin(ParentUser, OrderUser.parent_id == ParentUser.id)
        .where(*filters)
        .order_by(Order.created_at.asc())
    )

    result = await db.execute(stmt)
    rows_raw = result.all()

    # Group by distributor
    distributor_map: dict[str, dict] = {}
    total_amount = 0
    total_orders = 0

    for order, order_user, parent_user in rows_raw:
        # Determine distributor: if user is sub_account, distributor is parent
        # If user is distributor, distributor is self
        # Otherwise, use the user themselves
        if order_user.role == "sub_account" and parent_user:
            dist_id = str(parent_user.id)
            dist_name = parent_user.name
        elif order_user.role == "distributor":
            dist_id = str(order_user.id)
            dist_name = order_user.name
        else:
            dist_id = str(order_user.id)
            dist_name = order_user.name

        if dist_id not in distributor_map:
            distributor_map[dist_id] = {
                "distributor_id": dist_id,
                "distributor_name": dist_name,
                "orders": [],
                "total_amount": 0,
            }

        # Extract place_name from first item's item_data
        place_name = ""
        if order.items:
            first_item = order.items[0]
            if first_item.item_data and isinstance(first_item.item_data, dict):
                place_name = first_item.item_data.get("place_url", "")

        amt = int(order.total_amount) if order.total_amount else 0
        distributor_map[dist_id]["orders"].append(
            OrderBrief(
                id=order.id,
                place_name=place_name,
                total_amount=amt,
                status=order.status,
                created_at=order.created_at,
            )
        )
        distributor_map[dist_id]["total_amount"] += amt
        total_amount += amt
        total_orders += 1

    distributors = []
    for dist_data in distributor_map.values():
        distributors.append(
            DailyCheckDistributorRow(
                distributor_id=dist_data["distributor_id"],
                distributor_name=dist_data["distributor_name"],
                order_count=len(dist_data["orders"]),
                total_amount=dist_data["total_amount"],
                orders=dist_data["orders"],
            )
        )

    return DailyCheckResponse(
        date=check_date.isoformat(),
        distributors=distributors,
        summary={
            "total_orders": total_orders,
            "total_amount": total_amount,
            "distributor_count": len(distributors),
        },
    )

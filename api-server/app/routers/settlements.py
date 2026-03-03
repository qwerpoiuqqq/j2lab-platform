"""Settlements router: revenue/profit analysis, Excel export, aggregation views."""

from __future__ import annotations

import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import RoleChecker
from app.models.user import User, UserRole
from app.schemas.settlement import (
    DailyCheckResponse,
    SettlementByCompanyRow,
    SettlementByDateRow,
    SettlementByHandlerRow,
    SettlementResponse,
    SettlementSecretRequest,
    SettlementSecretResponse,
)
from app.core.config import settings
from app.services import settlement_service
from app.services.user_service import get_line_user_ids

router = APIRouter(prefix="/settlements", tags=["settlements"])

admin_checker = RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ORDER_HANDLER])
system_admin_checker = RoleChecker([UserRole.SYSTEM_ADMIN])


async def _resolve_settlement_filters(
    current_user: User,
    db: AsyncSession,
) -> dict:
    """Resolve company_id and handler_user_ids based on current user's role."""
    user_role = UserRole(current_user.role)
    filters: dict = {"company_id": None, "handler_user_ids": None}

    if user_role == UserRole.COMPANY_ADMIN:
        filters["company_id"] = current_user.company_id
    elif user_role == UserRole.ORDER_HANDLER:
        line_ids = await get_line_user_ids(db, current_user.id)
        filters["handler_user_ids"] = line_ids
    # system_admin: no filters

    return filters


@router.get("/", response_model=SettlementResponse)
async def list_settlements(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_checker),
):
    """List settlements with date range filter and role-based scope."""
    scope = await _resolve_settlement_filters(current_user, db)
    offset = (page - 1) * size
    rows, summary, total = await settlement_service.get_settlement_data(
        db, date_from=date_from, date_to=date_to, skip=offset, limit=size,
        company_id=scope["company_id"], handler_user_ids=scope["handler_user_ids"],
    )
    pages = (total + size - 1) // size if size > 0 else 0
    return SettlementResponse(
        items=rows,
        summary=summary,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get("/daily-check", response_model=DailyCheckResponse)
async def daily_settlement_check(
    check_date: date | None = Query(None, alias="date"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ORDER_HANDLER])
    ),
):
    """Daily settlement check view: submitted + payment_hold orders grouped by distributor.

    If no date is provided, defaults to today.
    company_admin sees only their company's orders.
    order_handler sees only their line's orders.
    """
    if check_date is None:
        check_date = date.today()

    company_id = None
    handler_user_ids = None
    user_role = UserRole(current_user.role)
    if user_role == UserRole.COMPANY_ADMIN:
        company_id = current_user.company_id
    elif user_role == UserRole.ORDER_HANDLER:
        handler_user_ids = await get_line_user_ids(db, current_user.id)

    return await settlement_service.get_daily_settlement_check(
        db, check_date=check_date, company_id=company_id,
        handler_user_ids=handler_user_ids,
    )


@router.get("/by-handler", response_model=list[SettlementByHandlerRow])
async def settlement_by_handler(
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_checker),
):
    """Get settlement data aggregated by handler with role-based scope."""
    scope = await _resolve_settlement_filters(current_user, db)
    return await settlement_service.get_settlement_by_handler(
        db, date_from=date_from, date_to=date_to,
        company_id=scope["company_id"], handler_user_ids=scope["handler_user_ids"],
    )


@router.get("/by-company", response_model=list[SettlementByCompanyRow])
async def settlement_by_company(
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_checker),
):
    """Get settlement data aggregated by company with role-based scope."""
    scope = await _resolve_settlement_filters(current_user, db)
    return await settlement_service.get_settlement_by_company(
        db, date_from=date_from, date_to=date_to,
        company_id=scope["company_id"], handler_user_ids=scope["handler_user_ids"],
    )


@router.get("/by-date", response_model=list[SettlementByDateRow])
async def settlement_by_date(
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_checker),
):
    """Get settlement data aggregated by date with role-based scope."""
    scope = await _resolve_settlement_filters(current_user, db)
    return await settlement_service.get_settlement_by_date(
        db, date_from=date_from, date_to=date_to,
        company_id=scope["company_id"], handler_user_ids=scope["handler_user_ids"],
    )


@router.post("/secret", response_model=SettlementSecretResponse)
async def settlement_secret(
    body: SettlementSecretRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(system_admin_checker),
):
    """Password-protected detailed settlement analysis (system_admin only)."""
    if body.password != settings.SETTLEMENT_SECRET_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid settlement password",
        )

    rows, summary, _ = await settlement_service.get_settlement_data(
        db, date_from=body.date_from, date_to=body.date_to, skip=0, limit=10000,
    )
    return SettlementSecretResponse(items=rows, summary=summary)


@router.get("/export")
async def export_settlements(
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_checker),
):
    """Export settlement data as Excel file with role-based scope."""
    from openpyxl import Workbook

    scope = await _resolve_settlement_filters(current_user, db)
    rows, summary, _ = await settlement_service.get_settlement_data(
        db, date_from=date_from, date_to=date_to, skip=0, limit=50000,
        company_id=scope["company_id"], handler_user_ids=scope["handler_user_ids"],
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Settlements"

    headers = [
        "Order ID", "Order Number", "Product", "User", "Role",
        "Qty", "Unit Price", "Base Price", "Subtotal", "Cost",
        "Profit", "Margin %", "Date",
    ]
    ws.append(headers)

    for row in rows:
        ws.append([
            row.order_id,
            row.order_number,
            row.product_name,
            row.user_name,
            row.user_role,
            row.quantity,
            row.unit_price,
            row.base_price,
            row.subtotal,
            row.cost,
            row.profit,
            row.margin_pct,
            row.created_at.strftime("%Y-%m-%d %H:%M"),
        ])

    ws.append([])
    ws.append([
        "SUMMARY", "", "", "", "",
        "", "", "", summary.total_revenue, summary.total_cost,
        summary.total_profit, summary.avg_margin_pct,
        f"Orders: {summary.order_count} / Items: {summary.item_count}",
    ])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = "settlements"
    if date_from:
        filename += f"_{date_from}"
    if date_to:
        filename += f"_to_{date_to}"
    filename += ".xlsx"

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

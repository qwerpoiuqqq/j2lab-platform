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
    SettlementByCompanyRow,
    SettlementByDateRow,
    SettlementByHandlerRow,
    SettlementResponse,
    SettlementSecretRequest,
    SettlementSecretResponse,
)
from app.core.config import settings
from app.services import settlement_service

router = APIRouter(prefix="/settlements", tags=["settlements"])

admin_checker = RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN])
system_admin_checker = RoleChecker([UserRole.SYSTEM_ADMIN])


@router.get("/", response_model=SettlementResponse)
async def list_settlements(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """List settlements with date range filter (system_admin, company_admin)."""
    offset = (page - 1) * size
    rows, summary, total = await settlement_service.get_settlement_data(
        db, date_from=date_from, date_to=date_to, skip=offset, limit=size,
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


@router.get("/by-handler", response_model=list[SettlementByHandlerRow])
async def settlement_by_handler(
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Get settlement data aggregated by handler (user)."""
    return await settlement_service.get_settlement_by_handler(
        db, date_from=date_from, date_to=date_to,
    )


@router.get("/by-company", response_model=list[SettlementByCompanyRow])
async def settlement_by_company(
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Get settlement data aggregated by company."""
    return await settlement_service.get_settlement_by_company(
        db, date_from=date_from, date_to=date_to,
    )


@router.get("/by-date", response_model=list[SettlementByDateRow])
async def settlement_by_date(
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Get settlement data aggregated by date (for chart display)."""
    return await settlement_service.get_settlement_by_date(
        db, date_from=date_from, date_to=date_to,
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
    _current_user: User = Depends(admin_checker),
):
    """Export settlement data as Excel file."""
    from openpyxl import Workbook

    rows, summary, _ = await settlement_service.get_settlement_data(
        db, date_from=date_from, date_to=date_to, skip=0, limit=50000,
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

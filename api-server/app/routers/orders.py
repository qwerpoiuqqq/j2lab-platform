"""Orders router: full order lifecycle with state transitions."""

from __future__ import annotations

import io
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import RoleChecker, get_current_active_user
from app.models.order import Order
from app.models.user import User, UserRole
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.order import (
    BulkStatusRequest,
    DeadlineUpdateRequest,
    ExcelUploadConfirmRequest,
    ExcelUploadPreviewItem,
    ExcelUploadPreviewResponse,
    OrderBriefResponse,
    OrderCreate,
    OrderRejectRequest,
    OrderResponse,
    OrderUpdate,
    SimplifiedOrderCreate,
)
from app.services import order_service
from app.services import pipeline_orchestrator
from app.services.pipeline_validation import validate_item_data_for_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("/", response_model=PaginatedResponse[OrderBriefResponse])
async def list_orders(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List orders with role-based filtering and pagination.

    - system_admin: sees all orders
    - company_admin, order_handler: sees orders in the same company
    - distributor: sees own + sub_account orders
    - sub_account: sees only own orders
    """
    pagination = PaginationParams(page=page, size=size)
    orders, total = await order_service.get_orders(
        db,
        skip=pagination.offset,
        limit=pagination.size,
        status=status_filter,
        search=search,
        current_user=current_user,
    )
    return PaginatedResponse.create(
        items=[OrderBriefResponse.model_validate(o) for o in orders],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.post(
    "/",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
    body: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a new order in draft status.

    Available to all authenticated users (distributor, sub_account typically).
    Prices are resolved automatically based on the user's price tier.
    """
    try:
        order = await order_service.create_order(db, body, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return order


# === Literal-path routes (must be before /{order_id} to avoid path conflicts) ===


@router.post(
    "/simplified",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_simplified_order(
    body: SimplifiedOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a simplified order (no product/category selection needed).

    Automatically matches products by campaign_type, calculates quantities,
    and builds pipeline-compatible item_data.
    """
    try:
        order = await order_service.create_simplified_order(db, body, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return order


@router.get("/excel-template/{product_id}")
async def get_excel_template(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
):
    """Generate an Excel template based on a product's form_schema."""
    from openpyxl import Workbook
    from app.services import product_service

    product = await product_service.get_product_by_id(db, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    wb = Workbook()
    ws = wb.active
    ws.title = "Order Template"

    # Build headers from form_schema
    headers = ["quantity"]
    if product.form_schema and isinstance(product.form_schema, list):
        for field in product.form_schema:
            if isinstance(field, dict):
                headers.append(field.get("name", field.get("key", "field")))
    elif product.form_schema and isinstance(product.form_schema, dict):
        for key in product.form_schema.get("fields", []):
            if isinstance(key, dict):
                headers.append(key.get("name", key.get("key", "field")))
            elif isinstance(key, str):
                headers.append(key)

    ws.append(headers)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = f"order_template_{product.id}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/excel-upload", response_model=ExcelUploadPreviewResponse)
async def excel_upload(
    file: UploadFile = File(...),
    product_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
):
    """Parse an uploaded Excel file, validate against product schema, return preview."""
    from openpyxl import load_workbook
    from app.services import product_service

    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .xlsx files are supported",
        )

    product = await product_service.get_product_by_id(db, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    content = await file.read()
    try:
        wb = load_workbook(io.BytesIO(content), read_only=True)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Excel file",
        )

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        return ExcelUploadPreviewResponse(
            items=[], total=0, valid_count=0, error_count=0,
            product_id=product_id, product_name=product.name,
        )

    headers = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(rows[0])]
    preview_items = []
    valid_count = 0

    for row_idx, row in enumerate(rows[1:], start=1):
        row_dict = {}
        for i, val in enumerate(row):
            if i < len(headers):
                row_dict[headers[i]] = val

        errors = order_service.validate_item_data(product, row_dict)
        is_valid = len(errors) == 0
        if is_valid:
            valid_count += 1

        preview_items.append(ExcelUploadPreviewItem(
            row_number=row_idx,
            data=row_dict,
            is_valid=is_valid,
            errors=errors,
        ))

    return ExcelUploadPreviewResponse(
        items=preview_items,
        total=len(preview_items),
        valid_count=valid_count,
        error_count=len(preview_items) - valid_count,
        product_id=product_id,
        product_name=product.name,
    )


@router.post("/excel-upload/confirm", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def excel_upload_confirm(
    body: ExcelUploadConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Confirm and create order from validated Excel rows."""
    try:
        order = await order_service.create_order_from_excel(
            db, product_id=body.product_id, rows=body.rows,
            current_user=current_user, notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return order


@router.get("/export")
async def export_orders(
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ORDER_HANDLER])
    ),
):
    """Export filtered order list as Excel."""
    from openpyxl import Workbook

    orders, total = await order_service.get_orders(
        db, skip=0, limit=50000, status=status_filter, current_user=current_user,
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Orders"

    headers = [
        "ID", "Order Number", "Status", "Payment",
        "Total Amount", "VAT", "Source", "Created At",
    ]
    ws.append(headers)

    for o in orders:
        ws.append([
            o.id,
            o.order_number,
            o.status,
            o.payment_status,
            int(o.total_amount) if o.total_amount else 0,
            int(o.vat_amount) if o.vat_amount else 0,
            o.source,
            o.created_at.strftime("%Y-%m-%d %H:%M") if o.created_at else "",
        ])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=orders_export.xlsx"},
    )


@router.post("/bulk-status", response_model=MessageResponse)
async def bulk_status_change(
    body: BulkStatusRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN])
    ),
):
    """Bulk status change for multiple orders."""
    success_count = 0
    errors = []

    for oid in body.order_ids:
        order = await order_service.get_order_by_id(db, oid)
        if order is None:
            errors.append(f"Order {oid}: not found")
            continue
        try:
            await order_service.transition_order_status(db, order, body.status, current_user)
            success_count += 1
        except ValueError as e:
            errors.append(f"Order {oid}: {str(e)}")

    return MessageResponse(
        message=f"Updated {success_count}/{len(body.order_ids)} orders",
        detail={"errors": errors} if errors else None,
    )


@router.get("/sub-account-pending")
async def get_sub_account_pending_orders(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.DISTRIBUTOR])
    ),
):
    """Get pending sub-account orders awaiting distributor inclusion/exclusion."""
    orders = await order_service.get_sub_account_pending_orders(
        db, distributor=current_user, skip=skip, limit=limit,
    )
    return {
        "items": [
            {
                "id": o.id,
                "order_number": o.order_number,
                "user_id": str(o.user_id),
                "status": o.status,
                "total_amount": int(o.total_amount) if o.total_amount else 0,
                "selection_status": o.selection_status,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in orders
        ],
    }


@router.post("/{order_id}/include")
async def include_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.DISTRIBUTOR])
    ),
):
    """Include a sub-account order (pending -> included)."""
    order = await order_service.get_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    try:
        await order_service.set_selection_status(db, order, "included", current_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"message": "Order included", "order_id": order.id}


@router.post("/{order_id}/exclude")
async def exclude_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.DISTRIBUTOR])
    ),
):
    """Exclude a sub-account order (pending -> excluded)."""
    order = await order_service.get_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    try:
        await order_service.set_selection_status(db, order, "excluded", current_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"message": "Order excluded", "order_id": order.id}


@router.post("/bulk-include")
async def bulk_include_orders(
    body: BulkStatusRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.DISTRIBUTOR])
    ),
):
    """Bulk include multiple sub-account orders."""
    success = 0
    errors = []
    for oid in body.order_ids:
        order = await order_service.get_order_by_id(db, oid)
        if order is None:
            errors.append(f"Order {oid}: not found")
            continue
        try:
            await order_service.set_selection_status(db, order, "included", current_user)
            success += 1
        except ValueError as e:
            errors.append(f"Order {oid}: {str(e)}")
    return {"included": success, "errors": errors}


@router.get("/deadlines")
async def get_order_deadlines(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get orders with deadlines in given month for calendar view."""
    from datetime import date as d
    from sqlalchemy import func
    from app.models.campaign import Campaign

    start = d(year, month, 1)
    if month == 12:
        end = d(year + 1, 1, 1)
    else:
        end = d(year, month + 1, 1)

    # Orders with deadline in range
    orders_q = await db.execute(
        select(Order).where(
            Order.completed_at.isnot(None),
            func.date(Order.completed_at) >= start,
            func.date(Order.completed_at) < end,
            Order.status.in_(["processing", "payment_confirmed", "completed"]),
        ).order_by(Order.completed_at.asc())
    )
    orders = orders_q.scalars().all()

    # Campaigns with end_date in range
    campaigns_q = await db.execute(
        select(Campaign).where(
            Campaign.end_date >= start,
            Campaign.end_date < end,
            Campaign.status.in_(["active", "completed"]),
        ).order_by(Campaign.end_date.asc())
    )
    campaigns = campaigns_q.scalars().all()

    return {
        "orders": [
            {
                "id": o.id,
                "order_number": o.order_number,
                "deadline": o.completed_at.isoformat() if o.completed_at else None,
                "status": o.status,
                "total_amount": int(o.total_amount) if o.total_amount else 0,
            }
            for o in orders
        ],
        "campaigns": [
            {
                "id": c.id,
                "campaign_code": c.campaign_code,
                "place_name": c.place_name,
                "end_date": c.end_date.isoformat() if c.end_date else None,
                "status": c.status,
            }
            for c in campaigns
        ],
    }


# === Parameterized /{order_id} routes ===


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a single order by ID with items."""
    order = await order_service.get_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    if not order_service.can_view_order(current_user, order):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this order",
        )

    return order


@router.patch("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: int,
    body: OrderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        RoleChecker(
            [UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ORDER_HANDLER]
        )
    ),
):
    """Update an order (only in draft status)."""
    order = await order_service.get_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    try:
        updated = await order_service.update_order(db, order, notes=body.notes)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return updated


@router.post("/{order_id}/submit", response_model=OrderResponse)
async def submit_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN, UserRole.DISTRIBUTOR])
    ),
):
    """Submit an order: draft -> submitted.

    Typically done by the distributor confirming a sub_account's order.
    """
    order = await order_service.get_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    # Distributors can only submit their own or sub_account orders
    user_role = UserRole(current_user.role)
    if user_role == UserRole.DISTRIBUTOR:
        if not order_service.can_view_order(current_user, order):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to submit this order",
            )

    try:
        submitted = await order_service.submit_order(db, order, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return submitted


@router.post("/{order_id}/confirm-payment", response_model=OrderResponse)
async def confirm_payment(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN])
    ),
):
    """Confirm payment: submitted -> payment_confirmed.

    Deducts balance from the order's user. company_admin or system_admin only.
    """
    order = await order_service.get_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    # company_admin can only confirm orders in their company
    user_role = UserRole(current_user.role)
    if user_role == UserRole.COMPANY_ADMIN:
        if order.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Company admin can only confirm orders in their own company",
            )

    try:
        confirmed = await order_service.confirm_payment(db, order, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Validate item_data for pipeline (non-blocking warnings)
    pipeline_warnings: list[str] = []
    if confirmed.items:
        for item in confirmed.items:
            item_warnings = validate_item_data_for_pipeline(item.item_data)
            for w in item_warnings:
                pipeline_warnings.append(f"Item #{item.row_number or item.id}: {w}")

    # Start E2E pipeline (best-effort -- payment confirmation is preserved on failure)
    try:
        await pipeline_orchestrator.start_pipeline_for_order(db, confirmed)
    except Exception as e:
        logger.error("Pipeline start failed for order %s: %s", order_id, e)

    # Refresh to ensure all attributes are loaded for serialization
    await db.refresh(confirmed)
    result = OrderResponse.model_validate(confirmed).model_dump()
    result["pipeline_warnings"] = pipeline_warnings
    return result


@router.post("/{order_id}/reject", response_model=OrderResponse)
async def reject_order(
    order_id: int,
    body: OrderRejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN])
    ),
):
    """Reject an order: submitted -> rejected. company_admin or system_admin only."""
    order = await order_service.get_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    # company_admin can only reject orders in their company
    user_role = UserRole(current_user.role)
    if user_role == UserRole.COMPANY_ADMIN:
        if order.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Company admin can only reject orders in their own company",
            )

    try:
        rejected = await order_service.reject_order(db, order, body.reason)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return rejected


@router.post("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN])
    ),
):
    """Cancel an order: draft/submitted -> cancelled. company_admin or system_admin only."""
    order = await order_service.get_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    try:
        cancelled = await order_service.cancel_order(db, order, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return cancelled


@router.post("/{order_id}/approve", response_model=OrderResponse)
async def approve_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN])
    ),
):
    """Approve order: submitted -> payment_confirmed. Alias for confirm-payment."""
    order = await order_service.get_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    user_role = UserRole(current_user.role)
    if user_role == UserRole.COMPANY_ADMIN:
        if order.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Company admin can only approve orders in their own company",
            )

    try:
        confirmed = await order_service.confirm_payment(db, order, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    try:
        await pipeline_orchestrator.start_pipeline_for_order(db, confirmed)
    except Exception as e:
        logger.error("Pipeline start failed for order %s: %s", order_id, e)

    await db.refresh(confirmed)
    return confirmed


@router.get("/{order_id}/items/export")
async def export_order_items(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Export order items as an Excel file."""
    from openpyxl import Workbook

    order = await order_service.get_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )
    if not order_service.can_view_order(current_user, order):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this order",
        )

    wb = Workbook()
    ws = wb.active
    ws.title = "Order Items"

    headers = [
        "Row #", "Product ID", "Quantity", "Unit Price",
        "Subtotal", "Status", "Result",
    ]
    ws.append(headers)

    for item in order.items:
        ws.append([
            item.row_number,
            item.product_id,
            item.quantity,
            int(item.unit_price) if item.unit_price else 0,
            int(item.subtotal) if item.subtotal else 0,
            item.status,
            item.result_message or "",
        ])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = f"order_{order.order_number}_items.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.patch("/{order_id}/deadline", response_model=OrderResponse)
async def update_deadline(
    order_id: int,
    body: DeadlineUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ORDER_HANDLER])
    ),
):
    """Update the deadline for an order."""
    order = await order_service.get_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    try:
        updated = await order_service.update_deadline(db, order, body.deadline)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return updated

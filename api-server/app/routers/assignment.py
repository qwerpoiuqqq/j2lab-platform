"""Assignment router: auto-assignment, confirm, override, choose (new/extend)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import RoleChecker
from app.models.order import OrderItem
from app.models.user import User, UserRole
from app.schemas.assignment import (
    AssignmentChoiceRequest,
    AssignmentConfirmRequest,
    AssignmentOverrideRequest,
    AssignmentResult,
    BulkConfirmRequest,
    PlaceNetworkHistoryResponse,
)
from app.schemas.common import MessageResponse
from app.services import assignment_service, campaign_service
from app.services import pipeline_orchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assignment", tags=["assignment"])

admin_checker = RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ORDER_HANDLER])


@router.get("/queue")
async def get_assignment_queue(
    assignment_status: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_checker),
):
    """Get order items pending assignment with AI recommendation info."""
    company_id = None
    handler_user_ids = None
    user_role = UserRole(current_user.role)

    if user_role == UserRole.COMPANY_ADMIN:
        company_id = current_user.company_id
    elif user_role == UserRole.ORDER_HANDLER:
        from app.services.user_service import get_line_user_ids
        handler_user_ids = await get_line_user_ids(db, current_user.id)

    enriched = await assignment_service.get_assignment_queue_enriched(
        db,
        company_id=company_id,
        assignment_status=assignment_status,
        skip=skip,
        limit=limit,
        handler_user_ids=handler_user_ids,
    )

    return {"items": enriched}


@router.post("/auto-assign", response_model=AssignmentResult)
async def run_auto_assignment(
    order_item_id: int,
    campaign_type: str,
    place_id: int,
    company_id: int,
    total_limit: int | None = None,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Run auto-assignment for a specific order item."""
    from sqlalchemy import select

    result = await db.execute(
        select(OrderItem).where(OrderItem.id == order_item_id)
    )
    order_item = result.scalar_one_or_none()
    if order_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order item not found",
        )

    assignment_result = await assignment_service.auto_assign(
        db,
        order_item=order_item,
        campaign_type=campaign_type,
        place_id=place_id,
        company_id=company_id,
        total_limit=total_limit,
    )
    return assignment_result


@router.patch("/{item_id}/account")
async def override_account(
    item_id: int,
    body: AssignmentOverrideRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_checker),
):
    """Manually change the assigned account/network for an order item."""
    from sqlalchemy import select

    result = await db.execute(
        select(OrderItem).where(OrderItem.id == item_id)
    )
    order_item = result.scalar_one_or_none()
    if order_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order item not found",
        )

    try:
        updated = await assignment_service.override_assignment(
            db,
            order_item=order_item,
            account_id=body.account_id,
            confirmed_by=current_user.id,
            network_preset_id=body.network_preset_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return {"message": "Assignment overridden", "order_item_id": updated.id}


@router.post("/{item_id}/confirm")
async def confirm_assignment(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_checker),
):
    """Confirm an auto-assigned account."""
    from sqlalchemy import select

    result = await db.execute(
        select(OrderItem).where(OrderItem.id == item_id)
    )
    order_item = result.scalar_one_or_none()
    if order_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order item not found",
        )

    try:
        updated = await assignment_service.confirm_assignment(
            db,
            order_item=order_item,
            confirmed_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Trigger campaign registration
    try:
        await pipeline_orchestrator.on_assignment_confirmed(db, item_id)
    except Exception as e:
        logger.error("Campaign registration trigger failed for item %s: %s", item_id, e)

    return {"message": "Assignment confirmed", "order_item_id": updated.id}


@router.post("/{item_id}/choose")
async def choose_assignment_action(
    item_id: int,
    body: AssignmentChoiceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_checker),
):
    """Choose new or extend for an assignment (PHASE 4).

    action=new: confirm + dispatch as new campaign registration
    action=extend: confirm + dispatch campaign extension
    """
    from sqlalchemy import select

    result = await db.execute(
        select(OrderItem).where(OrderItem.id == item_id)
    )
    order_item = result.scalar_one_or_none()
    if order_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order item not found",
        )

    # Confirm the assignment first
    try:
        updated = await assignment_service.confirm_assignment(
            db,
            order_item=order_item,
            confirmed_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Dispatch based on action choice
    try:
        await pipeline_orchestrator.on_assignment_choice(
            db, item_id, action=body.action
        )
    except Exception as e:
        logger.error(
            "Assignment choice dispatch failed for item %s (action=%s): %s",
            item_id, body.action, e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dispatch failed: {str(e)}",
        )

    return {
        "message": f"Assignment {body.action} dispatched",
        "order_item_id": updated.id,
        "action": body.action,
    }


@router.post("/bulk-confirm")
async def bulk_confirm(
    body: BulkConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_checker),
):
    """Bulk confirm multiple assignments."""
    from sqlalchemy import select

    confirmed = []
    errors = []

    for item_id in body.item_ids:
        result = await db.execute(
            select(OrderItem).where(OrderItem.id == item_id)
        )
        order_item = result.scalar_one_or_none()
        if order_item is None:
            errors.append({"item_id": item_id, "error": "Not found"})
            continue

        try:
            await assignment_service.confirm_assignment(
                db,
                order_item=order_item,
                confirmed_by=current_user.id,
            )
            confirmed.append(item_id)

            try:
                await pipeline_orchestrator.on_assignment_confirmed(db, item_id)
            except Exception as e:
                logger.error(
                    "Campaign registration trigger failed for item %s: %s",
                    item_id, e,
                )
        except ValueError as e:
            errors.append({"item_id": item_id, "error": str(e)})

    return {
        "confirmed": confirmed,
        "errors": errors,
        "total_confirmed": len(confirmed),
        "total_errors": len(errors),
    }


@router.get("/place/{place_id}/history")
async def get_place_history(
    place_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Get network usage history for a place."""
    campaigns = await assignment_service.get_place_network_history(
        db, place_id=place_id
    )
    return {
        "place_id": place_id,
        "campaigns": [
            {
                "campaign_id": c.id,
                "campaign_type": c.campaign_type,
                "network_preset_id": c.network_preset_id,
                "superap_account_id": c.superap_account_id,
                "status": c.status,
                "total_limit": c.total_limit,
                "start_date": str(c.start_date),
                "end_date": str(c.end_date),
            }
            for c in campaigns
        ],
    }


def _format_queue_item(item: OrderItem) -> dict:
    """Format an order item for the assignment queue response."""
    return {
        "order_item_id": item.id,
        "order_id": item.order_id,
        "place_id": item.place_id,
        "assignment_status": item.assignment_status,
        "assigned_account_id": item.assigned_account_id,
    }

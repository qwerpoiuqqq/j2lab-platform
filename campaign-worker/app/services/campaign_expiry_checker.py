"""Campaign expiry checker - auto-completes expired campaigns daily."""

from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.models.campaign import Campaign
from app.models.order import Order, OrderItem
from app.models.pipeline_state import PipelineState, PipelineStage
from app.models.pipeline_log import PipelineLog

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")


async def check_expired_campaigns() -> dict:
    """Find and auto-complete expired campaigns.

    Runs daily at 00:30 KST via APScheduler.

    Logic:
    1. Find campaigns where status IN ('active', 'paused') AND end_date < today (KST)
    2. For each expired campaign:
       a. Set campaign.status = 'completed'
       b. Transition PipelineState: campaign_active -> management -> completed
       c. Set OrderItem.status = 'completed'
       d. If ALL items in that Order are completed -> Order.status = 'completed'
    3. Commit all changes
    4. Log summary
    """
    today_kst = datetime.now(KST).date()
    logger.info("[ExpiryChecker] Starting check for expired campaigns (today=%s)", today_kst)

    completed_count = 0
    order_completed_count = 0
    errors = []

    async with async_session_factory() as session:
        # Step 1: Find expired campaigns
        result = await session.execute(
            select(Campaign).where(
                and_(
                    Campaign.status.in_(["active", "paused"]),
                    Campaign.end_date < today_kst,
                )
            )
        )
        expired_campaigns = list(result.scalars().all())

        if not expired_campaigns:
            logger.info("[ExpiryChecker] No expired campaigns found")
            return {"completed": 0, "orders_completed": 0, "errors": []}

        logger.info("[ExpiryChecker] Found %d expired campaigns", len(expired_campaigns))

        for campaign in expired_campaigns:
            try:
                # Step 2a: Set campaign status to completed
                campaign.status = "completed"

                # Step 2b: Transition PipelineState
                if campaign.id:
                    ps_result = await session.execute(
                        select(PipelineState).where(
                            PipelineState.campaign_id == campaign.id
                        )
                    )
                    pipeline_state = ps_result.scalar_one_or_none()

                    if pipeline_state:
                        old_stage = pipeline_state.current_stage

                        if old_stage == PipelineStage.CAMPAIGN_ACTIVE:
                            # Transition: campaign_active -> management
                            pipeline_state.previous_stage = old_stage
                            pipeline_state.current_stage = PipelineStage.MANAGEMENT
                            session.add(PipelineLog(
                                pipeline_state_id=pipeline_state.id,
                                from_stage=PipelineStage.CAMPAIGN_ACTIVE,
                                to_stage=PipelineStage.MANAGEMENT,
                                trigger_type="expiry_checker",
                                message=f"Campaign {campaign.id} expired (end_date={campaign.end_date})",
                            ))

                            # Transition: management -> completed
                            pipeline_state.previous_stage = PipelineStage.MANAGEMENT
                            pipeline_state.current_stage = PipelineStage.COMPLETED
                            session.add(PipelineLog(
                                pipeline_state_id=pipeline_state.id,
                                from_stage=PipelineStage.MANAGEMENT,
                                to_stage=PipelineStage.COMPLETED,
                                trigger_type="expiry_checker",
                                message=f"Campaign {campaign.id} auto-completed by expiry checker",
                            ))
                        elif old_stage == PipelineStage.MANAGEMENT:
                            # Already in management, just complete
                            pipeline_state.previous_stage = old_stage
                            pipeline_state.current_stage = PipelineStage.COMPLETED
                            session.add(PipelineLog(
                                pipeline_state_id=pipeline_state.id,
                                from_stage=PipelineStage.MANAGEMENT,
                                to_stage=PipelineStage.COMPLETED,
                                trigger_type="expiry_checker",
                                message=f"Campaign {campaign.id} auto-completed by expiry checker",
                            ))

                # Step 2c: Set OrderItem status to completed
                if campaign.order_item_id:
                    oi_result = await session.execute(
                        select(OrderItem).where(
                            OrderItem.id == campaign.order_item_id
                        )
                    )
                    order_item = oi_result.scalar_one_or_none()

                    if order_item:
                        order_item.status = "completed"

                        # Step 2d: Check if ALL items in the Order are completed
                        all_items_result = await session.execute(
                            select(OrderItem).where(
                                OrderItem.order_id == order_item.order_id
                            )
                        )
                        all_items = list(all_items_result.scalars().all())

                        all_completed = all(
                            item.status == "completed" for item in all_items
                        )

                        if all_completed:
                            order_result = await session.execute(
                                select(Order).where(Order.id == order_item.order_id)
                            )
                            order = order_result.scalar_one_or_none()
                            if order and order.status != "completed":
                                order.status = "completed"
                                order.completed_at = datetime.now(KST)
                                order_completed_count += 1

                completed_count += 1

            except Exception as e:
                error_msg = f"Campaign {campaign.id}: {e}"
                logger.error("[ExpiryChecker] Error processing %s", error_msg)
                errors.append(error_msg)

        # Step 3: Commit all changes
        await session.commit()

    # Step 4: Log summary
    summary = {
        "completed": completed_count,
        "orders_completed": order_completed_count,
        "errors": errors,
    }
    logger.info(
        "[ExpiryChecker] Complete: %d campaigns completed, %d orders completed, %d errors",
        completed_count,
        order_completed_count,
        len(errors),
    )
    return summary

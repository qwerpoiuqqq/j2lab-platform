"""Pipeline orchestrator: connects E2E pipeline stages.

Coordinates between existing services to automate:
  입금확인 → 키워드추출 → 자동배정 → 캠페인등록

Each function is called from a router and handles one pipeline transition,
delegating to the appropriate services and worker clients.

PHASE 3: Added check_and_queue_ready_items() for deadline-based queue trigger.
PHASE 4: Added on_assignment_choice() for user new/extend selection.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign_template import CampaignTemplate
from app.models.extraction_job import ExtractionJob
from app.models.order import Order, OrderItem, OrderStatus, OrderType
from app.models.pipeline_log import PipelineLog
from app.models.pipeline_state import PipelineState
from app.models.product import Product
from app.models.superap_account import SuperapAccount
from app.schemas.campaign import CampaignCreate
from app.schemas.extraction_job import ExtractionJobCreate
from app.services import (
    assignment_service,
    campaign_service,
    extraction_service,
    pipeline_service,
    superap_account_service,
)
from app.services.worker_clients import (
    WorkerDispatchError,
    dispatch_campaign_extension,
    dispatch_campaign_registration,
    dispatch_extraction_job,
)

logger = logging.getLogger(__name__)

# campaign_type -> active template lookup candidates.
# Prefer english `code`, but keep legacy Korean names as fallback.
_CAMPAIGN_TEMPLATE_CANDIDATES = {
    "traffic": ("traffic", "트래픽"),
    "save": ("save", "저장하기"),
    "landmark": ("landmark", "명소"),
    "share_directions_traffic": ("share_directions_traffic", "공유+길찾기+트래픽"),
    "traffic1": ("traffic1", "트래픽1"),
    "save1": ("save1", "저장하기1"),
}


async def start_pipeline_for_order(
    db: AsyncSession,
    order: Order,
    actor_id: object | None = None,
    actor_name: str | None = None,
) -> None:
    """Start the pipeline after payment confirmation.

    PHASE 3: Items now stay in payment_confirmed state waiting for deadline.
    The scheduler will move them to extraction_queued when deadline passes.
    If product has no daily_deadline or setup_delay_minutes=0, process immediately.

    Monthly guarantee / managed orders skip the full pipeline.
    """
    if actor_id is not None or actor_name is not None:
        logger.info(
            "Starting pipeline for order %s by actor_id=%s actor_name=%s",
            order.id,
            actor_id,
            actor_name,
        )

    # Skip pipeline for no-revenue order types (manual account assignment)
    if order.order_type in (OrderType.MONTHLY_GUARANTEE.value, OrderType.MANAGED.value):
        order.status = OrderStatus.PROCESSING.value
        order.updated_at = datetime.now(timezone.utc)
        await db.flush()
        logger.info(
            "Order %s (%s) set to processing (manual completion required)",
            order.id, order.order_type,
        )
        return

    items = order.items
    if not items:
        logger.warning("Order %s has no items, skipping pipeline start", order.id)
        return

    for item in items:
        try:
            await _start_pipeline_for_item(db, item, order)
        except Exception:
            logger.exception(
                "Pipeline start failed for order_item %s (order %s)",
                item.id,
                order.id,
            )

    order.status = OrderStatus.PROCESSING.value
    await db.flush()


async def complete_managed_order(db: AsyncSession, order_id: int) -> None:
    """Complete a monthly_guarantee or managed order manually."""
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise ValueError(f"Order {order_id} not found")
    if order.order_type not in (OrderType.MONTHLY_GUARANTEE.value, OrderType.MANAGED.value):
        raise ValueError(
            f"Order {order_id} is type '{order.order_type}', not monthly_guarantee or managed"
        )
    if order.status != OrderStatus.PROCESSING.value:
        raise ValueError(f"Order {order_id} is not in processing status (current: {order.status})")
    order.status = OrderStatus.COMPLETED.value
    order.completed_at = datetime.now(timezone.utc)
    await db.flush()
    logger.info("Order %s (%s) manually completed", order_id, order.order_type)


def _get_template_candidates(campaign_type: str) -> tuple[str, ...]:
    candidates = list(_CAMPAIGN_TEMPLATE_CANDIDATES.get(campaign_type, (campaign_type,)))
    if campaign_type not in candidates:
        candidates.insert(0, campaign_type)

    unique_candidates: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in unique_candidates:
            unique_candidates.append(candidate)
    return tuple(unique_candidates)


async def _get_active_template(
    db: AsyncSession,
    campaign_type: str,
) -> CampaignTemplate | None:
    for candidate in _get_template_candidates(campaign_type):
        result = await db.execute(
            select(CampaignTemplate)
            .where(
                CampaignTemplate.code == candidate,
                CampaignTemplate.is_active == True,
            )
            .limit(1)
        )
        template = result.scalar_one_or_none()
        if template is not None:
            return template

    for candidate in _get_template_candidates(campaign_type):
        result = await db.execute(
            select(CampaignTemplate)
            .where(
                CampaignTemplate.type_name == candidate,
                CampaignTemplate.is_active == True,
            )
            .limit(1)
        )
        template = result.scalar_one_or_none()
        if template is not None:
            return template

    return None


async def _start_pipeline_for_item(
    db: AsyncSession, item: OrderItem, order: Order
) -> None:
    """Start pipeline for a single order item.

    PHASE 3: Creates pipeline state at payment_confirmed.
    If setup_delay_minutes=0, immediately queues for extraction.
    Otherwise, waits for scheduler to trigger queue transition.
    """
    # Duplicate prevention: skip if pipeline already exists for this item
    existing = await pipeline_service.get_pipeline_state(db, item.id)
    if existing:
        logger.info("Pipeline already exists for item %s (stage=%s), skipping", item.id, existing.current_stage)
        return

    state = await pipeline_service.create_pipeline_state(
        db, item.id, initial_stage="payment_confirmed"
    )

    # Check if product requires delay
    product = await db.get(Product, item.product_id)
    should_delay = (
        product is not None
        and product.setup_delay_minutes
        and product.setup_delay_minutes > 0
    )

    if should_delay:
        # PHASE 3: Stay at payment_confirmed, scheduler will advance later
        logger.info(
            "OrderItem %s will wait for deadline trigger (delay=%d min)",
            item.id,
            product.setup_delay_minutes,
        )
        return

    # No delay — immediately proceed to extraction
    await _advance_to_extraction(db, item, state)


async def _advance_to_extraction(
    db: AsyncSession, item: OrderItem, state: PipelineState
) -> None:
    """Move an item from payment_confirmed to extraction_queued.

    NOTE: This only creates DB records (extraction_job + pipeline state).
    The actual dispatch to keyword-worker must happen AFTER db.commit()
    to avoid race conditions (keyword-worker can't see uncommitted records).
    Use dispatch_pending_extraction_jobs() after committing.
    """
    place_url = _extract_place_url(item)
    if not place_url:
        await pipeline_service.transition_stage(
            db,
            state=state,
            to_stage="cancelled",
            trigger_type="validation_error",
            error_message="item_data에 place_url이 없습니다. 수동 설정이 필요합니다.",
        )
        logger.warning(
            "OrderItem %s has no place_url in item_data, pipeline cancelled",
            item.id,
        )
        return

    item_data = item.item_data or {}
    target_count = item_data.get("target_count", 200)
    max_rank = item_data.get("max_rank", 20)
    min_rank = item_data.get("min_rank", 1)
    name_keyword_ratio = item_data.get("name_keyword_ratio", 0.30)

    job = await extraction_service.create_job(
        db,
        ExtractionJobCreate(
            naver_url=place_url,
            order_item_id=item.id,
            target_count=target_count,
            max_rank=max_rank,
            min_rank=min_rank,
            name_keyword_ratio=name_keyword_ratio,
        ),
    )

    await pipeline_service.transition_stage(
        db,
        state=state,
        to_stage="extraction_queued",
        trigger_type="auto_extraction_dispatch",
        message=f"Extraction job {job.id} created",
    )
    state.extraction_job_id = job.id
    await db.flush()
    logger.info("Extraction job %s created for item %s (dispatch after commit)", job.id, item.id)


async def dispatch_pending_extraction_jobs(db: AsyncSession) -> None:
    """Dispatch all extraction_queued jobs to keyword-worker.

    Must be called AFTER db.commit() so keyword-worker can see the records.
    Only dispatches jobs still in 'queued' status (skips running/completed/failed).
    The keyword-worker handles re-dispatch gracefully (re-queues existing queued jobs).
    """
    result = await db.execute(
        select(PipelineState).where(
            PipelineState.current_stage == "extraction_queued",
        )
    )
    states = list(result.scalars().all())

    for state in states:
        if not state.extraction_job_id:
            continue

        ej_result = await db.execute(
            select(ExtractionJob).where(ExtractionJob.id == state.extraction_job_id)
        )
        ej = ej_result.scalar_one_or_none()
        if not ej or ej.status != "queued":
            continue

        try:
            await dispatch_extraction_job(
                job_id=ej.id,
                naver_url=ej.naver_url,
                order_item_id=ej.order_item_id,
                target_count=ej.target_count,
                max_rank=ej.max_rank,
                min_rank=ej.min_rank,
                name_keyword_ratio=ej.name_keyword_ratio,
            )
            logger.info("Dispatched extraction job %s to keyword-worker", ej.id)
        except WorkerDispatchError:
            logger.exception(
                "Failed to dispatch extraction job %s to keyword-worker (will be retried)",
                ej.id,
            )


async def check_and_queue_ready_items(db: AsyncSession) -> dict:
    """PHASE 3: Check for items past their deadline and queue them for extraction.

    Called periodically by the scheduler (every 5 minutes).
    """
    now = datetime.now(timezone.utc)
    queued = 0
    skipped = 0

    # Find pipeline states at payment_confirmed
    result = await db.execute(
        select(PipelineState).where(
            PipelineState.current_stage == "payment_confirmed",
        )
    )
    states = list(result.scalars().all())

    for state in states:
        try:
            item_result = await db.execute(
                select(OrderItem).where(OrderItem.id == state.order_item_id)
            )
            item = item_result.scalar_one_or_none()
            if item is None:
                skipped += 1
                continue

            product = await db.get(Product, item.product_id)
            if product is None:
                skipped += 1
                continue

            # Calculate queue time
            deadline_time = product.daily_deadline
            delay_minutes = product.setup_delay_minutes or 0

            # Use the product's timezone to interpret the deadline, then compare with UTC now
            tz = ZoneInfo(product.deadline_timezone or "Asia/Seoul")
            today_in_tz = now.astimezone(tz).date()
            deadline_today = datetime.combine(
                today_in_tz, deadline_time, tzinfo=tz
            )
            queue_time = deadline_today + timedelta(minutes=delay_minutes)

            if now >= queue_time:
                await _advance_to_extraction(db, item, state)
                queued += 1
            else:
                skipped += 1

        except Exception:
            logger.exception(
                "Error checking pipeline state %s for deadline trigger",
                state.id,
            )
            skipped += 1

    await db.flush()
    return {"queued": queued, "skipped": skipped, "total_checked": len(states)}


async def on_extraction_complete(
    db: AsyncSession,
    order_item_id: int,
    extraction_job: ExtractionJob,
) -> None:
    """Handle extraction completion: trigger auto-assignment.

    PHASE 4: No longer auto-dispatches extensions. Waits at account_assigned
    for user choice (new/extend) via on_assignment_choice().
    """
    result = await db.execute(
        select(OrderItem).where(OrderItem.id == order_item_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        logger.error("OrderItem %s not found for auto-assignment", order_item_id)
        return

    order_result = await db.execute(
        select(Order).where(Order.id == item.order_id)
    )
    order = order_result.scalar_one_or_none()
    if order is None:
        logger.error("Order not found for OrderItem %s", order_item_id)
        return

    state = await pipeline_service.get_pipeline_state(db, order_item_id)
    if state is None:
        logger.error("PipelineState not found for OrderItem %s", order_item_id)
        return

    item_data = item.item_data or {}
    campaign_type = item_data.get("campaign_type", "traffic")

    if extraction_job.place_id and not item.place_id:
        item.place_id = extraction_job.place_id
        await db.flush()

    place_id = item.place_id
    if not place_id:
        state.error_message = "No place_id available after extraction"
        await db.flush()
        logger.warning(
            "OrderItem %s has no place_id after extraction, manual assignment needed",
            order_item_id,
        )
        return

    total_limit = item_data.get("total_limit")

    if order.company_id is None:
        state.error_message = "Order has no company_id, cannot auto-assign"
        await db.flush()
        logger.warning(
            "OrderItem %s order has no company_id, skipping auto-assignment",
            order_item_id,
        )
        return

    try:
        assignment_result = await assignment_service.auto_assign(
            db,
            order_item=item,
            campaign_type=campaign_type,
            place_id=place_id,
            company_id=order.company_id,
            total_limit=total_limit,
        )
    except Exception:
        state.error_message = "Auto-assignment failed"
        await db.flush()
        logger.exception(
            "Auto-assignment failed for OrderItem %s",
            order_item_id,
        )
        return

    if assignment_result.assigned_account_id:
        try:
            await pipeline_service.transition_stage(
                db,
                state=state,
                to_stage="account_assigned",
                trigger_type="auto_assignment",
                message=f"Auto-assigned to account {assignment_result.assigned_account_id}",
            )
        except ValueError:
            logger.warning(
                "Pipeline transition to account_assigned failed for item %s",
                order_item_id,
            )
            return

        # Auto-proceed: determine new vs extend and dispatch immediately
        action = "extend" if assignment_result.is_extension else "new"
        logger.info(
            "OrderItem %s auto-proceeding with action=%s (is_extension=%s)",
            order_item_id,
            action,
            assignment_result.is_extension,
        )
        try:
            await on_assignment_choice(db, order_item_id, action)
        except Exception:
            logger.exception(
                "Auto assignment choice failed for OrderItem %s (action=%s)",
                order_item_id,
                action,
            )
    else:
        suggestion = assignment_result.suggestion or assignment_result.error or "No account available"
        state.error_message = f"Auto-assignment: {suggestion}"
        await db.flush()
        logger.info(
            "Auto-assignment could not assign OrderItem %s: %s",
            order_item_id,
            suggestion,
        )


async def on_assignment_choice(
    db: AsyncSession, order_item_id: int, action: str
) -> None:
    """PHASE 4: Handle user's new/extend choice after assignment confirmation.

    action="new": Create new campaign and dispatch registration.
    action="extend": Dispatch campaign extension to existing campaign.
    """
    result = await db.execute(
        select(OrderItem).where(OrderItem.id == order_item_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise ValueError(f"OrderItem {order_item_id} not found")

    order_result = await db.execute(
        select(Order).where(Order.id == item.order_id)
    )
    order = order_result.scalar_one_or_none()
    if order is None:
        raise ValueError(f"Order not found for OrderItem {order_item_id}")

    state = await pipeline_service.get_pipeline_state(db, order_item_id)
    if state is None:
        raise ValueError(f"PipelineState not found for OrderItem {order_item_id}")

    item_data = item.item_data or {}
    campaign_type = item_data.get("campaign_type", "traffic")

    if action == "extend":
        # Find the extension target
        if item.place_id:
            extension = await assignment_service._check_extension(
                db,
                place_id=item.place_id,
                campaign_type=campaign_type,
                new_total=item_data.get("total_limit"),
            )
            if extension and extension[1]:  # is_extend = True
                existing_campaign = extension[0]
                try:
                    duration_days = item_data.get("duration_days", 30)
                    new_end = (date.today() + timedelta(days=duration_days)).isoformat()
                    additional_total = item_data.get("total_limit", 3000)

                    await dispatch_campaign_extension(
                        campaign_id=existing_campaign.id,
                        new_end_date=new_end,
                        additional_total=additional_total,
                    )

                    await pipeline_service.transition_stage(
                        db, state=state,
                        to_stage="assignment_confirmed",
                        trigger_type="user_choice_extend",
                        message="Extension chosen by user",
                    )
                    state.campaign_id = existing_campaign.id
                    await pipeline_service.transition_stage(
                        db, state=state,
                        to_stage="campaign_registering",
                        trigger_type="user_choice_extend",
                        message=f"Extension dispatched for campaign {existing_campaign.id}",
                    )
                    logger.info(
                        "Extension dispatched for OrderItem %s → Campaign %s",
                        order_item_id, existing_campaign.id,
                    )
                    return
                except Exception as e:
                    logger.error("Extension dispatch failed for item %s: %s", order_item_id, e)
                    raise

        # Fallback: if extension not available, treat as new
        logger.warning(
            "Extend target not found for item %s, falling back to new campaign",
            order_item_id,
        )
        # Record the fallback in the pipeline log
        fallback_log = PipelineLog(
            pipeline_state_id=state.id,
            from_stage=state.current_stage,
            to_stage=state.current_stage,
            trigger_type="extend_fallback",
            message="연장 대상 캠페인을 찾을 수 없어 신규 세팅으로 전환되었습니다.",
        )
        db.add(fallback_log)
        await db.flush()

    # action == "new" (or extend fallback)
    await on_assignment_confirmed(db, order_item_id)


async def on_assignment_confirmed(
    db: AsyncSession, order_item_id: int
) -> None:
    """Handle assignment confirmation: create campaign and queue registration state.

    Actual worker dispatch happens after commit in the router layer to avoid
    race conditions with campaign-worker reading uncommitted rows.
    """
    result = await db.execute(
        select(OrderItem).where(OrderItem.id == order_item_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        logger.error("OrderItem %s not found for campaign creation", order_item_id)
        return

    order_result = await db.execute(
        select(Order).where(Order.id == item.order_id)
    )
    order = order_result.scalar_one_or_none()
    if order is None:
        logger.error("Order not found for OrderItem %s", order_item_id)
        return

    state = await pipeline_service.get_pipeline_state(db, order_item_id)
    if state is None:
        logger.error("PipelineState not found for OrderItem %s", order_item_id)
        return

    try:
        await pipeline_service.transition_stage(
            db,
            state=state,
            to_stage="assignment_confirmed",
            trigger_type="user_action",
            message="Assignment confirmed by admin",
        )
    except ValueError:
        logger.warning(
            "Pipeline transition to assignment_confirmed failed for item %s "
            "(current stage: %s)",
            order_item_id,
            state.current_stage,
        )
        return

    extraction_job = None
    if state.extraction_job_id:
        ej_result = await db.execute(
            select(ExtractionJob).where(ExtractionJob.id == state.extraction_job_id)
        )
        extraction_job = ej_result.scalar_one_or_none()

    item_data = item.item_data or {}
    place_url = _extract_place_url(item) or ""
    place_name = item_data.get("place_name") or ""
    if extraction_job and extraction_job.place_name:
        place_name = extraction_job.place_name

    campaign_type = item_data.get("campaign_type", "traffic")
    daily_limit = item_data.get("daily_limit", 300)
    total_limit = item_data.get("total_limit")
    start_date = _parse_start_date(item_data)
    end_days = item_data.get("duration_days", 30)
    end_date = start_date + timedelta(days=end_days)

    template = await _get_active_template(db, campaign_type)
    template_id = template.id if template else None

    keywords: list[str] = []
    if extraction_job and extraction_job.results:
        keywords = _extract_keywords_from_results(extraction_job.results)
    original_keywords = ",".join(keywords) if keywords else None

    # Resolve network_preset_id from the assigned account
    network_preset_id = None
    if item.assigned_account_id:
        acc = await superap_account_service.get_account_by_id(db, item.assigned_account_id)
        if acc:
            network_preset_id = acc.network_preset_id

    campaign = await campaign_service.create_campaign(
        db,
        CampaignCreate(
            order_item_id=order_item_id,
            place_id=item.place_id,
            place_url=place_url,
            place_name=place_name,
            campaign_type=campaign_type,
            start_date=start_date,
            end_date=end_date,
            daily_limit=daily_limit,
            total_limit=total_limit,
            superap_account_id=item.assigned_account_id,
            network_preset_id=network_preset_id,
            company_id=order.company_id,
            template_id=template_id,
            original_keywords=original_keywords,
            managed_by=item.assigned_by,
        ),
    )

    if extraction_job:
        campaign.extraction_job_id = extraction_job.id

    if keywords:
        await campaign_service.add_keywords_to_pool(db, campaign.id, keywords)

    state.campaign_id = campaign.id
    await db.flush()

    try:
        await pipeline_service.transition_stage(
            db,
            state=state,
            to_stage="campaign_registering",
            trigger_type="auto_campaign_register",
            message=f"Campaign {campaign.id} created, awaiting registration dispatch",
        )
    except ValueError:
        logger.warning(
            "Pipeline transition to campaign_registering failed for item %s",
            order_item_id,
        )


async def retry_stuck_pipelines(db: AsyncSession) -> dict:
    """Find pipelines stuck for >5 minutes and retry, up to 3 times."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)

    stuck_stages = ["extraction_queued", "campaign_registering"]
    result = await db.execute(
        select(PipelineState).where(
            PipelineState.current_stage.in_(stuck_stages),
            PipelineState.updated_at < cutoff,
        )
    )
    stuck_states = list(result.scalars().all())

    retried = 0
    skipped = 0

    for state in stuck_states:
        retry_count = 0
        if state.error_message and "retry_count:" in state.error_message:
            try:
                retry_count = int(state.error_message.split("retry_count:")[1].split()[0])
            except (ValueError, IndexError):
                pass

        if retry_count >= 3:
            skipped += 1
            continue

        try:
            if state.current_stage == "extraction_queued" and state.extraction_job_id:
                ej_result = await db.execute(
                    select(ExtractionJob).where(ExtractionJob.id == state.extraction_job_id)
                )
                ej = ej_result.scalar_one_or_none()
                if ej:
                    await dispatch_extraction_job(
                        job_id=ej.id,
                        naver_url=ej.naver_url,
                        order_item_id=ej.order_item_id,
                        target_count=ej.target_count,
                        max_rank=ej.max_rank,
                        min_rank=ej.min_rank,
                        name_keyword_ratio=ej.name_keyword_ratio,
                    )
            elif state.current_stage == "campaign_registering" and state.campaign_id:
                await dispatch_campaign_registration(campaign_id=state.campaign_id)

            state.error_message = f"retry_count:{retry_count + 1} Retried at {datetime.now(timezone.utc).isoformat()}"
            state.updated_at = datetime.now(timezone.utc)
            retried += 1
        except WorkerDispatchError:
            logger.warning("Retry dispatch failed for pipeline state %s", state.id)
            skipped += 1

    await db.flush()
    return {"retried": retried, "skipped": skipped, "total_stuck": len(stuck_states)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_start_date(item_data: dict | None) -> date:
    """Extract start_date from item_data, defaulting to today."""
    if item_data and item_data.get("start_date"):
        try:
            return date.fromisoformat(str(item_data["start_date"]))
        except (ValueError, TypeError):
            pass
    return date.today()


def _extract_place_url(item: OrderItem) -> str | None:
    """Extract place_url from OrderItem.item_data."""
    if not item.item_data:
        return None
    return item.item_data.get("place_url")


def _extract_keywords_from_results(results: list | dict | None) -> list[str]:
    """Extract keyword strings from extraction job results."""
    if not results:
        return []

    keywords: list[str] = []

    if isinstance(results, list):
        for entry in results:
            if isinstance(entry, str):
                keywords.append(entry)
            elif isinstance(entry, dict) and "keyword" in entry:
                keywords.append(entry["keyword"])

    return keywords

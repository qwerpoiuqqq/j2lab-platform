"""APScheduler setup for api-server.

PHASE 3: Runs periodic jobs:
  - check_and_queue_ready_items: every 5 minutes, moves payment_confirmed items
    past their deadline to extraction_queued.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

_scheduler = None


async def start_scheduler() -> None:
    """Start the APScheduler background scheduler."""
    global _scheduler

    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
    except ImportError:
        logger.warning(
            "apscheduler not installed, deadline trigger scheduler disabled. "
            "Install with: pip install apscheduler"
        )
        return

    _scheduler = AsyncIOScheduler()

    _scheduler.add_job(
        _run_deadline_check,
        "interval",
        minutes=5,
        id="deadline_check",
        name="Check deadline and queue ready items",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("Deadline check scheduler started (interval: 5 minutes)")


async def stop_scheduler() -> None:
    """Shutdown the scheduler gracefully."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Deadline check scheduler stopped")


async def _run_deadline_check() -> None:
    """Run the deadline check job within a DB session.

    Two-phase approach (same as confirm-payment background task):
    Phase 1: Create extraction records and COMMIT
    Phase 2: Dispatch to keyword-worker (after commit so worker can see records)
    """
    from app.core.database import async_session_factory
    from app.services.pipeline_orchestrator import (
        check_and_queue_ready_items,
        dispatch_pending_extraction_jobs,
    )

    # Phase 1: Create records and commit
    queued_count = 0
    try:
        async with async_session_factory() as db:
            result = await check_and_queue_ready_items(db)
            queued_count = result["queued"]
            await db.commit()
            if queued_count > 0:
                logger.info(
                    "Deadline check: queued=%d, skipped=%d, checked=%d",
                    result["queued"],
                    result["skipped"],
                    result["total_checked"],
                )
    except Exception:
        logger.exception("Deadline check job failed (phase 1: record creation)")
        return

    # Phase 2: Dispatch extraction jobs (AFTER commit)
    # Always attempt dispatch so already-queued jobs are not left behind.
    try:
        async with async_session_factory() as db:
            await dispatch_pending_extraction_jobs(db)
    except Exception:
        logger.exception("Deadline check job failed (phase 2: dispatch)")

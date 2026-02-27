"""Worker HTTP clients: api-server -> keyword-worker / campaign-worker.

Uses httpx.AsyncClient for non-blocking HTTP calls to worker services.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class WorkerDispatchError(Exception):
    """Raised when a worker dispatch call fails."""

    def __init__(self, worker: str, message: str):
        self.worker = worker
        super().__init__(f"[{worker}] {message}")


def _client() -> httpx.AsyncClient:
    """Create a one-shot async client with standard timeouts."""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0),
    )


# ---------------------------------------------------------------------------
# Keyword Worker
# ---------------------------------------------------------------------------

async def dispatch_extraction_job(
    job_id: int,
    naver_url: str,
    target_count: int = 100,
    max_rank: int = 50,
    min_rank: int = 1,
    name_keyword_ratio: float = 0.30,
    order_item_id: int | None = None,
) -> dict[str, Any]:
    """Dispatch an extraction job to keyword-worker.

    POST {KEYWORD_WORKER_URL}/internal/jobs
    Matches keyword-worker CreateJobRequest schema.
    """
    url = f"{settings.KEYWORD_WORKER_URL}/internal/jobs"
    payload = {
        "job_id": job_id,
        "naver_url": naver_url,
        "target_count": target_count,
        "max_rank": max_rank,
        "min_rank": min_rank,
        "name_keyword_ratio": name_keyword_ratio,
        "order_item_id": order_item_id,
    }
    try:
        async with _client() as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError as exc:
        logger.error("Keyword worker dispatch failed: %s", exc)
        raise WorkerDispatchError("keyword", str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        logger.error("Keyword worker returned %s: %s", exc.response.status_code, exc.response.text)
        raise WorkerDispatchError("keyword", f"HTTP {exc.response.status_code}") from exc


async def get_extraction_job_status(job_id: int) -> dict[str, Any]:
    """Get extraction job status from keyword-worker."""
    url = f"{settings.KEYWORD_WORKER_URL}/internal/jobs/{job_id}/status"
    try:
        async with _client() as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError as exc:
        logger.error("Keyword worker status check failed: %s", exc)
        raise WorkerDispatchError("keyword", str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise WorkerDispatchError("keyword", f"HTTP {exc.response.status_code}") from exc


async def cancel_extraction_job(job_id: int) -> dict[str, Any]:
    """Cancel an extraction job on keyword-worker."""
    url = f"{settings.KEYWORD_WORKER_URL}/internal/jobs/{job_id}/cancel"
    try:
        async with _client() as client:
            resp = await client.post(url)
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError as exc:
        logger.error("Keyword worker cancel failed: %s", exc)
        raise WorkerDispatchError("keyword", str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise WorkerDispatchError("keyword", f"HTTP {exc.response.status_code}") from exc


# ---------------------------------------------------------------------------
# Campaign Worker
# ---------------------------------------------------------------------------

async def dispatch_campaign_registration(
    campaign_id: int,
    account_id: int | None = None,
    template_id: int | None = None,
) -> dict[str, Any]:
    """Dispatch campaign registration to campaign-worker.

    POST {CAMPAIGN_WORKER_URL}/internal/campaigns/register
    Matches campaign-worker RegisterCampaignRequest schema.
    """
    url = f"{settings.CAMPAIGN_WORKER_URL}/internal/campaigns/register"
    payload: dict[str, Any] = {"campaign_id": campaign_id}
    if account_id is not None:
        payload["account_id"] = account_id
    if template_id is not None:
        payload["template_id"] = template_id

    try:
        async with _client() as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError as exc:
        logger.error("Campaign worker dispatch failed: %s", exc)
        raise WorkerDispatchError("campaign", str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        logger.error("Campaign worker returned %s: %s", exc.response.status_code, exc.response.text)
        raise WorkerDispatchError("campaign", f"HTTP {exc.response.status_code}") from exc


async def dispatch_campaign_extension(
    campaign_id: int,
    new_end_date: str,
    additional_total: int,
    new_daily_limit: int | None = None,
) -> dict[str, Any]:
    """Dispatch campaign extension to campaign-worker."""
    url = f"{settings.CAMPAIGN_WORKER_URL}/internal/campaigns/{campaign_id}/extend"
    payload: dict[str, Any] = {
        "new_end_date": new_end_date,
        "additional_total": additional_total,
    }
    if new_daily_limit is not None:
        payload["new_daily_limit"] = new_daily_limit

    try:
        async with _client() as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError as exc:
        logger.error("Campaign worker extension failed: %s", exc)
        raise WorkerDispatchError("campaign", str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise WorkerDispatchError("campaign", f"HTTP {exc.response.status_code}") from exc


async def dispatch_keyword_rotation(
    campaign_id: int,
) -> dict[str, Any]:
    """Dispatch keyword rotation for a campaign to campaign-worker."""
    url = f"{settings.CAMPAIGN_WORKER_URL}/internal/campaigns/{campaign_id}/rotate-keywords"
    try:
        async with _client() as client:
            resp = await client.post(url)
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError as exc:
        logger.error("Campaign worker keyword rotation failed: %s", exc)
        raise WorkerDispatchError("campaign", str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise WorkerDispatchError("campaign", f"HTTP {exc.response.status_code}") from exc


async def get_campaign_worker_scheduler_status() -> dict[str, Any]:
    """Get scheduler status from campaign-worker."""
    url = f"{settings.CAMPAIGN_WORKER_URL}/internal/scheduler/status"
    try:
        async with _client() as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError as exc:
        logger.error("Campaign worker scheduler status check failed: %s", exc)
        raise WorkerDispatchError("campaign", str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise WorkerDispatchError("campaign", f"HTTP {exc.response.status_code}") from exc


async def trigger_campaign_worker_scheduler() -> dict[str, Any]:
    """Manually trigger scheduler on campaign-worker."""
    url = f"{settings.CAMPAIGN_WORKER_URL}/internal/scheduler/trigger"
    try:
        async with _client() as client:
            resp = await client.post(url)
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError as exc:
        logger.error("Campaign worker scheduler trigger failed: %s", exc)
        raise WorkerDispatchError("campaign", str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise WorkerDispatchError("campaign", f"HTTP {exc.response.status_code}") from exc


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

async def check_worker_health(
    worker: Literal["keyword", "campaign"],
) -> dict[str, Any]:
    """Check worker health status."""
    if worker == "keyword":
        url = f"{settings.KEYWORD_WORKER_URL}/internal/health"
    else:
        url = f"{settings.CAMPAIGN_WORKER_URL}/internal/health"

    try:
        async with _client() as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError as exc:
        logger.error("%s worker health check failed: %s", worker, exc)
        raise WorkerDispatchError(worker, str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise WorkerDispatchError(worker, f"HTTP {exc.response.status_code}") from exc

"""Tests for worker HTTP clients (mock transport)."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from app.services.worker_clients import (
    WorkerDispatchError,
    cancel_extraction_job,
    check_worker_health,
    dispatch_campaign_registration,
    dispatch_campaign_extension,
    dispatch_extraction_job,
    get_extraction_job_status,
)


def _mock_client(handler):
    """Create a mock httpx.AsyncClient with a custom handler."""
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport)


# ---------------------------------------------------------------------------
# dispatch_extraction_job
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestDispatchExtractionJob:

    async def test_success(self):
        def handler(request: httpx.Request):
            assert "/internal/jobs" in str(request.url)
            import json
            body = json.loads(request.content)
            assert body["job_id"] == 42
            assert body["naver_url"] == "https://map.naver.com/p/entry/place/123"
            return httpx.Response(200, json={"job_id": 42, "status": "queued", "message": "ok"})

        with patch("app.services.worker_clients._client", return_value=_mock_client(handler)):
            result = await dispatch_extraction_job(
                job_id=42,
                naver_url="https://map.naver.com/p/entry/place/123",
                target_count=100,
                order_item_id=10,
            )
        assert result["job_id"] == 42
        assert result["status"] == "queued"

    async def test_http_error(self):
        def handler(request: httpx.Request):
            return httpx.Response(500, text="Internal Server Error")

        with patch("app.services.worker_clients._client", return_value=_mock_client(handler)):
            with pytest.raises(WorkerDispatchError, match="keyword"):
                await dispatch_extraction_job(
                    job_id=1,
                    naver_url="https://map.naver.com/p/entry/place/123",
                )

    async def test_connection_error(self):
        def handler(request: httpx.Request):
            raise httpx.ConnectError("Connection refused")

        with patch("app.services.worker_clients._client", return_value=_mock_client(handler)):
            with pytest.raises(WorkerDispatchError, match="keyword"):
                await dispatch_extraction_job(
                    job_id=1,
                    naver_url="https://map.naver.com/p/entry/place/123",
                )


# ---------------------------------------------------------------------------
# get_extraction_job_status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGetExtractionJobStatus:

    async def test_success(self):
        def handler(request: httpx.Request):
            assert "/internal/jobs/5/status" in str(request.url)
            return httpx.Response(200, json={"job_id": 5, "status": "running"})

        with patch("app.services.worker_clients._client", return_value=_mock_client(handler)):
            result = await get_extraction_job_status(5)
        assert result["status"] == "running"

    async def test_not_found(self):
        def handler(request: httpx.Request):
            return httpx.Response(404, text="Not found")

        with patch("app.services.worker_clients._client", return_value=_mock_client(handler)):
            with pytest.raises(WorkerDispatchError):
                await get_extraction_job_status(999)


# ---------------------------------------------------------------------------
# cancel_extraction_job
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestCancelExtractionJob:

    async def test_success(self):
        def handler(request: httpx.Request):
            assert "/cancel" in str(request.url)
            return httpx.Response(200, json={"message": "cancelled"})

        with patch("app.services.worker_clients._client", return_value=_mock_client(handler)):
            result = await cancel_extraction_job(3)
        assert result["message"] == "cancelled"


# ---------------------------------------------------------------------------
# dispatch_campaign_registration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestDispatchCampaignRegistration:

    async def test_success(self):
        def handler(request: httpx.Request):
            assert "/internal/campaigns/register" in str(request.url)
            import json
            body = json.loads(request.content)
            assert body["campaign_id"] == 10
            return httpx.Response(200, json={"campaign_id": 10, "status": "queued"})

        with patch("app.services.worker_clients._client", return_value=_mock_client(handler)):
            result = await dispatch_campaign_registration(
                campaign_id=10,
                account_id=5,
            )
        assert result["campaign_id"] == 10

    async def test_http_error(self):
        def handler(request: httpx.Request):
            return httpx.Response(503, text="Service Unavailable")

        with patch("app.services.worker_clients._client", return_value=_mock_client(handler)):
            with pytest.raises(WorkerDispatchError, match="campaign"):
                await dispatch_campaign_registration(campaign_id=1)


# ---------------------------------------------------------------------------
# dispatch_campaign_extension
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestDispatchCampaignExtension:

    async def test_success(self):
        def handler(request: httpx.Request):
            assert "/extend" in str(request.url)
            return httpx.Response(200, json={"message": "extended"})

        with patch("app.services.worker_clients._client", return_value=_mock_client(handler)):
            result = await dispatch_campaign_extension(
                campaign_id=7,
                new_end_date="2026-04-30",
                additional_total=5000,
                new_daily_limit=400,
            )
        assert result["message"] == "extended"


# ---------------------------------------------------------------------------
# check_worker_health
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestCheckWorkerHealth:

    async def test_keyword_health(self):
        def handler(request: httpx.Request):
            assert "/internal/health" in str(request.url)
            return httpx.Response(200, json={"status": "healthy"})

        with patch("app.services.worker_clients._client", return_value=_mock_client(handler)):
            result = await check_worker_health("keyword")
        assert result["status"] == "healthy"

    async def test_campaign_health(self):
        def handler(request: httpx.Request):
            return httpx.Response(200, json={"status": "healthy"})

        with patch("app.services.worker_clients._client", return_value=_mock_client(handler)):
            result = await check_worker_health("campaign")
        assert result["status"] == "healthy"

    async def test_unhealthy(self):
        def handler(request: httpx.Request):
            return httpx.Response(503, text="Unhealthy")

        with patch("app.services.worker_clients._client", return_value=_mock_client(handler)):
            with pytest.raises(WorkerDispatchError):
                await check_worker_health("keyword")

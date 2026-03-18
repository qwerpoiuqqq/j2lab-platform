"""Test fixtures for campaign-worker tests.

Provides mock database sessions, mock superap client, and sample data.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.database import Base, async_session_factory, engine
from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP client for API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_superap_client():
    """Provide a mock SuperapClient."""
    client = AsyncMock()
    client.initialize = AsyncMock()
    client.close = AsyncMock()
    client.login = AsyncMock(return_value=True)
    client.fill_campaign_form = AsyncMock(
        return_value=MagicMock(
            success=True,
            filled_fields=["campaign_type", "campaign_name", "participation_guide",
                          "keywords", "hint", "total_budget", "day_budget",
                          "start_date", "end_date"],
            errors=[],
            screenshot_path=None,
        )
    )
    client.submit_campaign = AsyncMock(
        return_value=MagicMock(
            success=True,
            campaign_code="12345",
            error_message=None,
        )
    )
    client.extract_campaign_code = AsyncMock(return_value="12345")
    client.edit_campaign_keywords = AsyncMock(return_value=True)
    client.edit_campaign = AsyncMock(return_value=True)
    client.get_campaign_status = AsyncMock(return_value="진행중")
    client.get_campaign_status_with_conversions = AsyncMock(
        return_value={
            "status": "진행중",
            "current_count": 150,
            "total_count": 300,
        }
    )
    client.close_context = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


@pytest.fixture
def sample_campaign_data():
    """Provide sample campaign data for tests."""
    return {
        "id": 1,
        "campaign_code": "12345",
        "superap_account_id": 1,
        "place_name": "일류곱창 마포공덕본점",
        "place_url": "https://m.place.naver.com/restaurant/1724563569",
        "campaign_type": "traffic",
        "start_date": date(2026, 3, 1),
        "end_date": date(2026, 3, 31),
        "daily_limit": 300,
        "total_limit": 9300,
        "status": "active",
        "original_keywords": "마포 곱창,공덕 곱창,마포역 곱창맛집,서울 곱창 맛집",
        "landmark_name": "마포역 2번 출구",
        "step_count": 350,
    }


@pytest.fixture
def sample_account_data():
    """Provide sample superap account data for tests."""
    return {
        "id": 1,
        "user_id_superap": "트래픽 제이투랩",
        "password_encrypted": "test_encrypted_password",
        "company_id": 1,
        "is_active": True,
    }


@pytest.fixture
def sample_template_data():
    """Provide sample campaign template data for tests."""
    return {
        "id": 1,
        "code": "traffic",
        "type_name": "트래픽",
        "description_template": (
            "1. 네이버에서 &상호명&을 검색합니다.\n"
            "2. &명소명& 근처 업체를 찾습니다.\n"
            "3. 정답을 입력합니다."
        ),
        "hint_text": "&place_name& 대표자명",
        "campaign_type_selection": "플레이스 퀴즈",
        "links": ["https://map.naver.com"],
        "modules": ["landmark", "steps"],
        "is_active": True,
    }


@pytest.fixture
def sample_keywords():
    """Provide sample keyword pool data for tests."""
    return [
        {"keyword": "마포 곱창", "is_used": False},
        {"keyword": "공덕 곱창", "is_used": False},
        {"keyword": "마포역 곱창맛집", "is_used": False},
        {"keyword": "서울 곱창 맛집", "is_used": True},
        {"keyword": "공덕역 맛집", "is_used": False},
        {"keyword": "마포구 곱창", "is_used": True},
        {"keyword": "신공덕 곱창", "is_used": False},
        {"keyword": "마포 대창", "is_used": False},
        {"keyword": "공덕동 맛집", "is_used": False},
        {"keyword": "서울 대창 맛집", "is_used": False},
    ]

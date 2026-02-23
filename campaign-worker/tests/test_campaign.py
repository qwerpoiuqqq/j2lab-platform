"""Tests for campaign-worker core functionality.

Tests are mock-based since Playwright automation requires
a real browser and superap.io access.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.superap_client import (
    CampaignFormData,
    CampaignFormResult,
    SubmitResult,
    resolve_campaign_type_value,
)
from app.services.campaign_registrar import (
    _generate_campaign_name,
    _mask_place_name,
    extract_place_id,
)
from app.utils.crypto import decrypt_password, encrypt_password
from app.utils.status_map import normalize_status, to_display_label
from app.utils.template_vars import apply_template_variables


# ============================================================
# Unit tests: utility functions
# ============================================================


class TestExtractPlaceId:
    """Tests for extract_place_id()."""

    def test_restaurant_url(self):
        url = "https://m.place.naver.com/restaurant/1724563569"
        assert extract_place_id(url) == "1724563569"

    def test_restaurant_with_home(self):
        url = "https://m.place.naver.com/restaurant/1724563569/home"
        assert extract_place_id(url) == "1724563569"

    def test_cafe_url(self):
        url = "https://place.naver.com/cafe/9876543210"
        assert extract_place_id(url) == "9876543210"

    def test_map_url(self):
        url = "https://map.naver.com/v5/entry/place/1724563569"
        assert extract_place_id(url) == "1724563569"

    def test_empty_url(self):
        assert extract_place_id("") is None
        assert extract_place_id(None) is None

    def test_invalid_url(self):
        assert extract_place_id("https://example.com") is None


class TestMaskPlaceName:
    """Tests for _mask_place_name()."""

    def test_basic_masking(self):
        result = _mask_place_name("일류곱창 마포공덕본점")
        assert result == "일X곱X 마X공X본X"

    def test_short_name(self):
        result = _mask_place_name("스벅")
        assert result == "스X"

    def test_empty_name(self):
        assert _mask_place_name("") == ""
        assert _mask_place_name(None) is None

    def test_single_char(self):
        result = _mask_place_name("A")
        assert result == "A"


class TestGenerateCampaignName:
    """Tests for _generate_campaign_name()."""

    def test_basic_name(self):
        result = _generate_campaign_name("일류곱창", "traffic")
        assert result == "일류 퀴즈 맞추기"

    def test_save_type(self):
        result = _generate_campaign_name("일류곱창", "저장하기")
        assert result == "일류 저장 퀴즈 맞추기"

    def test_branch_name(self):
        result = _generate_campaign_name("일류곱창 마포공덕본점", "traffic")
        assert result == "일류 마포 퀴즈 맞추기"

    def test_short_name(self):
        result = _generate_campaign_name("AB", "traffic")
        assert result == "A 퀴즈 맞추기"


class TestStatusMap:
    """Tests for status normalization."""

    def test_korean_to_english(self):
        assert normalize_status("진행중") == "active"
        assert normalize_status("일일소진") == "daily_exhausted"
        assert normalize_status("캠페인소진") == "campaign_exhausted"
        assert normalize_status("중단") == "deactivated"

    def test_already_english(self):
        assert normalize_status("active") == "active"
        assert normalize_status("pending") == "pending"

    def test_empty_status(self):
        assert normalize_status("") == "pending"

    def test_unknown_status(self):
        assert normalize_status("unknown") == "unknown"

    def test_display_label(self):
        assert to_display_label("active") == "진행중"
        assert to_display_label("daily_exhausted") == "일일소진"
        assert to_display_label("") == "대기중"


class TestTemplateVars:
    """Tests for template variable substitution."""

    def test_korean_vars(self):
        template = "네이버에서 &상호명&을 검색하세요."
        context = {"place_name": "일X곱X"}
        result = apply_template_variables(template, context)
        assert result == "네이버에서 일X곱X을 검색하세요."

    def test_landmark_var(self):
        template = "&명소명& 근처를 찾으세요."
        context = {"landmark_name": "마포역 2번 출구"}
        result = apply_template_variables(template, context)
        assert result == "마포역 2번 출구 근처를 찾으세요."

    def test_english_vars(self):
        template = "&place_name& is the place."
        context = {"place_name": "Test Place"}
        result = apply_template_variables(template, context)
        assert result == "Test Place is the place."

    def test_missing_var(self):
        template = "&missing_var& stays as is."
        context = {}
        result = apply_template_variables(template, context)
        assert result == "&missing_var& stays as is."

    def test_empty_template(self):
        assert apply_template_variables("", {}) == ""
        assert apply_template_variables(None, {}) == ""


class TestCrypto:
    """Tests for AES encryption/decryption."""

    def test_encrypt_decrypt_roundtrip(self):
        original = "test_password_123"
        encrypted = encrypt_password(original)
        decrypted = decrypt_password(encrypted)
        assert decrypted == original
        assert encrypted != original

    def test_decrypt_plaintext_legacy(self):
        """Legacy plaintext passwords should be returned as-is."""
        plain = "legacy_password"
        result = decrypt_password(plain)
        assert result == plain

    def test_decrypt_empty(self):
        assert decrypt_password("") == ""


class TestCampaignTypeSelection:
    """Tests for campaign type value resolution."""

    def test_korean_to_radio(self):
        assert resolve_campaign_type_value("플레이스 퀴즈") == "cpc_detail_place"

    def test_already_radio(self):
        assert resolve_campaign_type_value("cpc_detail_place") == "cpc_detail_place"

    def test_empty(self):
        assert resolve_campaign_type_value("") is None
        assert resolve_campaign_type_value(None) is None

    def test_unknown(self):
        assert resolve_campaign_type_value("unknown_type") is None


# ============================================================
# Unit tests: CampaignFormData
# ============================================================


class TestCampaignFormData:
    """Tests for CampaignFormData dataclass."""

    def test_keyword_processing(self):
        form = CampaignFormData(
            campaign_name="test",
            place_name="test place",
            landmark_name="test landmark",
            participation_guide="guide",
            keywords=["keyword1", "keyword2", "keyword3"],
            hint="hint",
        )
        # Should be comma-separated within 255 chars
        assert form.processed_keywords
        assert "," in form.processed_keywords or len(form.keywords) == 1

    def test_total_limit_auto_calc(self):
        form = CampaignFormData(
            campaign_name="test",
            place_name="test",
            landmark_name="",
            participation_guide="guide",
            keywords=["kw1"],
            hint="hint",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
            daily_limit=300,
        )
        # 31 days * 300 = 9300
        assert form.total_limit == 9300

    def test_place_name_masking(self):
        form = CampaignFormData(
            campaign_name="test",
            place_name="일류곱창",
            landmark_name="test",
            participation_guide="&상호명& 검색",
            keywords=["kw1"],
            hint="hint",
        )
        assert "일X곱X" in form.processed_guide

    def test_date_strings(self):
        form = CampaignFormData(
            campaign_name="test",
            place_name="test",
            landmark_name="",
            participation_guide="guide",
            keywords=["kw1"],
            hint="hint",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )
        assert form.get_start_date_str() == "2026-03-01 00:00:00"
        assert form.get_end_date_str() == "2026-03-31 23:59:59"


# ============================================================
# API endpoint tests (mock-based)
# ============================================================


@pytest_asyncio.fixture
async def test_client() -> AsyncClient:
    """Provide a test HTTP client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    @pytest.mark.asyncio
    async def test_health(self, test_client: AsyncClient):
        response = await test_client.get("/internal/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "J2LAB Campaign Worker"


class TestSchedulerEndpoint:
    """Tests for scheduler status endpoint."""

    @pytest.mark.asyncio
    async def test_scheduler_status(self, test_client: AsyncClient):
        response = await test_client.get("/internal/scheduler/status")
        assert response.status_code == 200
        data = response.json()
        assert "is_running" in data
        assert "scheduler_active" in data
        assert "run_count" in data


class TestRegisterEndpoint:
    """Tests for campaign registration endpoint."""

    @pytest.mark.asyncio
    async def test_register_campaign(self, test_client: AsyncClient):
        """Test that registration endpoint accepts the request and queues it."""
        with patch(
            "app.routers.internal.register_campaign",
            new_callable=AsyncMock,
        ) as mock_register:
            mock_register.return_value = {
                "success": True,
                "campaign_code": "12345",
            }

            response = await test_client.post(
                "/internal/campaigns/register",
                json={"campaign_id": 1},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["message"] == "Registration queued"


class TestExtendEndpoint:
    """Tests for campaign extension endpoint."""

    @pytest.mark.asyncio
    async def test_extend_campaign(self, test_client: AsyncClient):
        """Test that extension endpoint accepts the request and queues it."""
        with patch(
            "app.routers.internal.extend_campaign",
            new_callable=AsyncMock,
        ) as mock_extend:
            mock_extend.return_value = {
                "success": True,
                "new_total_limit": 18600,
            }

            response = await test_client.post(
                "/internal/campaigns/1/extend",
                json={
                    "new_end_date": "2026-04-30",
                    "additional_total": 9300,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["message"] == "Extension queued"


class TestBulkSyncEndpoint:
    """Tests for bulk sync endpoint."""

    @pytest.mark.asyncio
    async def test_bulk_sync(self, test_client: AsyncClient):
        """Test that bulk sync endpoint accepts the request."""
        with patch(
            "app.routers.internal.bulk_sync_campaigns",
            new_callable=AsyncMock,
        ) as mock_sync:
            mock_sync.return_value = {"success": True, "synced_count": 5}

            response = await test_client.post(
                "/internal/campaigns/bulk-sync",
                json={},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


class TestSchedulerTriggerEndpoint:
    """Tests for manual scheduler trigger endpoint."""

    @pytest.mark.asyncio
    async def test_trigger_scheduler(self, test_client: AsyncClient):
        """Test manual scheduler trigger."""
        with patch(
            "app.routers.internal.check_and_rotate_keywords",
            new_callable=AsyncMock,
        ) as mock_rotate:
            mock_rotate.return_value = {"rotated": 3}

            response = await test_client.post("/internal/scheduler/trigger")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"

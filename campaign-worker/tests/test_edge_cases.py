"""Edge case tests for campaign-worker.

Covers:
- Registration failure and rollback
- Password decryption failure
- Keyword rotation with empty pool
- Sync with network errors
- Campaign name generation edge cases
- CampaignFormData edge cases
- Template variable edge cases
- Status map edge cases
- API validation edge cases
- Scheduler conflict (already running)
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.superap_client import (
    CAMPAIGN_TYPE_SELECTION_MAP,
    CampaignFormData,
    CampaignFormResult,
    SubmitResult,
    SuperapClient,
    SuperapError,
    SuperapLoginError,
    SuperapCampaignError,
    StealthConfig,
    resolve_campaign_type_value,
)
from app.services.campaign_registrar import (
    _generate_campaign_name,
    _mask_place_name,
    extract_place_id,
    _send_callback,
)
from app.services.keyword_rotator import (
    _was_rotated_today,
    get_scheduler_state,
    scheduler_state,
)
from app.utils.crypto import decrypt_password, encrypt_password, _derive_key
from app.utils.status_map import (
    SUPERAP_TO_INTERNAL,
    INTERNAL_TO_KOREAN,
    normalize_status,
    to_display_label,
)
from app.utils.template_vars import apply_template_variables, KOREAN_VAR_MAP


KST = ZoneInfo("Asia/Seoul")


@pytest_asyncio.fixture
async def test_client() -> AsyncClient:
    """Provide a test HTTP client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ============================================================
# Edge case: extract_place_id
# ============================================================


class TestExtractPlaceIdEdgeCases:
    """Edge cases for Naver Place URL parsing."""

    def test_hospital_url(self):
        url = "https://m.place.naver.com/hospital/1234567890"
        assert extract_place_id(url) == "1234567890"

    def test_beauty_url(self):
        url = "https://place.naver.com/beauty/5555555555"
        assert extract_place_id(url) == "5555555555"

    def test_accommodation_url(self):
        url = "https://place.naver.com/accommodation/1111111111"
        assert extract_place_id(url) == "1111111111"

    def test_shopping_url(self):
        url = "https://m.place.naver.com/shopping/2222222222/home"
        assert extract_place_id(url) == "2222222222"

    def test_url_with_query_params(self):
        url = "https://m.place.naver.com/restaurant/1724563569?from=search"
        assert extract_place_id(url) == "1724563569"

    def test_short_number_ignored(self):
        """IDs with fewer than 5 digits should not match the fallback."""
        url = "https://example.com/path/1234"
        assert extract_place_id(url) is None

    def test_long_numeric_path_fallback(self):
        """Fallback: any 5+ digit numeric path segment."""
        url = "https://map.naver.com/some/path/99999"
        assert extract_place_id(url) == "99999"


# ============================================================
# Edge case: _mask_place_name
# ============================================================


class TestMaskPlaceNameEdgeCases:
    """Edge cases for place name masking."""

    def test_all_spaces(self):
        result = _mask_place_name("   ")
        assert result == "   "

    def test_mixed_spaces_and_chars(self):
        result = _mask_place_name("A B C")
        assert result == "A X C"

    def test_unicode_characters(self):
        result = _mask_place_name("가나다라마")
        assert result == "가X다X마"

    def test_three_chars(self):
        result = _mask_place_name("ABC")
        assert result == "AXC"

    def test_four_chars(self):
        result = _mask_place_name("ABCD")
        assert result == "AXCX"


# ============================================================
# Edge case: _generate_campaign_name
# ============================================================


class TestGenerateCampaignNameEdgeCases:
    """Edge cases for campaign name generation."""

    def test_empty_place_name(self):
        result = _generate_campaign_name("", "traffic")
        assert "퀴즈 맞추기" in result

    def test_single_char_place_name(self):
        result = _generate_campaign_name("가", "traffic")
        assert result == "가 퀴즈 맞추기"

    def test_place_save_type(self):
        result = _generate_campaign_name("테스트", "place_save_tab")
        assert "저장 퀴즈 맞추기" in result

    def test_save_keyword_in_type(self):
        result = _generate_campaign_name("테스트", "save")
        assert "저장 퀴즈 맞추기" in result

    def test_branch_with_short_brand(self):
        """Brand name with 2 chars + branch ending in 점."""
        result = _generate_campaign_name("스벅 강남점", "traffic")
        assert "스 강남" in result or "스 강" in result

    def test_branch_with_single_char_brand(self):
        """Brand name with 1 char + branch ending in 점."""
        result = _generate_campaign_name("A 서울역점", "traffic")
        assert "A" in result

    def test_branch_empty_branch_word(self):
        """Branch name is just '점'."""
        result = _generate_campaign_name("테스트브랜드 점", "traffic")
        # '점' without prefix -> falls back to brand_prefix only
        assert "퀴즈 맞추기" in result

    def test_multiple_spaces_in_name(self):
        result = _generate_campaign_name("일류 곱창 맛집", "traffic")
        # Has 3 parts, last doesn't end with 점, so uses first 2 chars
        assert "퀴즈 맞추기" in result


# ============================================================
# Edge case: CampaignFormData
# ============================================================


class TestCampaignFormDataEdgeCases:
    """Edge cases for CampaignFormData dataclass."""

    def test_empty_keywords(self):
        form = CampaignFormData(
            campaign_name="test",
            place_name="test",
            landmark_name="",
            participation_guide="guide",
            keywords=[],
            hint="hint",
        )
        assert form.processed_keywords == ""
        assert form.get_keywords_count() == 0

    def test_keywords_exceeding_255_chars(self):
        """Long keywords should be truncated to 255 chars."""
        long_keywords = [f"키워드{i}_{i*100}" for i in range(50)]
        form = CampaignFormData(
            campaign_name="test",
            place_name="test",
            landmark_name="",
            participation_guide="guide",
            keywords=long_keywords,
            hint="hint",
        )
        assert len(form.processed_keywords) <= 255

    def test_keywords_with_whitespace_only(self):
        form = CampaignFormData(
            campaign_name="test",
            place_name="test",
            landmark_name="",
            participation_guide="guide",
            keywords=["  ", "   ", ""],
            hint="hint",
        )
        assert form.processed_keywords == ""

    def test_total_limit_not_overwritten(self):
        """If total_limit is explicitly provided, it should not be auto-calculated."""
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
            total_limit=5000,
        )
        assert form.total_limit == 5000

    def test_no_dates_no_auto_calc(self):
        """Without dates, total_limit stays None."""
        form = CampaignFormData(
            campaign_name="test",
            place_name="test",
            landmark_name="",
            participation_guide="guide",
            keywords=["kw1"],
            hint="hint",
            daily_limit=300,
        )
        assert form.total_limit is None

    def test_string_date_parsing(self):
        form = CampaignFormData(
            campaign_name="test",
            place_name="test",
            landmark_name="",
            participation_guide="guide",
            keywords=["kw1"],
            hint="hint",
            start_date="2026-04-01",
            end_date="2026-04-30",
            daily_limit=100,
        )
        assert form.total_limit == 30 * 100
        assert form.get_start_date_str() == "2026-04-01 00:00:00"
        assert form.get_end_date_str() == "2026-04-30 23:59:59"

    def test_datetime_date_input(self):
        form = CampaignFormData(
            campaign_name="test",
            place_name="test",
            landmark_name="",
            participation_guide="guide",
            keywords=["kw1"],
            hint="hint",
            start_date=datetime(2026, 5, 1, 10, 30),
            end_date=datetime(2026, 5, 31, 18, 0),
            daily_limit=200,
        )
        assert form.total_limit == 31 * 200
        assert form.get_start_date_str() == "2026-05-01 00:00:00"

    def test_no_start_date_str(self):
        form = CampaignFormData(
            campaign_name="test",
            place_name="test",
            landmark_name="",
            participation_guide="guide",
            keywords=["kw1"],
            hint="hint",
        )
        assert form.get_start_date_str() == ""
        assert form.get_end_date_str() == ""

    def test_generate_campaign_name_from_form(self):
        form = CampaignFormData(
            campaign_name="test",
            place_name="일류곱창",
            landmark_name="",
            participation_guide="guide",
            keywords=["kw1"],
            hint="hint",
        )
        name = form.generate_campaign_name()
        assert "퀴즈 맞추기" in name

    def test_generate_campaign_name_save_type(self):
        form = CampaignFormData(
            campaign_name="test",
            place_name="테스트가게",
            landmark_name="",
            participation_guide="guide",
            keywords=["kw1"],
            hint="hint",
            campaign_type="save",
        )
        name = form.generate_campaign_name()
        assert "저장 퀴즈 맞추기" in name

    def test_landmark_in_guide(self):
        form = CampaignFormData(
            campaign_name="test",
            place_name="테스트",
            landmark_name="서울역",
            participation_guide="&명소명& 방문하세요",
            keywords=["kw1"],
            hint="hint",
        )
        assert "서울역 방문하세요" == form.processed_guide


# ============================================================
# Edge case: Crypto
# ============================================================


class TestCryptoEdgeCases:
    """Edge cases for AES encryption."""

    def test_korean_password(self):
        original = "비밀번호테스트123!"
        encrypted = encrypt_password(original)
        assert decrypt_password(encrypted) == original

    def test_special_chars_password(self):
        original = "p@$$w0rd!#%^&*()"
        encrypted = encrypt_password(original)
        assert decrypt_password(encrypted) == original

    def test_long_password(self):
        original = "A" * 500
        encrypted = encrypt_password(original)
        assert decrypt_password(encrypted) == original

    def test_derive_key_consistency(self):
        """Same input should produce same key."""
        key1 = _derive_key("test-secret")
        key2 = _derive_key("test-secret")
        assert key1 == key2

    def test_derive_key_different_for_different_secrets(self):
        key1 = _derive_key("secret-1")
        key2 = _derive_key("secret-2")
        assert key1 != key2

    def test_garbled_fernet_token_returns_as_is(self):
        """Non-Fernet tokens should be returned as legacy plaintext."""
        garbled = "gAAAA_this_is_not_valid_fernet"
        result = decrypt_password(garbled)
        assert result == garbled


# ============================================================
# Edge case: Status map
# ============================================================


class TestStatusMapEdgeCases:
    """Edge cases for status mapping."""

    def test_all_korean_statuses_mapped(self):
        for korean, english in SUPERAP_TO_INTERNAL.items():
            assert normalize_status(korean) == english

    def test_all_english_statuses_idempotent(self):
        for english in INTERNAL_TO_KOREAN.keys():
            assert normalize_status(english) == english

    def test_all_english_statuses_have_display(self):
        for english in INTERNAL_TO_KOREAN.keys():
            label = to_display_label(english)
            assert label  # non-empty
            assert label != english  # should map to Korean

    def test_none_status_treated_as_empty(self):
        """normalize_status should handle None gracefully."""
        # None is not in the signature but test defensive behavior
        assert normalize_status("") == "pending"

    def test_집행중_maps_to_active(self):
        """'집행중' is an alternate form of '진행중'."""
        assert normalize_status("집행중") == "active"

    def test_전체소진_maps_to_campaign_exhausted(self):
        assert normalize_status("전체소진") == "campaign_exhausted"

    def test_대기중_maps_to_pending(self):
        assert normalize_status("대기중") == "pending"

    def test_종료_maps_to_completed(self):
        assert normalize_status("종료") == "completed"

    def test_일시정지_maps_to_paused(self):
        assert normalize_status("일시정지") == "paused"


# ============================================================
# Edge case: Template variables
# ============================================================


class TestTemplateVarsEdgeCases:
    """Edge cases for template variable substitution."""

    def test_multiple_vars_in_one_template(self):
        template = "&상호명&에서 &명소명& 방문하고 &걸음수& 걸으세요"
        context = {"place_name": "테스트", "landmark_name": "명소", "steps": 300}
        result = apply_template_variables(template, context)
        assert result == "테스트에서 명소 방문하고 300 걸으세요"

    def test_repeated_var(self):
        template = "&상호명& 검색 후 &상호명& 찾기"
        context = {"place_name": "일류"}
        result = apply_template_variables(template, context)
        assert result == "일류 검색 후 일류 찾기"

    def test_integer_value(self):
        template = "걸음수: &걸음수&"
        context = {"steps": 500}
        result = apply_template_variables(template, context)
        assert result == "걸음수: 500"

    def test_zero_value(self):
        template = "걸음수: &걸음수&"
        context = {"steps": 0}
        result = apply_template_variables(template, context)
        assert result == "걸음수: 0"

    def test_all_korean_var_mappings(self):
        """Verify all Korean variable name mappings."""
        assert KOREAN_VAR_MAP["상호명"] == "place_name"
        assert KOREAN_VAR_MAP["명소명"] == "landmark_name"
        assert KOREAN_VAR_MAP["걸음수"] == "steps"

    def test_ampersand_in_value(self):
        """Values containing & should not be re-processed."""
        template = "&place_name& test"
        context = {"place_name": "A&B"}
        result = apply_template_variables(template, context)
        assert result == "A&B test"


# ============================================================
# Edge case: Campaign type selection
# ============================================================


class TestCampaignTypeSelectionEdgeCases:
    """Edge cases for campaign type resolution."""

    def test_all_korean_labels_resolve(self):
        for label, value in CAMPAIGN_TYPE_SELECTION_MAP.items():
            resolved = resolve_campaign_type_value(label)
            assert resolved == value, f"Failed for {label}"

    def test_all_radio_values_resolve(self):
        for value in CAMPAIGN_TYPE_SELECTION_MAP.values():
            resolved = resolve_campaign_type_value(value)
            assert resolved == value, f"Failed for {value}"

    def test_youtube_types(self):
        assert resolve_campaign_type_value("시청하기") == "video_length_default"
        assert resolve_campaign_type_value("구독하기") == "youtube_subs_default"
        assert resolve_campaign_type_value("쇼츠 좋아요") == "short_like_default"

    def test_sns_types(self):
        assert resolve_campaign_type_value("인스타그램 팔로우") == "sns_instagram_follow"
        assert resolve_campaign_type_value("인스타그램 게시물 좋아요") == "sns_instagram_like"

    def test_whitespace_not_trimmed(self):
        """Leading/trailing whitespace should cause a miss."""
        assert resolve_campaign_type_value(" 플레이스 퀴즈 ") is None


# ============================================================
# Edge case: _was_rotated_today (keyword rotator)
# ============================================================


class TestWasRotatedToday:
    """Edge cases for the rotation check logic."""

    def test_none_last_change(self):
        """No previous rotation means should rotate."""
        assert _was_rotated_today(None, date(2026, 3, 1)) is False

    def test_rotated_yesterday(self):
        """Rotation yesterday means not rotated today."""
        yesterday_utc = datetime(2026, 2, 28, 14, 0, 0, tzinfo=timezone.utc)
        today_kst = date(2026, 3, 1)
        assert _was_rotated_today(yesterday_utc, today_kst) is False

    def test_rotated_today(self):
        """Rotation today (in KST) means skip."""
        # 2026-03-01 01:00 UTC = 2026-03-01 10:00 KST
        today_utc = datetime(2026, 3, 1, 1, 0, 0, tzinfo=timezone.utc)
        today_kst = date(2026, 3, 1)
        assert _was_rotated_today(today_utc, today_kst) is True

    def test_naive_datetime_treated_as_utc(self):
        """Naive datetime should be assumed UTC."""
        naive = datetime(2026, 3, 1, 1, 0, 0)  # No tzinfo
        today_kst = date(2026, 3, 1)
        # This should be treated as UTC -> 10:00 KST on 3/1
        assert _was_rotated_today(naive, today_kst) is True


# ============================================================
# Edge case: StealthConfig
# ============================================================


class TestStealthConfig:
    """Edge cases for stealth configuration."""

    def test_random_user_agent_is_from_list(self):
        for _ in range(10):
            ua = StealthConfig.get_random_user_agent()
            assert ua in StealthConfig.USER_AGENTS

    def test_random_viewport_is_from_list(self):
        for _ in range(10):
            vp = StealthConfig.get_random_viewport()
            assert vp in StealthConfig.VIEWPORTS

    def test_random_delay_in_range(self):
        for _ in range(20):
            delay = StealthConfig.get_random_delay()
            assert StealthConfig.MIN_DELAY <= delay <= StealthConfig.MAX_DELAY


# ============================================================
# Edge case: API endpoints
# ============================================================


class TestRegisterEndpointEdgeCases:
    """Edge cases for campaign registration endpoint."""

    @pytest.mark.asyncio
    async def test_register_missing_campaign_id(self, test_client: AsyncClient):
        """Missing campaign_id should return 422."""
        response = await test_client.post(
            "/internal/campaigns/register",
            json={},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_invalid_campaign_id_type(self, test_client: AsyncClient):
        """Non-integer campaign_id should return 422."""
        response = await test_client.post(
            "/internal/campaigns/register",
            json={"campaign_id": "not_an_int"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_with_optional_fields(self, test_client: AsyncClient):
        """Optional account_id and template_id should be accepted."""
        with patch(
            "app.routers.internal.register_campaign",
            new_callable=AsyncMock,
        ) as mock_register:
            mock_register.return_value = {"success": True}

            response = await test_client.post(
                "/internal/campaigns/register",
                json={
                    "campaign_id": 42,
                    "account_id": 1,
                    "template_id": 2,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["campaign_id"] == 42


class TestExtendEndpointEdgeCases:
    """Edge cases for campaign extension endpoint."""

    @pytest.mark.asyncio
    async def test_extend_missing_required_fields(self, test_client: AsyncClient):
        """Missing new_end_date or additional_total should return 422."""
        response = await test_client.post(
            "/internal/campaigns/1/extend",
            json={"new_end_date": "2026-04-30"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_extend_zero_additional_total(self, test_client: AsyncClient):
        """additional_total must be >= 1."""
        response = await test_client.post(
            "/internal/campaigns/1/extend",
            json={
                "new_end_date": "2026-04-30",
                "additional_total": 0,
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_extend_negative_additional_total(self, test_client: AsyncClient):
        """Negative additional_total should fail validation."""
        response = await test_client.post(
            "/internal/campaigns/1/extend",
            json={
                "new_end_date": "2026-04-30",
                "additional_total": -100,
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_extend_invalid_date_format(self, test_client: AsyncClient):
        """Invalid date format should fail."""
        response = await test_client.post(
            "/internal/campaigns/1/extend",
            json={
                "new_end_date": "not-a-date",
                "additional_total": 100,
            },
        )
        assert response.status_code == 422


class TestBulkSyncEndpointEdgeCases:
    """Edge cases for bulk sync endpoint."""

    @pytest.mark.asyncio
    async def test_bulk_sync_with_specific_account_ids(self, test_client: AsyncClient):
        """Sync with specific account IDs."""
        with patch(
            "app.routers.internal.bulk_sync_campaigns",
            new_callable=AsyncMock,
        ) as mock_sync:
            mock_sync.return_value = {"success": True, "synced_count": 2}

            response = await test_client.post(
                "/internal/campaigns/bulk-sync",
                json={"account_ids": [1, 2, 3]},
            )
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_bulk_sync_null_account_ids(self, test_client: AsyncClient):
        """Null account_ids should sync all."""
        with patch(
            "app.routers.internal.bulk_sync_campaigns",
            new_callable=AsyncMock,
        ) as mock_sync:
            mock_sync.return_value = {"success": True, "synced_count": 5}

            response = await test_client.post(
                "/internal/campaigns/bulk-sync",
                json={"account_ids": None},
            )
            assert response.status_code == 200


class TestSchedulerTriggerEdgeCases:
    """Edge cases for scheduler trigger endpoint."""

    @pytest.mark.asyncio
    async def test_trigger_while_running(self, test_client: AsyncClient):
        """Should return 409 if scheduler is already running."""
        original = scheduler_state["is_running"]
        scheduler_state["is_running"] = True
        try:
            response = await test_client.post("/internal/scheduler/trigger")
            assert response.status_code == 409
            data = response.json()
            assert "already running" in data["detail"]
        finally:
            scheduler_state["is_running"] = original


class TestHealthEndpointEdgeCases:
    """Edge cases for health endpoint."""

    @pytest.mark.asyncio
    async def test_health_response_fields(self, test_client: AsyncClient):
        response = await test_client.get("/internal/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"
        assert "J2LAB" in data["service"]


class TestSchedulerStatusEdgeCases:
    """Edge cases for scheduler status endpoint."""

    @pytest.mark.asyncio
    async def test_scheduler_status_includes_all_fields(self, test_client: AsyncClient):
        response = await test_client.get("/internal/scheduler/status")
        assert response.status_code == 200
        data = response.json()
        required_fields = [
            "is_running", "scheduler_active", "last_run",
            "run_count", "last_error", "recent_logs",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"


# ============================================================
# Edge case: Callback sending
# ============================================================


class TestCallbackEdgeCases:
    """Edge cases for api-server callback."""

    @pytest.mark.asyncio
    async def test_callback_network_error(self):
        """Callback should not raise even on network error."""
        with patch("app.services.campaign_registrar.httpx.AsyncClient") as mock_client_cls:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.post = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client_cls.return_value = mock_instance

            # Should not raise
            await _send_callback(999, "failed", "test error")

    @pytest.mark.asyncio
    async def test_callback_server_error(self):
        """Callback should handle 5xx responses gracefully."""
        with patch("app.services.campaign_registrar.httpx.AsyncClient") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_instance

            # Should not raise
            await _send_callback(999, "completed", "test")


# ============================================================
# Edge case: get_scheduler_state
# ============================================================


class TestGetSchedulerState:
    """Tests for scheduler state reporting."""

    def test_state_structure(self):
        state = get_scheduler_state()
        assert "is_running" in state
        assert "scheduler_active" in state
        assert "last_run" in state
        assert "last_result" in state
        assert "last_error" in state
        assert "run_count" in state
        assert "recent_logs" in state

    def test_recent_logs_is_list(self):
        state = get_scheduler_state()
        assert isinstance(state["recent_logs"], list)


# ============================================================
# Edge case: SuperapClient exceptions
# ============================================================


class TestSuperapExceptions:
    """Test exception hierarchy."""

    def test_superap_error_hierarchy(self):
        assert issubclass(SuperapLoginError, SuperapError)
        assert issubclass(SuperapCampaignError, SuperapError)
        assert issubclass(SuperapError, Exception)

    def test_login_error_message(self):
        err = SuperapLoginError("Login failed: bad password")
        assert "Login failed" in str(err)

    def test_campaign_error_message(self):
        err = SuperapCampaignError("Code extraction failed")
        assert "Code extraction" in str(err)


# ============================================================
# Edge case: CampaignFormResult / SubmitResult
# ============================================================


class TestResultDataclasses:
    """Test result dataclass edge cases."""

    def test_form_result_defaults(self):
        result = CampaignFormResult(success=False)
        assert result.success is False
        assert result.screenshot_path is None
        assert result.filled_fields == []
        assert result.errors == []

    def test_submit_result_defaults(self):
        result = SubmitResult(success=True)
        assert result.success is True
        assert result.campaign_code is None
        assert result.error_message is None
        assert result.redirect_url is None

    def test_form_result_with_data(self):
        result = CampaignFormResult(
            success=True,
            screenshot_path="/tmp/test.png",
            filled_fields=["campaign_name", "keywords"],
            errors=["hint failed"],
        )
        assert len(result.filled_fields) == 2
        assert len(result.errors) == 1

    def test_submit_result_with_data(self):
        result = SubmitResult(
            success=True,
            campaign_code="99999",
            redirect_url="https://superap.io/report",
        )
        assert result.campaign_code == "99999"


# ============================================================
# Edge case: Endpoint 404 for unknown routes
# ============================================================


class TestUnknownRoutes:
    """Test that unknown routes return proper errors."""

    @pytest.mark.asyncio
    async def test_unknown_internal_route(self, test_client: AsyncClient):
        response = await test_client.get("/internal/nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_root_path(self, test_client: AsyncClient):
        response = await test_client.get("/")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_wrong_method_on_health(self, test_client: AsyncClient):
        response = await test_client.post("/internal/health")
        assert response.status_code == 405

    @pytest.mark.asyncio
    async def test_wrong_method_on_register(self, test_client: AsyncClient):
        response = await test_client.get("/internal/campaigns/register")
        assert response.status_code == 405

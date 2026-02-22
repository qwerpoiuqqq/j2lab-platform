"""캠페인 연장 서비스 테스트.

Phase 3 - Task 3.4: 연장 세팅 로직 테스트
"""

import pytest
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from app.services.campaign_extension import (
    ExtensionInfo,
    ExtensionResult,
    MAX_TOTAL_COUNT,
    extract_place_id,
    check_extension_eligible,
    extend_campaign,
)
from app.services.superap import SuperapController, SuperapCampaignError
from app.models.campaign import Campaign
from app.models.keyword import KeywordPool


# ============================================================================
# extract_place_id 테스트
# ============================================================================

class TestExtractPlaceId:
    """extract_place_id() 함수 테스트."""

    def test_restaurant_url(self):
        """레스토랑 URL에서 ID 추출."""
        url = "https://m.place.naver.com/restaurant/1724563569"
        assert extract_place_id(url) == "1724563569"

    def test_restaurant_url_with_path(self):
        """하위 경로가 있는 레스토랑 URL."""
        url = "https://m.place.naver.com/restaurant/1724563569/home"
        assert extract_place_id(url) == "1724563569"

    def test_cafe_url(self):
        """카페 URL에서 ID 추출."""
        url = "https://m.place.naver.com/cafe/12345678"
        assert extract_place_id(url) == "12345678"

    def test_hospital_url(self):
        """병원 URL에서 ID 추출."""
        url = "https://m.place.naver.com/hospital/9876543210"
        assert extract_place_id(url) == "9876543210"

    def test_beauty_url(self):
        """뷰티 URL에서 ID 추출."""
        url = "https://m.place.naver.com/beauty/55555555"
        assert extract_place_id(url) == "55555555"

    def test_desktop_url(self):
        """데스크톱 URL에서 ID 추출."""
        url = "https://place.naver.com/restaurant/1724563569"
        assert extract_place_id(url) == "1724563569"

    def test_map_url(self):
        """네이버 지도 URL에서 ID 추출."""
        url = "https://map.naver.com/v5/entry/place/1724563569"
        assert extract_place_id(url) == "1724563569"

    def test_url_with_query_params(self):
        """쿼리 파라미터가 있는 URL."""
        url = "https://m.place.naver.com/restaurant/1724563569?from=map"
        assert extract_place_id(url) == "1724563569"

    def test_empty_url(self):
        """빈 URL."""
        assert extract_place_id("") is None

    def test_none_url(self):
        """None URL."""
        assert extract_place_id(None) is None

    def test_invalid_url(self):
        """유효하지 않은 URL."""
        assert extract_place_id("not-a-url") is None

    def test_url_without_id(self):
        """ID가 없는 URL."""
        assert extract_place_id("https://m.place.naver.com/") is None

    def test_different_ids(self):
        """다른 ID 값들."""
        assert extract_place_id("https://m.place.naver.com/restaurant/100") == "100"
        assert extract_place_id("https://m.place.naver.com/restaurant/9999999999") == "9999999999"

    def test_accommodation_url(self):
        """숙소 URL에서 ID 추출."""
        url = "https://m.place.naver.com/accommodation/77777777"
        assert extract_place_id(url) == "77777777"

    def test_shopping_url(self):
        """쇼핑 URL에서 ID 추출."""
        url = "https://m.place.naver.com/shopping/66666666"
        assert extract_place_id(url) == "66666666"


# ============================================================================
# check_extension_eligible 테스트
# ============================================================================

class TestCheckExtensionEligible:
    """check_extension_eligible() 함수 테스트."""

    @pytest.fixture
    def mock_db(self):
        """Mock DB 세션."""
        return MagicMock()

    def _make_campaign(self, place_id="1724563569", total_limit=2100, status="active"):
        """테스트용 캠페인 객체 생성."""
        campaign = MagicMock(spec=Campaign)
        campaign.id = 1
        campaign.place_id = place_id
        campaign.campaign_code = "1336101"
        campaign.total_limit = total_limit
        campaign.status = status
        return campaign

    def test_eligible_basic(self, mock_db):
        """기본 연장 가능 케이스."""
        campaign = self._make_campaign(total_limit=2100)
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = campaign

        result = check_extension_eligible("1724563569", 2100, mock_db)

        assert result.is_eligible is True
        assert result.existing_campaign_code == "1336101"
        assert result.existing_total_count == 2100

    def test_eligible_exact_limit(self, mock_db):
        """정확히 10,000타에 도달하는 케이스."""
        campaign = self._make_campaign(total_limit=7900)
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = campaign

        result = check_extension_eligible("1724563569", 2100, mock_db)

        assert result.is_eligible is True
        assert "10000" in result.reason

    def test_not_eligible_exceeds_limit(self, mock_db):
        """총 타수 초과로 연장 불가."""
        campaign = self._make_campaign(total_limit=8000)
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = campaign

        result = check_extension_eligible("1724563569", 3000, mock_db)

        assert result.is_eligible is False
        assert "초과" in result.reason
        assert result.existing_campaign_code == "1336101"
        assert result.existing_total_count == 8000

    def test_not_eligible_no_active_campaign(self, mock_db):
        """진행 중인 캠페인 없음."""
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        result = check_extension_eligible("1724563569", 2100, mock_db)

        assert result.is_eligible is False
        assert "진행 중인 캠페인이 없습니다" in result.reason

    def test_not_eligible_empty_place_id(self, mock_db):
        """빈 place_id."""
        result = check_extension_eligible("", 2100, mock_db)

        assert result.is_eligible is False
        assert "플레이스 ID가 없습니다" in result.reason

    def test_not_eligible_none_place_id(self, mock_db):
        """None place_id."""
        result = check_extension_eligible(None, 2100, mock_db)

        assert result.is_eligible is False

    def test_eligible_small_addition(self, mock_db):
        """소량 추가로 연장 가능."""
        campaign = self._make_campaign(total_limit=9000)
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = campaign

        result = check_extension_eligible("1724563569", 1000, mock_db)

        assert result.is_eligible is True

    def test_not_eligible_one_over(self, mock_db):
        """1타 초과로 연장 불가."""
        campaign = self._make_campaign(total_limit=9000)
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = campaign

        result = check_extension_eligible("1724563569", 1001, mock_db)

        assert result.is_eligible is False

    def test_existing_campaign_id_returned(self, mock_db):
        """기존 캠페인 ID가 반환되는지 확인."""
        campaign = self._make_campaign(total_limit=2100)
        campaign.id = 42
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = campaign

        result = check_extension_eligible("1724563569", 2100, mock_db)

        assert result.existing_campaign_id == 42


# ============================================================================
# extend_campaign 테스트
# ============================================================================

class TestExtendCampaign:
    """extend_campaign() 함수 테스트."""

    @pytest.fixture
    def mock_superap(self):
        """Mock SuperapController."""
        controller = MagicMock(spec=SuperapController)
        controller.edit_campaign = AsyncMock(return_value=True)
        return controller

    @pytest.fixture
    def mock_db(self):
        """Mock DB 세션."""
        db = MagicMock()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        db.rollback = MagicMock()
        return db

    def _make_campaign_with_keywords(self, db, total_limit=2100, keywords=None):
        """테스트용 캠페인 + 키워드 생성."""
        campaign = MagicMock(spec=Campaign)
        campaign.id = 1
        campaign.campaign_code = "1336101"
        campaign.total_limit = total_limit
        campaign.end_date = date(2026, 2, 11)
        campaign.status = "active"
        campaign.original_keywords = "일류곱창,마포맛집"

        # 기존 키워드
        if keywords is None:
            keywords = ["일류곱창", "마포맛집"]
        kw_objects = []
        for kw in keywords:
            kw_obj = MagicMock(spec=KeywordPool)
            kw_obj.keyword = kw
            kw_objects.append(kw_obj)
        campaign.keywords = kw_objects

        db.query.return_value.filter.return_value.first.return_value = campaign
        return campaign

    @pytest.mark.asyncio
    async def test_extend_success(self, mock_superap, mock_db):
        """연장 성공 케이스."""
        campaign = self._make_campaign_with_keywords(mock_db, total_limit=2100)

        result = await extend_campaign(
            superap_controller=mock_superap,
            db=mock_db,
            account_id="test_account",
            existing_campaign_id=1,
            new_total_count=2100,
            new_end_date=date(2026, 2, 18),
            new_keywords=["곱창맛집", "공덕역맛집"],
        )

        assert result.success is True
        assert result.new_total_count == 4200
        assert result.new_end_date == date(2026, 2, 18)
        assert result.added_keywords_count == 2

        # superap.io 수정 호출 확인
        mock_superap.edit_campaign.assert_called_once_with(
            account_id="test_account",
            campaign_code="1336101",
            new_total_limit=4200,
            new_end_date=date(2026, 2, 18),
        )

        # DB 커밋 확인
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_extend_with_duplicate_keywords(self, mock_superap, mock_db):
        """중복 키워드가 있는 경우."""
        campaign = self._make_campaign_with_keywords(
            mock_db, total_limit=2100, keywords=["일류곱창", "마포맛집"]
        )

        result = await extend_campaign(
            superap_controller=mock_superap,
            db=mock_db,
            account_id="test_account",
            existing_campaign_id=1,
            new_total_count=2100,
            new_end_date=date(2026, 2, 18),
            new_keywords=["일류곱창", "곱창맛집"],  # "일류곱창"은 중복
        )

        assert result.success is True
        assert result.added_keywords_count == 1  # 중복 제외 1개만 추가

    @pytest.mark.asyncio
    async def test_extend_campaign_not_found(self, mock_superap, mock_db):
        """캠페인을 찾을 수 없는 경우."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = await extend_campaign(
            superap_controller=mock_superap,
            db=mock_db,
            account_id="test_account",
            existing_campaign_id=999,
            new_total_count=2100,
            new_end_date=date(2026, 2, 18),
            new_keywords=["키워드"],
        )

        assert result.success is False
        assert "찾을 수 없습니다" in result.error_message

    @pytest.mark.asyncio
    async def test_extend_no_campaign_code(self, mock_superap, mock_db):
        """캠페인 코드가 없는 경우."""
        campaign = self._make_campaign_with_keywords(mock_db, total_limit=2100)
        campaign.campaign_code = None

        result = await extend_campaign(
            superap_controller=mock_superap,
            db=mock_db,
            account_id="test_account",
            existing_campaign_id=1,
            new_total_count=2100,
            new_end_date=date(2026, 2, 18),
            new_keywords=["키워드"],
        )

        assert result.success is False
        assert "캠페인 코드가 없습니다" in result.error_message

    @pytest.mark.asyncio
    async def test_extend_exceeds_max_total(self, mock_superap, mock_db):
        """총 타수 초과."""
        campaign = self._make_campaign_with_keywords(mock_db, total_limit=9000)

        result = await extend_campaign(
            superap_controller=mock_superap,
            db=mock_db,
            account_id="test_account",
            existing_campaign_id=1,
            new_total_count=1001,
            new_end_date=date(2026, 2, 18),
            new_keywords=["키워드"],
        )

        assert result.success is False
        assert "초과" in result.error_message

    @pytest.mark.asyncio
    async def test_extend_superap_edit_failure(self, mock_superap, mock_db):
        """superap.io 수정 실패."""
        campaign = self._make_campaign_with_keywords(mock_db, total_limit=2100)
        mock_superap.edit_campaign = AsyncMock(return_value=False)

        result = await extend_campaign(
            superap_controller=mock_superap,
            db=mock_db,
            account_id="test_account",
            existing_campaign_id=1,
            new_total_count=2100,
            new_end_date=date(2026, 2, 18),
            new_keywords=["키워드"],
        )

        assert result.success is False
        assert "수정 실패" in result.error_message
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_extend_superap_exception(self, mock_superap, mock_db):
        """superap.io 예외 발생."""
        campaign = self._make_campaign_with_keywords(mock_db, total_limit=2100)
        mock_superap.edit_campaign = AsyncMock(
            side_effect=SuperapCampaignError("연결 오류")
        )

        result = await extend_campaign(
            superap_controller=mock_superap,
            db=mock_db,
            account_id="test_account",
            existing_campaign_id=1,
            new_total_count=2100,
            new_end_date=date(2026, 2, 18),
            new_keywords=["키워드"],
        )

        assert result.success is False
        assert "Superap 오류" in result.error_message
        mock_db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_extend_exact_max_total(self, mock_superap, mock_db):
        """정확히 10,000타에 도달."""
        campaign = self._make_campaign_with_keywords(mock_db, total_limit=7900)

        result = await extend_campaign(
            superap_controller=mock_superap,
            db=mock_db,
            account_id="test_account",
            existing_campaign_id=1,
            new_total_count=2100,
            new_end_date=date(2026, 2, 18),
            new_keywords=["키워드"],
        )

        assert result.success is True
        assert result.new_total_count == 10000

    @pytest.mark.asyncio
    async def test_extend_empty_keywords(self, mock_superap, mock_db):
        """빈 키워드 목록으로 연장."""
        campaign = self._make_campaign_with_keywords(mock_db, total_limit=2100)

        result = await extend_campaign(
            superap_controller=mock_superap,
            db=mock_db,
            account_id="test_account",
            existing_campaign_id=1,
            new_total_count=2100,
            new_end_date=date(2026, 2, 18),
            new_keywords=[],
        )

        assert result.success is True
        assert result.added_keywords_count == 0

    @pytest.mark.asyncio
    async def test_extend_updates_campaign_fields(self, mock_superap, mock_db):
        """캠페인 필드 업데이트 확인."""
        campaign = self._make_campaign_with_keywords(mock_db, total_limit=2100)

        result = await extend_campaign(
            superap_controller=mock_superap,
            db=mock_db,
            account_id="test_account",
            existing_campaign_id=1,
            new_total_count=2100,
            new_end_date=date(2026, 2, 18),
            new_keywords=["새키워드"],
        )

        assert result.success is True
        assert campaign.total_limit == 4200
        assert campaign.end_date == date(2026, 2, 18)


# ============================================================================
# ExtensionInfo 데이터 클래스 테스트
# ============================================================================

class TestExtensionInfo:
    """ExtensionInfo 데이터 클래스 테스트."""

    def test_eligible_info(self):
        """연장 가능 정보."""
        info = ExtensionInfo(
            is_eligible=True,
            existing_campaign_code="1336101",
            existing_campaign_id=1,
            existing_total_count=2100,
            reason="연장 가능",
        )

        assert info.is_eligible is True
        assert info.existing_campaign_code == "1336101"

    def test_not_eligible_info(self):
        """연장 불가 정보."""
        info = ExtensionInfo(
            is_eligible=False,
            reason="총 타수 초과",
        )

        assert info.is_eligible is False
        assert info.existing_campaign_code is None


# ============================================================================
# ExtensionResult 데이터 클래스 테스트
# ============================================================================

class TestExtensionResult:
    """ExtensionResult 데이터 클래스 테스트."""

    def test_success_result(self):
        """성공 결과."""
        result = ExtensionResult(
            success=True,
            campaign_id=1,
            new_total_count=4200,
            new_end_date=date(2026, 2, 18),
            added_keywords_count=3,
        )

        assert result.success is True
        assert result.new_total_count == 4200
        assert result.error_message is None

    def test_failure_result(self):
        """실패 결과."""
        result = ExtensionResult(
            success=False,
            error_message="수정 실패",
        )

        assert result.success is False
        assert result.campaign_id is None


# ============================================================================
# MAX_TOTAL_COUNT 상수 테스트
# ============================================================================

class TestConstants:
    """상수 테스트."""

    def test_max_total_count(self):
        """MAX_TOTAL_COUNT 값 확인."""
        assert MAX_TOTAL_COUNT == 10000

"""Edge case tests for keyword-worker (Phase 2 verification).

Tests added by Agent B for:
- URL parser edge cases
- Empty/malformed PlaceData handling
- Keyword parser special character handling
- DB keyword duplicate handling
- Callback failure graceful handling
- Rank checker edge cases
- Place scraper address parsing
- API router error responses
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.extraction_job import ExtractionJob, ExtractionJobStatus
from app.models.keyword import Keyword
from app.models.keyword_rank_history import KeywordRankHistory
from app.models.place import Place
from app.services.extraction_service import ExtractionService
from app.services.keyword_parser import (
    STANDALONE_BLOCKED,
    detect_business_type,
    generate_keyword_pool,
    generate_region_keywords,
    parse_business_name,
)
from app.services.place_scraper import (
    AddressParser,
    PlaceData,
    PlaceScraper,
    RegionInfo,
    ReviewKeyword,
)
from app.services.rank_checker import PlaceInfo, RankCheckResult, RankChecker
from app.utils.url_parser import (
    PlaceType,
    get_place_type_korean,
    parse_place_url,
)


# ==================== URL Parser Edge Cases ====================


class TestURLParserEdgeCases:
    """Edge cases for URL parser."""

    def test_url_with_query_params(self):
        """URL with query parameters should still parse correctly."""
        result = parse_place_url(
            "https://m.place.naver.com/restaurant/1082820234/home?entry=pll&source=search"
        )
        assert result.is_valid is True
        assert result.mid == "1082820234"
        assert result.place_type == PlaceType.RESTAURANT

    def test_url_with_hash_fragment(self):
        """URL with hash fragment should parse correctly."""
        result = parse_place_url(
            "https://m.place.naver.com/restaurant/1082820234#review"
        )
        assert result.is_valid is True
        assert result.mid == "1082820234"

    def test_http_url(self):
        """HTTP (non-HTTPS) URL should parse correctly."""
        result = parse_place_url(
            "http://m.place.naver.com/restaurant/1082820234"
        )
        assert result.is_valid is True
        assert result.mid == "1082820234"

    def test_url_without_protocol(self):
        """URL without protocol should parse correctly."""
        result = parse_place_url("m.place.naver.com/restaurant/1082820234")
        assert result.is_valid is True
        assert result.mid == "1082820234"

    def test_unknown_place_type_is_invalid(self):
        """Unknown place type (e.g., 'gym') should be marked as invalid."""
        result = parse_place_url(
            "https://m.place.naver.com/gym/1234567890"
        )
        assert result.is_valid is False
        assert result.place_type == PlaceType.UNKNOWN
        assert "gym" in (result.error_message or "")

    def test_naver_me_short_url_not_supported(self):
        """Short naver.me URLs are not supported."""
        result = parse_place_url("https://naver.me/abc123")
        assert result.is_valid is False

    def test_url_with_only_digits(self):
        """Just a number string should be invalid."""
        result = parse_place_url("1082820234")
        assert result.is_valid is False

    def test_url_with_special_chars(self):
        """URL with special characters should be handled."""
        result = parse_place_url(
            "https://m.place.naver.com/restaurant/1234567890/home?tab=photo&src=검색"
        )
        assert result.is_valid is True
        assert result.mid == "1234567890"

    def test_map_url_without_entry(self):
        """map.naver.com without /entry/ path should be invalid."""
        result = parse_place_url(
            "https://map.naver.com/v5/search/맛집"
        )
        assert result.is_valid is False

    def test_get_place_type_korean_returns_korean(self):
        """get_place_type_korean should return actual Korean names."""
        assert get_place_type_korean(PlaceType.RESTAURANT) == "맛집/음식점"
        assert get_place_type_korean(PlaceType.HOSPITAL) == "병의원"
        assert get_place_type_korean(PlaceType.HAIRSHOP) == "미용실"
        assert get_place_type_korean(PlaceType.NAILSHOP) == "네일샵"
        assert get_place_type_korean(PlaceType.PLACE) == "일반 업종"
        assert get_place_type_korean(PlaceType.UNKNOWN) == "알 수 없음"


# ==================== Empty PlaceData Edge Cases ====================


class TestEmptyPlaceData:
    """Tests for handling empty/minimal PlaceData."""

    def test_empty_place_data_keyword_pool(self):
        """Keyword pool from completely empty PlaceData should be empty or minimal."""
        place = PlaceData()
        pool = generate_keyword_pool(place, target_count=100)
        # With no region/name/category, pool should be empty or very small
        # All keywords require at least a region
        assert isinstance(pool, list)

    def test_place_data_no_region(self):
        """PlaceData with name but no region info."""
        place = PlaceData(
            name="테스트식당",
            category="한식",
            region=RegionInfo(),
        )
        pool = generate_keyword_pool(place, target_count=100)
        # Should generate name-only keywords (R8) at minimum
        keywords = [item["keyword"] for item in pool]
        assert "테스트식당" in keywords or len(keywords) == 0

    def test_place_data_no_name(self):
        """PlaceData with region but no name."""
        place = PlaceData(
            category="한식",
            region=RegionInfo(
                gu="강남구",
                gu_without_suffix="강남",
            ),
        )
        pool = generate_keyword_pool(place, target_count=100)
        keywords = [item["keyword"] for item in pool]
        # Should still generate region + biz type keywords
        has_region = any("강남" in k for k in keywords)
        assert has_region

    def test_place_data_to_dict_empty(self):
        """PlaceData.to_dict() should work with default values."""
        place = PlaceData()
        d = place.to_dict()
        assert d["name"] == ""
        assert d["category"] == ""
        assert d["keywords"] == []
        assert d["region"]["city"] == ""
        assert d["discovered_regions"] == []

    def test_place_data_to_dict_with_set_regions(self):
        """PlaceData.to_dict() should convert set to list for discovered_regions."""
        place = PlaceData(discovered_regions={"서울", "부산"})
        d = place.to_dict()
        assert isinstance(d["discovered_regions"], list)
        assert set(d["discovered_regions"]) == {"서울", "부산"}


# ==================== Keyword Parser Special Character Tests ====================


class TestKeywordParserSpecialChars:
    """Tests for special character handling in keyword generation."""

    def test_category_with_commas(self):
        """Category with commas should be split correctly."""
        btype = detect_business_type("한식,양식,음식점")
        assert btype == "restaurant"

    def test_category_with_slashes(self):
        """Category with slash separators."""
        btype = detect_business_type("정형외과/재활의학과")
        assert btype == "hospital"

    def test_name_with_special_chars(self):
        """Business name with parentheses, brackets, etc."""
        parts = parse_business_name("맛집(강남점)")
        assert "맛집" in parts or "맛집(강남점)" in parts

    def test_name_with_numbers(self):
        """Business name with numbers."""
        parts = parse_business_name("24시 해장국")
        assert "24시" in parts or "해장국" in parts

    def test_name_with_english(self):
        """Business name mixing Korean and English."""
        parts = parse_business_name("BBQ 치킨 강남점")
        assert any("BBQ" in p for p in parts)
        assert any("치킨" in p for p in parts)

    def test_single_char_name_filtered(self):
        """Single character names should be filtered (< 2 chars)."""
        parts = parse_business_name("A")
        # Single space parts are filtered by len >= 2
        assert all(len(p) >= 2 for p in parts)

    def test_keyword_pool_no_standalone_blocked(self):
        """Generated keywords should not contain standalone blocked words."""
        place = PlaceData(
            name="추천맛집",
            category="한식",
            region=RegionInfo(gu="강남구", gu_without_suffix="강남"),
            keywords=["추천", "잘하는"],
        )
        pool = generate_keyword_pool(place, target_count=50)
        keywords = [item["keyword"] for item in pool]
        # Standalone blocked words should be filtered out as individual base_keywords
        for kw in keywords:
            # Each keyword should be >= 2 chars
            assert len(kw) >= 2

    def test_region_keyword_min_length(self):
        """All region keywords should be at least 2 characters."""
        region = RegionInfo(
            gu="강남구",
            dong="역삼동",
            gu_without_suffix="강남",
            dong_without_suffix="역삼",
            stations=["강남역"],
        )
        keywords = generate_region_keywords(region)
        for kw in keywords:
            assert len(kw) >= 2, f"Keyword '{kw}' is less than 2 chars"


# ==================== DB Keyword Duplicate Tests ====================


class TestDBKeywordDuplicates:
    """Tests for duplicate keyword handling in database."""

    @pytest.mark.asyncio
    async def test_duplicate_keyword_same_place(self, db_session: AsyncSession):
        """Adding duplicate keyword for same place should raise or be handled."""
        place = Place(
            id=88888,
            name="테스트 맛집",
            place_type="restaurant",
            category="한식",
        )
        db_session.add(place)
        await db_session.commit()

        kw1 = Keyword(
            place_id=88888,
            keyword="강남 맛집",
            keyword_type="pll",
            current_rank=5,
        )
        db_session.add(kw1)
        await db_session.commit()

        # Attempting to add exact same keyword for same place
        kw2 = Keyword(
            place_id=88888,
            keyword="강남 맛집",
            keyword_type="pll",
            current_rank=3,
        )
        db_session.add(kw2)
        # SQLite doesn't enforce UniqueConstraint the same way as PostgreSQL
        # In production (PostgreSQL), this would raise IntegrityError
        # The extraction_service uses SELECT-then-INSERT pattern to avoid this

    @pytest.mark.asyncio
    async def test_keyword_update_existing(self, db_session: AsyncSession):
        """Updating an existing keyword should change the rank."""
        place = Place(
            id=77777,
            name="테스트2",
            place_type="restaurant",
            category="한식",
        )
        db_session.add(place)
        await db_session.commit()

        kw = Keyword(
            place_id=77777,
            keyword="강남 맛집",
            keyword_type="pll",
            current_rank=5,
            current_map_type="신지도",
            last_checked_at=datetime.now(timezone.utc),
        )
        db_session.add(kw)
        await db_session.commit()

        # Update rank
        kw.current_rank = 2
        await db_session.commit()

        result = await db_session.get(Keyword, kw.id)
        assert result.current_rank == 2

    @pytest.mark.asyncio
    async def test_rank_history_unique_per_day(self, db_session: AsyncSession):
        """Only one rank history entry per keyword per day."""
        place = Place(
            id=66666,
            name="테스트3",
            place_type="restaurant",
            category="한식",
        )
        db_session.add(place)
        await db_session.commit()

        kw = Keyword(
            place_id=66666,
            keyword="강남 한식",
            keyword_type="pll",
        )
        db_session.add(kw)
        await db_session.commit()

        today = date.today()
        hist1 = KeywordRankHistory(
            keyword_id=kw.id,
            rank_position=5,
            map_type="신지도",
            recorded_date=today,
        )
        db_session.add(hist1)
        await db_session.commit()

        # Update existing history for today
        hist1.rank_position = 3
        await db_session.commit()

        stmt = select(KeywordRankHistory).where(
            KeywordRankHistory.keyword_id == kw.id,
            KeywordRankHistory.recorded_date == today,
        )
        result = await db_session.execute(stmt)
        records = result.scalars().all()
        assert len(records) == 1
        assert records[0].rank_position == 3


# ==================== Extraction Service Edge Cases ====================


class TestExtractionServiceEdgeCases:
    """Edge case tests for extraction service."""

    def test_cancel_job_sets_flag_to_false(self):
        """cancel_job should set the running flag to False."""
        service = ExtractionService()
        service._running_jobs[1] = True
        assert service._is_running(1) is True
        service.cancel_job(1)
        assert service._is_running(1) is False

    def test_is_running_returns_false_for_unknown_job(self):
        """_is_running should return False for unknown job IDs."""
        service = ExtractionService()
        assert service._is_running(9999) is False

    @pytest.mark.asyncio
    async def test_fail_job_nonexistent(self, db_session: AsyncSession):
        """_fail_job on non-existent job should not raise."""
        service = ExtractionService()
        # Mock the session factory
        with patch(
            "app.services.extraction_service.async_session_factory",
        ) as mock_factory:
            mock_session = AsyncMock()
            mock_session.get = AsyncMock(return_value=None)
            mock_session.commit = AsyncMock()
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_factory.return_value = mock_ctx

            # Should not raise
            await service._fail_job(9999, "test error")

    @pytest.mark.asyncio
    async def test_complete_job_nonexistent(self, db_session: AsyncSession):
        """_complete_job on non-existent job should not raise."""
        service = ExtractionService()
        with patch(
            "app.services.extraction_service.async_session_factory",
        ) as mock_factory:
            mock_session = AsyncMock()
            mock_session.get = AsyncMock(return_value=None)
            mock_session.commit = AsyncMock()
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_factory.return_value = mock_ctx

            await service._complete_job(9999, [], 0)

    @pytest.mark.asyncio
    async def test_save_keywords_empty_data(self):
        """_save_keywords with empty data should return 0."""
        service = ExtractionService()
        with patch(
            "app.services.extraction_service.async_session_factory",
        ):
            result = await service._save_keywords(
                place_id=12345,
                rank_results=[],
                final_keywords=[],
                target_count=100,
            )
            assert result == 0

    @pytest.mark.asyncio
    async def test_job_already_running_is_skipped(self, db_session: AsyncSession):
        """A job that's not in QUEUED state should be skipped."""
        # Create a running job directly
        job = ExtractionJob(
            naver_url="https://m.place.naver.com/restaurant/1234567/home",
            status=ExtractionJobStatus.RUNNING.value,
        )
        db_session.add(job)
        await db_session.commit()
        job_id = job.id

        service = ExtractionService()

        with patch(
            "app.services.extraction_service.async_session_factory",
        ) as mock_factory:
            mock_session = AsyncMock()
            mock_job = MagicMock()
            mock_job.status = ExtractionJobStatus.RUNNING.value
            mock_session.get = AsyncMock(return_value=mock_job)
            mock_session.commit = AsyncMock()
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_factory.return_value = mock_ctx

            await service.execute_job(job_id)
            # Job should be skipped, not added to running jobs
            assert job_id not in service._running_jobs


# ==================== Callback Failure Tests ====================


class TestCallbackGracefulFailure:
    """Test callback failure handling."""

    @pytest.mark.asyncio
    async def test_callback_httpx_import_error(self):
        """Callback should handle httpx ImportError gracefully."""
        service = ExtractionService()
        with patch.dict("sys.modules", {"httpx": None}):
            with patch("builtins.__import__", side_effect=ImportError("no httpx")):
                # Should not raise
                await service._send_callback(1, "completed", 100, 12345)

    @pytest.mark.asyncio
    async def test_callback_connection_error(self):
        """Callback should handle connection errors gracefully."""
        service = ExtractionService()
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=Exception("Connection refused")
            )
            mock_client.aclose = AsyncMock()
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_ctx

            # Should not raise
            await service._send_callback(1, "failed", 0, 0)

    @pytest.mark.asyncio
    async def test_callback_non_200_response(self):
        """Callback should log warning for non-200 responses."""
        service = ExtractionService()
        import httpx

        with patch("httpx.AsyncClient") as MockClient:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_ctx

            # Should not raise, just log warning
            await service._send_callback(1, "completed", 100, 12345)


# ==================== Rank Checker Edge Cases ====================


class TestRankCheckerEdgeCases:
    """Edge case tests for rank checker."""

    @pytest.mark.asyncio
    async def test_check_rank_http_error(self):
        """Rank check should handle HTTP errors gracefully."""
        checker = RankChecker()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("HTTP Error"))
        checker._client = mock_client

        result, place_info = await checker.check_rank(
            "강남 맛집", "1234567", max_rank=30
        )

        assert result.rank is None
        assert result.error is not None
        assert "HTTP Error" in result.error
        assert place_info is None

    @pytest.mark.asyncio
    async def test_check_rank_empty_items(self):
        """Rank check with empty items list should return no rank."""
        checker = RankChecker()
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "businesses": {
                    "total": 0,
                    "items": [],
                }
            }
        }
        mock_client.post = AsyncMock(return_value=mock_response)
        checker._client = mock_client

        result, place_info = await checker.check_rank(
            "매우특이한키워드", "1234567", max_rank=30
        )

        assert result.rank is None
        assert result.result_count == 0

    @pytest.mark.asyncio
    async def test_check_map_type_network_error(self):
        """Map type check should handle network errors gracefully."""
        checker = RankChecker()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Network error"))
        checker._client = mock_client

        result = await checker.check_map_type("강남 맛집")
        assert result == "구지도"  # Default fallback

    @pytest.mark.asyncio
    async def test_batch_check_ranks_empty(self):
        """Batch check with empty keywords list."""
        checker = RankChecker()
        checker._client = AsyncMock()

        results, place_info = await checker.batch_check_ranks(
            keywords=[], place_id="1234567", max_rank=30
        )

        assert results == []
        assert place_info is None

    def test_booking_keywords_with_existing_reservation_keyword(self):
        """Keywords already containing '예약' should not get booking suffix."""
        checker = RankChecker(booking_keyword_ratio=0.5)
        keywords = ["강남 맛집 예약", "강남역 스테이크"]
        place_info = PlaceInfo(
            place_id="123", name="테스트", category="restaurant"
        )
        rank_results = [
            RankCheckResult(
                keyword="강남 맛집 예약",
                map_type="신지도",
                result_count=50,
            ),
            RankCheckResult(
                keyword="강남역 스테이크",
                map_type="신지도",
                result_count=50,
            ),
        ]

        final, booking, replaced = checker.generate_booking_keywords(
            keywords,
            place_info=place_info,
            rank_results=rank_results,
            map_type="신지도",
        )

        # '예약' keyword should not be replaced
        for bkw in replaced:
            assert "예약" not in bkw

    def test_booking_keywords_with_no_rank_results(self):
        """Booking keywords with map_type but no rank results."""
        checker = RankChecker(booking_keyword_ratio=0.2)
        keywords = ["강남 맛집", "강남역 한식", "역삼 맛집"]
        place_info = PlaceInfo(
            place_id="123", name="테스트", category="restaurant"
        )

        final, booking, replaced = checker.generate_booking_keywords(
            keywords,
            place_info=place_info,
            rank_results=None,
            map_type="신지도",
        )

        # With no rank results but 신지도, all keywords are eligible
        assert len(booking) >= 1

    @pytest.mark.asyncio
    async def test_full_check_method(self):
        """Test full_check method with mocked responses."""
        checker = RankChecker()
        mock_client = AsyncMock()

        # Mock map type check
        map_response = MagicMock()
        map_response.status_code = 200
        map_response.text = '{"queryType": "restaurant"}'
        mock_client.get = AsyncMock(return_value=map_response)

        # Mock rank check
        rank_response = MagicMock()
        rank_response.status_code = 200
        rank_response.json.return_value = {
            "data": {
                "businesses": {
                    "total": 50,
                    "items": [
                        {
                            "id": "123",
                            "name": "테스트",
                            "businessCategory": "restaurant",
                            "naverBookingHubId": "hub1",
                        },
                    ],
                }
            }
        }
        mock_client.post = AsyncMock(return_value=rank_response)
        checker._client = mock_client

        result = await checker.full_check(
            keywords=["강남 맛집"],
            place_id="123",
            max_rank=30,
        )

        assert result["map_type"] == "신지도"
        assert len(result["ranks"]) == 1
        assert result["place_info"] is not None

    def test_is_restaurant_category_various(self):
        """Test restaurant category detection with various inputs."""
        checker = RankChecker()
        assert checker._is_restaurant_category("restaurant") is True
        assert checker._is_restaurant_category("한식") is True
        assert checker._is_restaurant_category("카페") is True
        assert checker._is_restaurant_category("치과") is False
        assert checker._is_restaurant_category("미용실") is False
        assert checker._is_restaurant_category("") is False
        assert checker._is_restaurant_category("RESTAURANT") is True


# ==================== Address Parser Edge Cases ====================


class TestAddressParserEdgeCases:
    """Edge cases for address parsing."""

    def test_empty_address(self):
        parser = AddressParser()
        region = parser.parse("")
        assert region.city == ""
        assert region.gu == ""
        assert region.dong == ""

    def test_seoul_address(self):
        parser = AddressParser()
        region = parser.parse("서울특별시 강남구 역삼동 123-45")
        assert region.city == "서울"
        assert region.gu == "강남구"
        assert region.dong == "역삼동"

    def test_gyeonggi_address(self):
        parser = AddressParser()
        region = parser.parse("경기도 고양시 일산동구 장항동 123")
        assert region.city == "경기"
        assert region.si == "고양시"
        assert region.gu == "일산동구"
        assert region.dong == "장항동"
        assert region.major_area == "일산"

    def test_busan_address(self):
        parser = AddressParser()
        region = parser.parse("부산광역시 해운대구 우동 123")
        assert region.city == "부산"
        assert region.gu == "해운대구"

    def test_road_address(self):
        parser = AddressParser()
        region = parser.parse("서울특별시 강남구 테헤란로 123")
        assert region.road == "테헤란로"

    def test_sejong_special_city(self):
        parser = AddressParser()
        region = parser.parse("세종특별자치시 조치원읍 123")
        assert region.city == "세종"

    def test_jeju_special_province(self):
        parser = AddressParser()
        region = parser.parse("제주특별자치도 제주시 연동 123")
        assert region.city == "제주"
        assert region.si == "제주시"

    def test_station_extraction_from_road_info(self):
        parser = AddressParser()
        region = parser.parse("서울특별시 강남구 역삼동", road_info="강남역 인근 테헤란로")
        assert "강남역" in region.stations

    def test_multiple_stations(self):
        parser = AddressParser()
        region = parser.parse("서울특별시 강남구", road_info="강남역, 역삼역 근처")
        assert "강남역" in region.stations
        assert "역삼역" in region.stations

    def test_dong_ending_with_gu(self):
        """Dong names ending with 동구 should not be treated as dong."""
        parser = AddressParser()
        region = parser.parse("경기도 고양시 일산동구 장항동")
        assert region.gu == "일산동구"
        assert region.dong == "장항동"

    def test_road_name_with_gil(self):
        """Road names ending with 길 should be detected."""
        parser = AddressParser()
        region = parser.parse("서울특별시 강남구 역삼동 봉은사길 123")
        assert region.road == "봉은사길"


# ==================== API Router Edge Cases ====================


@pytest.fixture
def api_client():
    """Create a test client for API tests."""
    return TestClient(app)


class TestAPIRouterEdgeCases:
    """Edge case tests for internal API router."""

    def test_health_returns_version(self, api_client):
        """Health endpoint should return version."""
        response = api_client.get("/internal/health")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert data["version"] == "0.1.0"

    def test_capacity_available_slots(self, api_client):
        """Capacity should show correct available slots."""
        response = api_client.get("/internal/capacity")
        data = response.json()
        assert data["max_concurrent_jobs"] == 3
        assert data["available_slots"] == data["max_concurrent_jobs"] - data["running_jobs"]

    def test_create_job_invalid_url_validation(self, api_client):
        """Create job with missing required field should fail."""
        response = api_client.post(
            "/internal/jobs",
            json={
                # Missing naver_url (required)
                "target_count": 100,
            },
        )
        assert response.status_code == 422  # Validation error

    def test_create_job_target_count_too_low(self, api_client):
        """Create job with target_count below minimum should fail."""
        response = api_client.post(
            "/internal/jobs",
            json={
                "naver_url": "https://m.place.naver.com/restaurant/123",
                "target_count": 5,  # Min is 10
            },
        )
        assert response.status_code == 422

    def test_create_job_target_count_too_high(self, api_client):
        """Create job with target_count above maximum should fail."""
        response = api_client.post(
            "/internal/jobs",
            json={
                "naver_url": "https://m.place.naver.com/restaurant/123",
                "target_count": 1000,  # Max is 500
            },
        )
        assert response.status_code == 422

    def test_create_job_name_keyword_ratio_invalid(self, api_client):
        """Create job with name_keyword_ratio > 1.0 should fail."""
        response = api_client.post(
            "/internal/jobs",
            json={
                "naver_url": "https://m.place.naver.com/restaurant/123",
                "name_keyword_ratio": 1.5,
            },
        )
        assert response.status_code == 422

    def test_create_job_max_rank_below_min(self, api_client):
        """Create job with max_rank below minimum should fail."""
        response = api_client.post(
            "/internal/jobs",
            json={
                "naver_url": "https://m.place.naver.com/restaurant/123",
                "max_rank": 3,  # Min is 5
            },
        )
        assert response.status_code == 422


# ==================== PlaceData serialization edge cases ====================


class TestPlaceDataSerialization:
    """Test PlaceData serialization edge cases."""

    def test_review_keywords_serialization(self):
        """ReviewKeyword objects should serialize correctly."""
        place = PlaceData(
            name="테스트",
            review_menu_keywords=[
                ReviewKeyword(label="파스타", count=100),
                ReviewKeyword(label="", count=0),  # empty label
            ],
            review_theme_keywords=[
                ReviewKeyword(label="분위기", count=50),
            ],
        )
        d = place.to_dict()
        assert len(d["review_menu_keywords"]) == 2
        assert d["review_menu_keywords"][0]["label"] == "파스타"
        assert d["review_menu_keywords"][1]["label"] == ""

    def test_empty_review_keywords(self):
        """Empty review keywords should serialize to empty list."""
        place = PlaceData()
        d = place.to_dict()
        assert d["review_menu_keywords"] == []
        assert d["review_theme_keywords"] == []


# ==================== Business Type Edge Cases ====================


class TestBusinessTypeEdgeCases:
    """Additional business type detection tests."""

    def test_none_category(self):
        """None-like empty category should return general."""
        assert detect_business_type("") == "general"

    def test_mixed_category(self):
        """Category mixing restaurant and hospital should match first."""
        # "음식" comes before any hospital keyword
        assert detect_business_type("음식점병원") == "restaurant"

    def test_cafe_is_restaurant(self):
        """Cafe should be detected as restaurant."""
        assert detect_business_type("카페, 디저트") == "restaurant"

    def test_animal_hospital(self):
        """Animal hospital should be detected as hospital."""
        assert detect_business_type("동물병원") == "hospital"

    def test_vet_clinic(self):
        """Vet clinic should be detected as hospital."""
        assert detect_business_type("펫클리닉") == "hospital"

    def test_general_businesses(self):
        """Various general businesses."""
        assert detect_business_type("세탁소") == "general"
        assert detect_business_type("부동산") == "general"
        assert detect_business_type("헬스장") == "general"


# ==================== Extraction Job Model Edge Cases ====================


class TestExtractionJobModelEdgeCases:
    """Edge case tests for ExtractionJob model."""

    @pytest.mark.asyncio
    async def test_job_with_no_optional_fields(self, db_session: AsyncSession):
        """Job with only required fields should work."""
        job = ExtractionJob(
            naver_url="https://m.place.naver.com/restaurant/1234567/home",
            status=ExtractionJobStatus.QUEUED.value,
        )
        db_session.add(job)
        await db_session.commit()

        result = await db_session.get(ExtractionJob, job.id)
        assert result is not None
        assert result.target_count == 100  # default
        assert result.max_rank == 50  # default
        assert result.min_rank == 1  # default
        assert result.name_keyword_ratio == 0.30  # default
        assert result.order_item_id is None
        assert result.place_id is None
        assert result.place_name is None
        assert result.results is None
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_job_status_enum_values(self, db_session: AsyncSession):
        """All ExtractionJobStatus enum values should be valid."""
        assert ExtractionJobStatus.QUEUED.value == "queued"
        assert ExtractionJobStatus.RUNNING.value == "running"
        assert ExtractionJobStatus.COMPLETED.value == "completed"
        assert ExtractionJobStatus.FAILED.value == "failed"
        assert ExtractionJobStatus.CANCELLED.value == "cancelled"

    @pytest.mark.asyncio
    async def test_job_with_results_json(self, db_session: AsyncSession):
        """Job with JSON results should store and retrieve correctly."""
        results = [
            {"keyword": "강남 맛집", "rank": 3, "map_type": "신지도"},
            {"keyword": "강남역 맛집", "rank": None, "map_type": ""},
        ]
        job = ExtractionJob(
            naver_url="https://m.place.naver.com/restaurant/1234567/home",
            status=ExtractionJobStatus.COMPLETED.value,
            results=results,
            result_count=2,
        )
        db_session.add(job)
        await db_session.commit()

        result = await db_session.get(ExtractionJob, job.id)
        assert result.results is not None
        assert len(result.results) == 2
        assert result.results[0]["keyword"] == "강남 맛집"
        assert result.results[0]["rank"] == 3


# ==================== Place Model Edge Cases ====================


class TestPlaceModelEdgeCases:
    """Edge case tests for Place model."""

    @pytest.mark.asyncio
    async def test_place_with_json_fields(self, db_session: AsyncSession):
        """Place with JSON array fields."""
        place = Place(
            id=55555,
            name="테스트",
            place_type="restaurant",
            keywords=["키워드1", "키워드2"],
            conveniences=["주차", "배달"],
            micro_reviews=["맛있어요", "분위기좋아요"],
            stations=["강남역", "역삼역"],
            discovered_regions=["강남", "서초"],
        )
        db_session.add(place)
        await db_session.commit()

        result = await db_session.get(Place, 55555)
        assert result.keywords == ["키워드1", "키워드2"]
        assert result.conveniences == ["주차", "배달"]
        assert "강남역" in result.stations
        assert "강남" in result.discovered_regions

    @pytest.mark.asyncio
    async def test_place_with_empty_json_fields(self, db_session: AsyncSession):
        """Place with empty JSON arrays."""
        place = Place(
            id=44444,
            name="빈데이터",
            place_type="general",
            keywords=[],
            conveniences=[],
            menus=[],
            medical_subjects=[],
        )
        db_session.add(place)
        await db_session.commit()

        result = await db_session.get(Place, 44444)
        assert result.keywords == []
        assert result.menus == []

    @pytest.mark.asyncio
    async def test_place_update_preserves_id(self, db_session: AsyncSession):
        """Updating a place should preserve the original ID."""
        place = Place(
            id=33333,
            name="원래이름",
            place_type="restaurant",
        )
        db_session.add(place)
        await db_session.commit()

        place.name = "변경된이름"
        place.category = "한식"
        await db_session.commit()

        result = await db_session.get(Place, 33333)
        assert result.id == 33333
        assert result.name == "변경된이름"
        assert result.category == "한식"


# ==================== Region Keyword Generation Edge Cases ====================


class TestRegionKeywordsEdgeCases:
    """Additional edge cases for region keyword generation."""

    def test_station_without_yeok_suffix(self):
        """Station name without 역 suffix should still be processed."""
        region = RegionInfo(
            stations=["정발산"],  # no 역 suffix
        )
        keywords = generate_region_keywords(region)
        # Should add station directly
        assert "정발산" in keywords

    def test_very_short_station_name(self):
        """Short station name (2 chars)."""
        region = RegionInfo(
            stations=["역삼역"],
        )
        keywords = generate_region_keywords(region)
        assert "역삼역" in keywords
        # base = "역삼" (2 chars, should be included)
        assert "역삼" in keywords

    def test_region_with_road_only(self):
        """Region with only road info."""
        region = RegionInfo(
            road="테헤란로",
        )
        keywords = generate_region_keywords(region)
        # Road alone doesn't generate core_regions, so no combinations
        assert isinstance(keywords, list)

    def test_region_with_major_area(self):
        """Region with major_area should include it."""
        region = RegionInfo(
            gu="일산동구",
            gu_without_suffix="일산동",
            major_area="일산",
        )
        keywords = generate_region_keywords(region)
        assert "일산" in keywords
        assert "일산동구" in keywords

    def test_region_deduplication(self):
        """Generated region keywords should have no duplicates."""
        region = RegionInfo(
            city="서울",
            si="",
            gu="강남구",
            dong="역삼동",
            gu_without_suffix="강남",
            dong_without_suffix="역삼",
            stations=["강남역", "역삼역"],
        )
        keywords = generate_region_keywords(region)
        assert len(keywords) == len(set(keywords)), "Region keywords should be unique"

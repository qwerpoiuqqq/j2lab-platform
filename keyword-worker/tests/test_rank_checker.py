"""Tests for rank checker service (mocked HTTP calls)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.services.rank_checker import (
    PlaceInfo,
    RankCheckResult,
    RankChecker,
)


class TestRankCheckResult:
    """Test RankCheckResult data model."""

    def test_to_dict(self):
        result = RankCheckResult(
            keyword="강남 맛집",
            keyword_type="pll",
            rank=3,
            result_count=50,
            query_type="restaurant",
            map_type="신지도",
        )
        d = result.to_dict()
        assert d["keyword"] == "강남 맛집"
        assert d["rank"] == 3
        assert d["keyword_type"] == "pll"
        assert d["map_type"] == "신지도"

    def test_plt_type(self):
        result = RankCheckResult(
            keyword="미도인 강남",
            keyword_type="plt",
            rank=1,
            result_count=1,
        )
        assert result.keyword_type == "plt"


class TestPlaceInfo:
    """Test PlaceInfo data model."""

    def test_to_dict(self):
        info = PlaceInfo(
            place_id="1234567",
            name="테스트 맛집",
            category="restaurant",
            has_booking=True,
            booking_type="realtime",
        )
        d = info.to_dict()
        assert d["place_id"] == "1234567"
        assert d["has_booking"] is True
        assert d["booking_type"] == "realtime"


class TestRankCheckerBookingKeywords:
    """Test booking keyword generation logic."""

    def test_restaurant_booking_keywords(self):
        checker = RankChecker(booking_keyword_ratio=0.1)

        keywords = ["강남 맛집", "강남역 스테이크", "강남 파스타"]
        place_info = PlaceInfo(
            place_id="123",
            name="테스트",
            category="restaurant",
            has_booking=True,
        )

        # All keywords are eligible (신지도 map type)
        rank_results = [
            RankCheckResult(
                keyword=kw, map_type="신지도", result_count=50
            )
            for kw in keywords
        ]

        final, booking, replaced = checker.generate_booking_keywords(
            keywords,
            place_info=place_info,
            rank_results=rank_results,
            map_type="신지도",
        )

        # With 3 keywords and 10% ratio, at least 1 should be replaced
        assert len(booking) >= 1
        assert len(replaced) >= 1
        assert all("실시간 예약" in bk for bk in booking)
        # Total count should be preserved
        assert len(final) == len(keywords)

    def test_non_restaurant_no_booking(self):
        checker = RankChecker(booking_keyword_ratio=0.1)

        keywords = ["강남 치과", "강남역 임플란트"]
        place_info = PlaceInfo(
            place_id="123",
            name="테스트치과",
            category="hospital",
        )

        final, booking, replaced = checker.generate_booking_keywords(
            keywords, place_info=place_info
        )

        assert len(booking) == 0
        assert len(replaced) == 0
        assert final == keywords

    def test_empty_keywords(self):
        checker = RankChecker()
        final, booking, replaced = checker.generate_booking_keywords([])
        assert final == []
        assert booking == []
        assert replaced == []

    def test_no_eligible_old_map(self):
        """No booking keywords if all are on old map."""
        checker = RankChecker(booking_keyword_ratio=0.5)
        keywords = ["강남 맛집", "강남역 스테이크"]
        place_info = PlaceInfo(
            place_id="123", name="테스트", category="restaurant"
        )
        rank_results = [
            RankCheckResult(
                keyword=kw, map_type="구지도", result_count=50
            )
            for kw in keywords
        ]

        final, booking, replaced = checker.generate_booking_keywords(
            keywords,
            place_info=place_info,
            rank_results=rank_results,
            map_type="구지도",
        )

        assert len(booking) == 0


class TestRankCheckerMapType:
    """Test map type detection (mocked)."""

    @pytest.mark.asyncio
    async def test_check_map_type_new(self):
        """Test 신지도 detection."""
        checker = RankChecker()
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"queryType": "restaurant"}'
        mock_client.get = AsyncMock(return_value=mock_response)
        checker._client = mock_client

        result = await checker.check_map_type("강남 맛집")
        assert result == "신지도"

    @pytest.mark.asyncio
    async def test_check_map_type_old(self):
        """Test 구지도 detection."""
        checker = RankChecker()
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"some": "data"}'
        mock_client.get = AsyncMock(return_value=mock_response)
        checker._client = mock_client

        result = await checker.check_map_type("강남 치과 지도")
        assert result == "구지도"


class TestRankCheckerCheckRank:
    """Test rank checking (mocked HTTP)."""

    @pytest.mark.asyncio
    async def test_check_rank_found(self):
        """Test finding a place in search results."""
        checker = RankChecker()
        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "businesses": {
                    "total": 50,
                    "items": [
                        {"id": "111", "name": "다른곳", "businessCategory": "restaurant"},
                        {"id": "222", "name": "다른곳2", "businessCategory": "restaurant"},
                        {"id": "1234567", "name": "타겟맛집", "businessCategory": "restaurant", "naverBookingHubId": "hub123"},
                    ],
                }
            }
        }
        mock_client.post = AsyncMock(return_value=mock_response)
        checker._client = mock_client

        result, place_info = await checker.check_rank(
            "강남 맛집", "1234567", max_rank=30
        )

        assert result.rank == 3
        assert result.keyword_type == "pll"
        assert result.result_count == 50
        assert place_info is not None
        assert place_info.place_id == "1234567"
        assert place_info.has_booking is True

    @pytest.mark.asyncio
    async def test_check_rank_not_found(self):
        """Test when place is not in search results."""
        checker = RankChecker()
        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "businesses": {
                    "total": 50,
                    "items": [
                        {"id": "111", "name": "다른곳", "businessCategory": "restaurant"},
                    ],
                }
            }
        }
        mock_client.post = AsyncMock(return_value=mock_response)
        checker._client = mock_client

        result, place_info = await checker.check_rank(
            "강남 맛집", "9999999", max_rank=30
        )

        assert result.rank is None
        assert place_info is None

    @pytest.mark.asyncio
    async def test_check_rank_plt(self):
        """Test PLT (single result) detection."""
        checker = RankChecker()
        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "businesses": {
                    "total": 1,
                    "items": [
                        {"id": "1234567", "name": "미도인 강남", "businessCategory": "restaurant"},
                    ],
                }
            }
        }
        mock_client.post = AsyncMock(return_value=mock_response)
        checker._client = mock_client

        result, _ = await checker.check_rank(
            "미도인 강남", "1234567", max_rank=30
        )

        assert result.keyword_type == "plt"
        assert result.rank == 1
        assert result.result_count == 1

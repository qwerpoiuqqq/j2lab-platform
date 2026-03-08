"""Naver Place rank checker using GraphQL API (httpx-based).

Checks keyword rankings via Naver's GraphQL API (nxPlaces).
Much faster than browser-based checking (~0.05s per keyword).

Ported from: reference/keyword-extract/src/keyword_rank_checker.py
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Global semaphore: limits total concurrent Naver API requests across ALL jobs
_global_naver_semaphore = asyncio.Semaphore(5)

try:
    import httpx

    _httpx_available = True
except ImportError:
    logger.warning("httpx not installed. Install with: pip install httpx")
    _httpx_available = False
    httpx = None


@dataclass
class RankCheckResult:
    """Result of a single keyword rank check."""

    keyword: str
    keyword_type: str = "pll"  # "pll" (list) or "plt" (target/single)
    rank: Optional[int] = None
    result_count: int = 0
    query_type: Optional[str] = None  # restaurant, hospital, etc.
    map_type: str = ""  # "신지도" or "구지도"
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "keyword": self.keyword,
            "keyword_type": self.keyword_type,
            "rank": self.rank,
            "result_count": self.result_count,
            "query_type": self.query_type,
            "map_type": self.map_type,
            "error": self.error,
        }


@dataclass
class PlaceInfo:
    """Basic place info from search results."""

    place_id: str
    name: str = ""
    category: str = ""
    has_booking: bool = False
    booking_type: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "place_id": self.place_id,
            "name": self.name,
            "category": self.category,
            "has_booking": self.has_booking,
            "booking_type": self.booking_type,
        }


class RankChecker:
    """Naver Place rank checker via GraphQL API.

    Uses httpx for async HTTP requests to Naver's GraphQL endpoint.
    Falls back gracefully if httpx is not available.
    """

    GRAPHQL_URL = "https://nx-api.place.naver.com/graphql"
    SEARCH_URL = "https://m.search.naver.com/search.naver"

    # Default coordinates (Seoul center)
    DEFAULT_X = "126.9783882"
    DEFAULT_Y = "37.5666103"

    BOOKING_SUFFIX = "실시간 예약"
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    # Restaurant-like categories eligible for booking keywords
    BOOKING_ELIGIBLE_CATEGORIES = [
        "restaurant", "음식점", "맛집", "식당", "카페", "cafe",
        "한식", "양식", "일식", "중식", "분식", "뷔페", "고기", "회",
    ]

    def __init__(
        self,
        timeout: float = 15.0,
        default_max_rank: int = 30,
        x: Optional[str] = None,
        y: Optional[str] = None,
        booking_keyword_ratio: float = 0.1,
    ):
        self.timeout = timeout
        self.default_max_rank = default_max_rank
        self.x = x or self.DEFAULT_X
        self.y = y or self.DEFAULT_Y
        self.booking_keyword_ratio = booking_keyword_ratio
        self._client: Optional[Any] = None

    async def __aenter__(self):
        if not _httpx_available:
            raise ImportError("httpx is required for RankChecker")
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            headers={
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
                "Accept": "application/json",
                "Accept-Language": "ko-KR,ko;q=0.9",
            },
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    async def check_map_type(self, keyword: str) -> str:
        """Check map type (신지도/구지도) for a keyword via HTML search."""
        try:
            resp = await self._client.get(
                self.SEARCH_URL,
                params={"query": keyword},
                headers={
                    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
                },
            )
            if resp.status_code == 200:
                qt_match = re.search(r'"queryType"\s*:\s*"([^"]+)"', resp.text)
                if qt_match and qt_match.group(1):
                    return "신지도"
            return "구지도"
        except Exception:
            return "구지도"

    async def check_rank(
        self,
        keyword: str,
        place_id: str,
        max_rank: Optional[int] = None,
        map_type: str = "",
    ) -> tuple:
        """Check rank for a single keyword.

        Returns:
            Tuple of (RankCheckResult, PlaceInfo or None)
        """
        result = RankCheckResult(keyword=keyword, keyword_type="pll")
        place_info = None
        max_rank = max_rank or self.default_max_rank

        query = """
        query getPlacesList($input: PlacesInput) {
            businesses: nxPlaces(input: $input) {
                total
                items {
                    id
                    name
                    businessCategory
                    naverBookingHubId
                    bookingUrl
                }
            }
        }
        """

        try:
            resp = None
            for attempt in range(5):
                resp = await self._client.post(
                    self.GRAPHQL_URL,
                    json={
                        "operationName": "getPlacesList",
                        "query": query,
                        "variables": {
                            "input": {
                                "query": keyword,
                                "display": max_rank,
                                "deviceType": "mobile",
                                "x": self.x,
                                "y": self.y,
                            }
                        },
                    },
                    headers={
                        "Content-Type": "application/json",
                        "Referer": "https://m.place.naver.com/",
                        "Origin": "https://m.place.naver.com",
                    },
                )

                if resp.status_code == 200:
                    break

                if resp.status_code in self.RETRYABLE_STATUS_CODES and attempt < 4:
                    wait = min(2 ** attempt + random.uniform(0, 1), 30.0)
                    await asyncio.sleep(wait)
                    continue
                break

            if resp is not None and resp.status_code == 200:
                data = resp.json()
                businesses = data.get("data", {}).get("businesses", {})
                items = businesses.get("items", [])
                total = businesses.get("total", 0)

                result.result_count = total
                if items:
                    result.query_type = items[0].get("businessCategory")

                result.keyword_type = "plt" if total == 1 else "pll"
                result.map_type = map_type or ""

                for idx, item in enumerate(items, 1):
                    if str(item.get("id")) == str(place_id):
                        result.rank = idx
                        has_booking = bool(
                            item.get("naverBookingHubId") or item.get("bookingUrl")
                        )
                        booking_type = (
                            "realtime"
                            if item.get("naverBookingHubId")
                            else ("url" if item.get("bookingUrl") else None)
                        )
                        place_info = PlaceInfo(
                            place_id=str(item.get("id")),
                            name=item.get("name", ""),
                            category=item.get("businessCategory", ""),
                            has_booking=has_booking,
                            booking_type=booking_type,
                        )
                        break

        except Exception as e:
            result.error = str(e)
            logger.warning("Rank check failed for '%s': %s", keyword, e)

        return result, place_info

    async def batch_check_ranks(
        self,
        keywords: List[str],
        place_id: str,
        max_rank: Optional[int] = None,
        max_concurrent: int = 5,
        map_type: str = "",
        on_result: Optional[Callable[[RankCheckResult], None]] = None,
    ) -> tuple:
        """Check ranks for multiple keywords in parallel.

        Args:
            on_result: Optional callback invoked with each RankCheckResult as it
                       completes.  Used by ExtractionService to accumulate partial
                       results that survive a timeout cancellation.

        Returns:
            Tuple of (List[RankCheckResult], PlaceInfo or None)
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        found_place_info = None

        async def check_one(kw: str) -> RankCheckResult:
            nonlocal found_place_info
            async with _global_naver_semaphore:
                await asyncio.sleep(random.uniform(0.3, 0.7))
                result, pinfo = await self.check_rank(kw, place_id, max_rank, map_type)
                if pinfo and not found_place_info:
                    found_place_info = pinfo
                if on_result is not None:
                    on_result(result)
                return result

        tasks = [check_one(kw) for kw in keywords]
        results = await asyncio.gather(*tasks)
        return list(results), found_place_info

    def _is_restaurant_category(self, category: str) -> bool:
        """Check if category is restaurant-like."""
        if not category:
            return False
        category_lower = category.lower()
        return any(cat in category_lower for cat in self.BOOKING_ELIGIBLE_CATEGORIES)

    def generate_booking_keywords(
        self,
        keywords: List[str],
        place_info: Optional[PlaceInfo] = None,
        rank_results: Optional[List[RankCheckResult]] = None,
        ratio: Optional[float] = None,
        map_type: str = "",
    ) -> tuple:
        """Generate booking keyword variants for restaurant listings.

        Replaces a portion of eligible keywords with "실시간 예약" suffix.
        Total keyword count is preserved.

        Returns:
            Tuple of (final_keywords, booking_keywords, replaced_keywords)
        """
        if not keywords:
            return list(keywords), [], []

        category = ""
        if place_info:
            category = place_info.category or ""
        elif rank_results:
            for r in rank_results:
                if r.query_type:
                    category = r.query_type
                    break

        if not self._is_restaurant_category(category):
            return list(keywords), [], []

        ratio = ratio if ratio is not None else self.booking_keyword_ratio

        eligible_keywords = []
        if rank_results:
            keyword_to_result = {r.keyword: r for r in rank_results}
            for kw in keywords:
                result = keyword_to_result.get(kw)
                if result:
                    is_new_map = result.map_type == "신지도" or map_type == "신지도"
                    is_list_type = result.result_count > 1
                    if is_new_map and is_list_type and "예약" not in kw:
                        eligible_keywords.append(kw)
        elif map_type == "신지도":
            eligible_keywords = [kw for kw in keywords if "예약" not in kw]

        if not eligible_keywords:
            return list(keywords), [], []

        total_keywords = len(keywords)
        booking_count = max(1, int(total_keywords * ratio))
        replaced_keywords = eligible_keywords[:booking_count]
        booking_keywords = [f"{kw} {self.BOOKING_SUFFIX}" for kw in replaced_keywords]

        replaced_set = set(replaced_keywords)
        remaining = [kw for kw in keywords if kw not in replaced_set]
        final_keywords = remaining + booking_keywords

        return final_keywords, booking_keywords, replaced_keywords

    async def full_check(
        self,
        keywords: List[str],
        place_id: str,
        max_rank: Optional[int] = None,
        auto_booking_keywords: bool = True,
        check_map_type_flag: bool = True,
        booking_keyword_ratio: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Full check: rank + type + booking keywords.

        Returns:
            Dict with keys: place_info, map_type, ranks, booking_keywords,
            replaced_keywords, all_keywords
        """
        result: Dict[str, Any] = {
            "place_info": None,
            "map_type": "",
            "ranks": [],
            "booking_keywords": [],
            "replaced_keywords": [],
            "all_keywords": list(keywords),
        }

        map_type = ""
        if check_map_type_flag and keywords:
            map_type = await self.check_map_type(keywords[0])
            result["map_type"] = map_type

        base_ranks, place_info = await self.batch_check_ranks(
            keywords, place_id, max_rank, map_type=map_type
        )

        if place_info:
            result["place_info"] = place_info.to_dict()

        if auto_booking_keywords:
            final_kws, booking_kws, replaced_kws = self.generate_booking_keywords(
                keywords,
                place_info=place_info,
                rank_results=base_ranks,
                ratio=booking_keyword_ratio,
                map_type=map_type,
            )
            result["booking_keywords"] = booking_kws
            result["replaced_keywords"] = replaced_kws
            result["all_keywords"] = final_kws

        result["ranks"] = [r.to_dict() for r in base_ranks]
        return result

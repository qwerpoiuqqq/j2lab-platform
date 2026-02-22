"""
키워드 순위 + 태그 체커 v2
2단계 처리로 API 요청 최소화

태그 체계:
- 단일 타겟: 검색 결과 1개
- 신지도 리스트: 결과 여러 개 + queryType 있음
- 구지도 리스트: 결과 여러 개 + queryType 없음

사용법:
    from src.keyword_checker_v2 import KeywordChecker

    async with KeywordChecker() as checker:
        results = await checker.check(
            keywords=["강남 맛집", "미도인 강남", "강남역 스테이크"],
            place_id="1427134948",
            max_rank=30  # 30위 이내만 태그 확인
        )

        for r in results:
            print(f"{r['keyword']} - {r['rank']}위 - {r['tag']}")
"""

import asyncio
import re
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

try:
    import httpx
except ImportError:
    httpx = None


@dataclass
class KeywordResult:
    """키워드 체크 결과"""
    keyword: str
    rank: Optional[int]  # None = 순위권 외
    tag: str  # "단일 타겟", "신지도 리스트", "구지도 리스트", ""
    result_count: int = 0
    has_booking: bool = False
    booking_type: Optional[str] = None  # "realtime", "url"

    def to_dict(self) -> Dict:
        return {
            "keyword": self.keyword,
            "rank": self.rank,
            "tag": self.tag,
            "result_count": self.result_count,
            "has_booking": self.has_booking,
            "booking_type": self.booking_type,
        }

    def __str__(self) -> str:
        rank_str = f"{self.rank}위" if self.rank else "순위권외"
        booking_str = " [예약]" if self.has_booking else ""
        return f"{self.keyword} - {rank_str} - {self.tag}{booking_str}"


class KeywordChecker:
    """
    키워드 순위 + 태그 체커

    2단계 처리:
    1단계: GraphQL로 순위만 빠르게 체크
    2단계: 순위권 내 키워드만 HTML로 태그 확인
    """

    GRAPHQL_URL = "https://nx-api.place.naver.com/graphql"
    SEARCH_URL = "https://m.search.naver.com/search.naver"

    DEFAULT_X = "126.9783882"
    DEFAULT_Y = "37.5666103"

    def __init__(self, x: str = None, y: str = None):
        self.x = x or self.DEFAULT_X
        self.y = y or self.DEFAULT_Y
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
            headers={
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
                "Accept-Language": "ko-KR,ko;q=0.9",
            }
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    async def check(
        self,
        keywords: List[str],
        place_id: str,
        max_rank: int = 30,
        tag_all: bool = False  # True면 순위권 외도 태그 확인
    ) -> List[KeywordResult]:
        """
        키워드 순위 + 태그 체크

        Args:
            keywords: 키워드 리스트
            place_id: 업체 ID
            max_rank: 최대 순위 (이 이내만 태그 확인)
            tag_all: True면 모든 키워드 태그 확인 (느림)

        Returns:
            KeywordResult 리스트
        """
        # 1단계: 순위만 빠르게 체크 (GraphQL)
        rank_results = await self._batch_check_ranks(keywords, place_id, max_rank)

        # 순위권 내 키워드 필터링
        if tag_all:
            keywords_to_tag = keywords
        else:
            keywords_to_tag = [r.keyword for r in rank_results if r.rank is not None]

        # 2단계: 순위권 키워드만 태그 확인 (HTML)
        if keywords_to_tag:
            tags = await self._batch_check_tags(keywords_to_tag)

            # 태그 매핑
            tag_map = {kw: tag for kw, tag in zip(keywords_to_tag, tags)}
            for r in rank_results:
                if r.keyword in tag_map:
                    r.tag = tag_map[r.keyword]

        return rank_results

    async def _check_rank(
        self,
        keyword: str,
        place_id: str,
        max_rank: int
    ) -> KeywordResult:
        """단일 키워드 순위 체크 (GraphQL)"""
        result = KeywordResult(keyword=keyword, rank=None, tag="")

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
                            "y": self.y
                        }
                    }
                },
                headers={
                    "Content-Type": "application/json",
                    "Referer": "https://m.place.naver.com/",
                    "Origin": "https://m.place.naver.com",
                }
            )

            if resp.status_code == 200:
                data = resp.json()
                businesses = data.get("data", {}).get("businesses", {})
                items = businesses.get("items", [])
                total = businesses.get("total", 0)

                result.result_count = total

                # 순위 찾기
                for idx, item in enumerate(items, 1):
                    if str(item.get("id")) == str(place_id):
                        result.rank = idx
                        # 예약 정보
                        if item.get("naverBookingHubId"):
                            result.has_booking = True
                            result.booking_type = "realtime"
                        elif item.get("bookingUrl"):
                            result.has_booking = True
                            result.booking_type = "url"
                        break

        except Exception:
            pass

        return result

    async def _batch_check_ranks(
        self,
        keywords: List[str],
        place_id: str,
        max_rank: int,
        max_concurrent: int = 10
    ) -> List[KeywordResult]:
        """여러 키워드 순위 병렬 체크"""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def check_one(kw: str) -> KeywordResult:
            async with semaphore:
                return await self._check_rank(kw, place_id, max_rank)

        tasks = [check_one(kw) for kw in keywords]
        return await asyncio.gather(*tasks)

    async def _check_tag(self, keyword: str) -> str:
        """
        단일 키워드 태그 확인 (HTML)

        Returns:
            "단일 타겟" | "신지도 리스트" | "구지도 리스트"
        """
        try:
            resp = await self._client.get(
                self.SEARCH_URL,
                params={"query": keyword}
            )

            if resp.status_code != 200:
                return ""

            html = resp.text

            # 1. 결과 개수 확인
            total_match = re.search(r'"total"\s*:\s*(\d+)', html)
            total = int(total_match.group(1)) if total_match else 0

            # 단일 타겟 판정
            if total == 1:
                return "단일 타겟"

            # 2. queryType으로 신지도/구지도 판정
            qt_match = re.search(r'"queryType"\s*:\s*"([^"]+)"', html)

            if qt_match and qt_match.group(1):
                return "신지도 리스트"
            else:
                return "구지도 리스트"

        except Exception:
            return ""

    async def _batch_check_tags(
        self,
        keywords: List[str],
        max_concurrent: int = 5
    ) -> List[str]:
        """여러 키워드 태그 병렬 체크"""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def check_one(kw: str) -> str:
            async with semaphore:
                return await self._check_tag(kw)

        tasks = [check_one(kw) for kw in keywords]
        return await asyncio.gather(*tasks)


# 간편 함수
async def check_keywords(
    keywords: List[str],
    place_id: str,
    max_rank: int = 30
) -> List[Dict]:
    """간편 체크 함수"""
    async with KeywordChecker() as checker:
        results = await checker.check(keywords, place_id, max_rank)
        return [r.to_dict() for r in results]


# 테스트
if __name__ == "__main__":
    async def test():
        print("=" * 60)
        print("키워드 순위 + 태그 체커 v2")
        print("=" * 60)

        keywords = [
            "강남 맛집",
            "강남역 스테이크",
            "미도인 강남",
            "신논현 레스토랑",
            "강남 지도 맛집",
        ]
        place_id = "1427134948"

        print(f"\n업체 ID: {place_id}")
        print(f"키워드 수: {len(keywords)}개")
        print("-" * 60)

        async with KeywordChecker() as checker:
            results = await checker.check(
                keywords=keywords,
                place_id=place_id,
                max_rank=30
            )

            print(f"\n[결과]")
            print("-" * 60)
            for r in results:
                print(r)

        print("\n" + "=" * 60)

    asyncio.run(test())

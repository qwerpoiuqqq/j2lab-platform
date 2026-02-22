"""
키워드 형태(pll/plt/plr) + 순위 빠른 조회 모듈
백엔드 전용 - 브라우저 없이 API 요청만 사용

키워드 형태:
- pll (Place List): 일반 리스트 - 여러 업체가 리스트로 표시
- plt (Place List Target): 단일 타겟 - 결과가 1개만 표시 (브랜드/상호명 검색)
- plr (Place List Realtime): 실시간 예약 리스트

사용법:
    from src.keyword_type_checker import KeywordTypeChecker

    async with KeywordTypeChecker() as checker:
        # 단일 키워드 분석
        result = await checker.check("강남 맛집")
        print(result.keyword_type)  # "pll"

        # 순위 + 형태 함께 조회
        result = await checker.check_with_rank("강남 피부과", place_id="1234567")
        print(result["rank"], result["keyword_type"])

        # 배치 처리
        results = await checker.batch_check(["키워드1", "키워드2"])
"""

import asyncio
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime

try:
    import httpx
except ImportError:
    print("[KeywordTypeChecker] httpx 필요: pip install httpx")
    httpx = None


@dataclass
class KeywordCheckResult:
    """키워드 체크 결과"""
    keyword: str
    keyword_type: str  # pll, plt, plr, unknown
    result_count: int = 0
    query_type: Optional[str] = None  # restaurant, hospital, cafe, hairshop 등
    rank: Optional[int] = None  # 순위 (check_with_rank 사용 시)
    place_id: Optional[str] = None  # plt일 경우 해당 업체 ID
    place_name: Optional[str] = None  # plt일 경우 해당 업체명
    checked_at: str = field(default_factory=lambda: datetime.now().isoformat())
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "keyword": self.keyword,
            "keyword_type": self.keyword_type,
            "result_count": self.result_count,
            "query_type": self.query_type,
            "rank": self.rank,
            "place_id": self.place_id,
            "place_name": self.place_name,
            "checked_at": self.checked_at,
            "error": self.error,
        }


class KeywordTypeChecker:
    """
    키워드 형태 + 순위 빠른 체크 (API 전용)

    특징:
    - GraphQL API 사용으로 빠른 응답 (0.2~0.5초/키워드)
    - 브라우저 불필요
    - 형태(pll/plt)와 순위를 한 번에 조회
    """

    GRAPHQL_URL = "https://nx-api.place.naver.com/graphql"
    SEARCH_URL = "https://m.search.naver.com/search.naver"

    # 기본 좌표 (서울 중심)
    DEFAULT_X = "126.9783882"
    DEFAULT_Y = "37.5666103"

    USER_AGENTS = [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
        "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 Chrome/121.0.0.0 Mobile",
    ]

    def __init__(
        self,
        timeout: float = 15.0,
        default_max_rank: int = 30,
        x: str = None,
        y: str = None
    ):
        """
        Args:
            timeout: 요청 타임아웃 (초)
            default_max_rank: 기본 최대 순위 확인 범위
            x, y: 검색 기준 좌표 (위도/경도)
        """
        self.timeout = timeout
        self.default_max_rank = default_max_rank
        self.x = x or self.DEFAULT_X
        self.y = y or self.DEFAULT_Y
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        import random
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=True,
            headers={
                "User-Agent": random.choice(self.USER_AGENTS),
                "Accept": "application/json",
                "Accept-Language": "ko-KR,ko;q=0.9",
            }
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    async def check(self, keyword: str) -> KeywordCheckResult:
        """
        키워드 형태만 빠르게 체크 (순위 없이)

        Args:
            keyword: 검색 키워드

        Returns:
            KeywordCheckResult
        """
        result = KeywordCheckResult(keyword=keyword, keyword_type="unknown")

        try:
            gql_data = await self._graphql_search(keyword, display=5)

            if gql_data:
                total = gql_data.get("total", 0)
                items = gql_data.get("items", [])

                result.result_count = total

                if items:
                    result.query_type = items[0].get("businessCategory")

                    if total == 1 or len(items) == 1:
                        result.keyword_type = "plt"
                        result.place_id = str(items[0].get("id"))
                        result.place_name = items[0].get("name")
                    else:
                        result.keyword_type = "pll"
                else:
                    # 결과 없음
                    result.keyword_type = "pll"
                    result.result_count = 0
            else:
                result.error = "API 응답 없음"

        except Exception as e:
            result.error = str(e)

        return result

    async def check_with_rank(
        self,
        keyword: str,
        place_id: str,
        max_rank: int = None
    ) -> KeywordCheckResult:
        """
        키워드 형태 + 특정 업체 순위 함께 조회

        Args:
            keyword: 검색 키워드
            place_id: 순위를 확인할 업체 ID
            max_rank: 최대 순위 확인 범위

        Returns:
            KeywordCheckResult (rank 포함)
        """
        result = KeywordCheckResult(keyword=keyword, keyword_type="unknown")
        max_rank = max_rank or self.default_max_rank

        try:
            gql_data = await self._graphql_search(keyword, display=max_rank)

            if gql_data:
                total = gql_data.get("total", 0)
                items = gql_data.get("items", [])

                result.result_count = total

                # 형태 판단
                if total == 1:
                    result.keyword_type = "plt"
                else:
                    result.keyword_type = "pll"

                # 순위 찾기
                for idx, item in enumerate(items, 1):
                    if result.query_type is None:
                        result.query_type = item.get("businessCategory")

                    if str(item.get("id")) == str(place_id):
                        result.rank = idx
                        result.place_id = str(item.get("id"))
                        result.place_name = item.get("name")
                        break
            else:
                result.error = "API 응답 없음"

        except Exception as e:
            result.error = str(e)

        return result

    async def batch_check(
        self,
        keywords: List[str],
        place_id: Optional[str] = None,
        max_rank: int = None,
        delay: float = 0.2
    ) -> List[KeywordCheckResult]:
        """
        여러 키워드 일괄 체크

        Args:
            keywords: 키워드 리스트
            place_id: 순위 확인할 업체 ID (없으면 형태만 체크)
            max_rank: 최대 순위 범위
            delay: 요청 간 딜레이 (초)

        Returns:
            KeywordCheckResult 리스트
        """
        results = []

        for kw in keywords:
            if place_id:
                r = await self.check_with_rank(kw, place_id, max_rank)
            else:
                r = await self.check(kw)

            results.append(r)

            if delay > 0:
                await asyncio.sleep(delay)

        return results

    async def batch_check_parallel(
        self,
        keywords: List[str],
        place_id: Optional[str] = None,
        max_rank: int = None,
        max_concurrent: int = 5
    ) -> List[KeywordCheckResult]:
        """
        여러 키워드 병렬 체크 (더 빠름)

        Args:
            keywords: 키워드 리스트
            place_id: 순위 확인할 업체 ID
            max_rank: 최대 순위 범위
            max_concurrent: 최대 동시 요청 수

        Returns:
            KeywordCheckResult 리스트
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def check_one(kw: str) -> KeywordCheckResult:
            async with semaphore:
                if place_id:
                    return await self.check_with_rank(kw, place_id, max_rank)
                else:
                    return await self.check(kw)

        tasks = [check_one(kw) for kw in keywords]
        return await asyncio.gather(*tasks)

    async def _graphql_search(self, keyword: str, display: int) -> Optional[Dict]:
        """GraphQL API로 검색"""
        query = """
        query getPlacesList($input: PlacesInput) {
            businesses: nxPlaces(input: $input) {
                total
                items {
                    id
                    name
                    businessCategory
                }
            }
        }
        """

        variables = {
            "input": {
                "query": keyword,
                "display": display,
                "deviceType": "mobile",
                "x": self.x,
                "y": self.y
            }
        }

        try:
            resp = await self._client.post(
                self.GRAPHQL_URL,
                json={
                    "operationName": "getPlacesList",
                    "query": query,
                    "variables": variables
                },
                headers={
                    "Content-Type": "application/json",
                    "Referer": "https://m.place.naver.com/",
                    "Origin": "https://m.place.naver.com",
                }
            )

            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", {}).get("businesses", {})

        except Exception:
            pass

        return None


# 간편 함수들
async def check_keyword_type(keyword: str) -> Dict[str, Any]:
    """
    단일 키워드 형태 체크 (간편 함수)

    Returns:
        {"keyword": str, "keyword_type": str, "result_count": int, ...}
    """
    async with KeywordTypeChecker() as checker:
        result = await checker.check(keyword)
        return result.to_dict()


async def check_keyword_rank(
    keyword: str,
    place_id: str,
    max_rank: int = 30
) -> Dict[str, Any]:
    """
    키워드 형태 + 순위 체크 (간편 함수)

    Returns:
        {"keyword": str, "keyword_type": str, "rank": int, ...}
    """
    async with KeywordTypeChecker() as checker:
        result = await checker.check_with_rank(keyword, place_id, max_rank)
        return result.to_dict()


async def batch_check_keywords(
    keywords: List[str],
    place_id: Optional[str] = None,
    max_rank: int = 30,
    parallel: bool = True
) -> List[Dict[str, Any]]:
    """
    여러 키워드 일괄 체크 (간편 함수)

    Args:
        keywords: 키워드 리스트
        place_id: 순위 확인할 업체 ID (없으면 형태만)
        max_rank: 최대 순위 범위
        parallel: True면 병렬 처리

    Returns:
        결과 딕셔너리 리스트
    """
    async with KeywordTypeChecker() as checker:
        if parallel:
            results = await checker.batch_check_parallel(keywords, place_id, max_rank)
        else:
            results = await checker.batch_check(keywords, place_id, max_rank)

        return [r.to_dict() for r in results]


# 동기 래퍼 (기존 코드와 호환)
def check_keyword_type_sync(keyword: str) -> Dict[str, Any]:
    """동기 버전 - 형태만 체크"""
    return asyncio.run(check_keyword_type(keyword))


def check_keyword_rank_sync(
    keyword: str,
    place_id: str,
    max_rank: int = 30
) -> Dict[str, Any]:
    """동기 버전 - 순위 + 형태 체크"""
    return asyncio.run(check_keyword_rank(keyword, place_id, max_rank))


def batch_check_keywords_sync(
    keywords: List[str],
    place_id: Optional[str] = None,
    max_rank: int = 30
) -> List[Dict[str, Any]]:
    """동기 버전 - 배치 체크"""
    return asyncio.run(batch_check_keywords(keywords, place_id, max_rank))


# 테스트
if __name__ == "__main__":
    async def test():
        print("=" * 60)
        print("KeywordTypeChecker 테스트")
        print("=" * 60)

        async with KeywordTypeChecker() as checker:
            # 테스트 키워드들
            test_keywords = [
                "강남 맛집",       # pll 예상
                "미도인 강남",     # plt 예상 (상호명)
                "서초구 피부과",   # pll 예상
            ]

            print("\n[형태 분석]")
            print("-" * 60)

            for kw in test_keywords:
                result = await checker.check(kw)
                type_marker = "[PLT]" if result.keyword_type == "plt" else "[PLL]"
                print(f"{type_marker} {kw}")
                print(f"   형태: {result.keyword_type} | 결과: {result.result_count}개 | 카테고리: {result.query_type}")
                if result.place_name:
                    print(f"   업체: {result.place_name}")
                print()

            # 순위 + 형태 함께 조회
            print("\n[순위 + 형태 통합]")
            print("-" * 60)

            result = await checker.check_with_rank(
                keyword="강남 피부과",
                place_id="12927872",  # 예시 ID
                max_rank=30
            )
            print(f"키워드: {result.keyword}")
            print(f"형태: {result.keyword_type}")
            print(f"순위: {result.rank or '순위권 외'}")
            print(f"결과 수: {result.result_count}")

            # 배치 처리 성능 테스트
            print("\n[배치 성능 테스트]")
            print("-" * 60)

            import time
            start = time.time()

            batch_results = await checker.batch_check_parallel(
                keywords=["강남 맛집", "서초 맛집", "송파 맛집", "강동 맛집", "관악 맛집"],
                place_id=None
            )

            elapsed = time.time() - start
            print(f"5개 키워드 병렬 처리: {elapsed:.2f}초")
            print(f"키워드당 평균: {elapsed/5:.2f}초")

        print("\n" + "=" * 60)
        print("테스트 완료!")

    asyncio.run(test())

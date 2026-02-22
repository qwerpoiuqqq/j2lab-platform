"""
키워드 순위 + 형태 + 예약 키워드 자동 생성 통합 모듈
백엔드 전용 - 브라우저 없이 API 요청만 사용

주요 기능:
1. 키워드 형태 구분 (pll/plt)
2. 업체 순위 조회
3. 예약 가능 업체 자동 감지
4. 예약 키워드 자동 생성

사용법:
    from src.keyword_rank_checker import KeywordRankChecker

    async with KeywordRankChecker() as checker:
        # 순위 + 형태 + 예약 키워드 한 번에
        result = await checker.full_check(
            keywords=["강남 맛집", "강남역 스테이크"],
            place_id="1234567"
        )
        print(result["ranks"])           # 순위 결과
        print(result["booking_keywords"]) # 자동 생성된 예약 키워드
"""

import asyncio
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime

try:
    import httpx
except ImportError:
    print("[KeywordRankChecker] httpx 필요: pip install httpx")
    httpx = None


@dataclass
class PlaceInfo:
    """업체 정보"""
    place_id: str
    name: str = ""
    category: str = ""  # restaurant, hospital, cafe, hairshop 등
    has_booking: bool = False
    booking_type: Optional[str] = None  # "realtime" 또는 "url"
    booking_hub_id: Optional[str] = None
    booking_url: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "place_id": self.place_id,
            "name": self.name,
            "category": self.category,
            "has_booking": self.has_booking,
            "booking_type": self.booking_type,
            "booking_hub_id": self.booking_hub_id,
            "booking_url": self.booking_url,
        }


@dataclass
class RankCheckResult:
    """순위 체크 결과"""
    keyword: str
    keyword_type: str  # "pll" 또는 "plt"
    rank: Optional[int] = None
    result_count: int = 0
    query_type: Optional[str] = None  # restaurant, hospital, cafe 등
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


class KeywordRankChecker:
    """
    키워드 순위 + 형태 + 예약 키워드 통합 체커

    특징:
    - GraphQL API로 빠른 조회 (키워드당 0.05초)
    - 예약 가능 업체 자동 감지
    - 예약 키워드 자동 생성
    """

    GRAPHQL_URL = "https://nx-api.place.naver.com/graphql"

    # 기본 좌표 (서울 중심)
    DEFAULT_X = "126.9783882"
    DEFAULT_Y = "37.5666103"

    # 예약 키워드 접미사 (realtime일 때만 "실시간 예약" 사용)
    BOOKING_SUFFIX = "실시간 예약"

    def __init__(
        self,
        timeout: float = 15.0,
        default_max_rank: int = 30,
        x: str = None,
        y: str = None,
        booking_keyword_ratio: float = 0.1  # 실시간 예약 키워드 비율 (기본 10%)
    ):
        self.timeout = timeout
        self.default_max_rank = default_max_rank
        self.x = x or self.DEFAULT_X
        self.y = y or self.DEFAULT_Y
        self.booking_keyword_ratio = booking_keyword_ratio
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            headers={
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
                "Accept": "application/json",
                "Accept-Language": "ko-KR,ko;q=0.9",
            }
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    async def get_place_info(self, place_id: str) -> Optional[PlaceInfo]:
        """업체 정보 + 예약 가능 여부 조회"""
        query = """
        query getPlaceDetail($input: PlaceDetailInput) {
            placeDetail(input: $input) {
                id
                name
                category
                businessCategory
                naverBookingHubId
                bookingUrl
            }
        }
        """

        try:
            resp = await self._client.post(
                self.GRAPHQL_URL,
                json={
                    "operationName": "getPlaceDetail",
                    "query": query,
                    "variables": {"input": {"placeId": place_id, "deviceType": "mobile"}}
                },
                headers={
                    "Content-Type": "application/json",
                    "Referer": "https://m.place.naver.com/",
                    "Origin": "https://m.place.naver.com",
                }
            )

            if resp.status_code == 200:
                data = resp.json()
                detail = data.get("data", {}).get("placeDetail", {})

                if detail:
                    has_booking = bool(detail.get("naverBookingHubId") or detail.get("bookingUrl"))
                    booking_type = "realtime" if detail.get("naverBookingHubId") else ("url" if detail.get("bookingUrl") else None)

                    return PlaceInfo(
                        place_id=place_id,
                        name=detail.get("name", ""),
                        category=detail.get("businessCategory") or detail.get("category", ""),
                        has_booking=has_booking,
                        booking_type=booking_type,
                        booking_hub_id=detail.get("naverBookingHubId"),
                        booking_url=detail.get("bookingUrl")
                    )
        except Exception:
            pass

        return None

    SEARCH_URL = "https://m.search.naver.com/search.naver"

    async def check_map_type(self, keyword: str) -> str:
        """
        HTML에서 지도 형태 확인 (queryType 기반)
        Returns: "신지도" 또는 "구지도"
        """
        try:
            resp = await self._client.get(
                self.SEARCH_URL,
                params={"query": keyword},
                headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"}
            )

            if resp.status_code == 200:
                import re
                html = resp.text
                # queryType이 있으면 신지도
                qt_match = re.search(r'"queryType"\s*:\s*"([^"]+)"', html)
                if qt_match and qt_match.group(1):
                    return "신지도"

            return "구지도"

        except Exception:
            return "구지도"

    async def check_rank(
        self,
        keyword: str,
        place_id: str,
        max_rank: int = None,
        map_type: str = None  # 이미 알고 있으면 전달 (요청 최소화)
    ) -> tuple:
        """
        단일 키워드 순위 + 형태 조회
        Returns: (RankCheckResult, PlaceInfo or None)

        키워드 형태:
        - plt: 타겟 키워드 (결과 1개)
        - pll: 리스트 키워드 (결과 여러 개)
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

                # 첫 번째 아이템의 businessCategory
                if items:
                    result.query_type = items[0].get("businessCategory")

                # 키워드 형태: plt(결과 1개) vs pll(여러 개)
                result.keyword_type = "plt" if total == 1 else "pll"

                # 지도 형태: 전달받은 값 사용 또는 비워둠
                result.map_type = map_type or ""

                # place_id 순위 찾기
                for idx, item in enumerate(items, 1):
                    if str(item.get("id")) == str(place_id):
                        result.rank = idx
                        # 검색 결과에서 예약 정보 추출
                        has_booking = bool(item.get("naverBookingHubId") or item.get("bookingUrl"))
                        booking_type = "realtime" if item.get("naverBookingHubId") else ("url" if item.get("bookingUrl") else None)

                        place_info = PlaceInfo(
                            place_id=str(item.get("id")),
                            name=item.get("name", ""),
                            category=item.get("businessCategory", ""),
                            has_booking=has_booking,
                            booking_type=booking_type,
                            booking_hub_id=item.get("naverBookingHubId"),
                            booking_url=item.get("bookingUrl")
                        )
                        break

        except Exception as e:
            result.error = str(e)

        return result, place_info

    async def batch_check_ranks(
        self,
        keywords: List[str],
        place_id: str,
        max_rank: int = None,
        max_concurrent: int = 5,
        map_type: str = ""  # 지도 형태 (이미 확인된 값)
    ) -> tuple:
        """
        여러 키워드 병렬 순위 조회
        Returns: (List[RankCheckResult], PlaceInfo or None)
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        found_place_info = None

        async def check_one(kw: str) -> RankCheckResult:
            nonlocal found_place_info
            async with semaphore:
                result, place_info = await self.check_rank(kw, place_id, max_rank, map_type)
                if place_info and not found_place_info:
                    found_place_info = place_info
                return result

        tasks = [check_one(kw) for kw in keywords]
        results = await asyncio.gather(*tasks)
        return results, found_place_info

    # 실시간 예약 키워드 적용 대상 업종 (restaurant 계열)
    BOOKING_ELIGIBLE_CATEGORIES = [
        "restaurant", "음식점", "맛집", "식당", "카페", "cafe",
        "한식", "양식", "일식", "중식", "분식", "뷔페", "고기", "회",
    ]

    def _is_restaurant_category(self, category: str) -> bool:
        """restaurant 계열 업종인지 확인"""
        if not category:
            return False
        category_lower = category.lower()
        return any(cat in category_lower for cat in self.BOOKING_ELIGIBLE_CATEGORIES)

    def generate_booking_keywords(
        self,
        keywords: List[str],
        place_info: PlaceInfo = None,
        rank_results: List[RankCheckResult] = None,
        ratio: float = None,
        map_type: str = ""
    ) -> tuple:
        """
        restaurant 업종의 신지도 리스트 키워드 일부를 "실시간 예약" 버전으로 교체

        Args:
            keywords: 기본 키워드 리스트
            place_info: 업체 정보 (업종 확인용)
            rank_results: 순위 체크 결과 (신지도 리스트 필터링용)
            ratio: 실시간 예약 키워드 비율 (None이면 self.booking_keyword_ratio 사용)
            map_type: 지도 형태 ("신지도" 또는 "구지도")

        Returns:
            tuple: (final_keywords, booking_keywords, replaced_keywords)
            - final_keywords: 최종 키워드 리스트 (총 개수 유지, 일부가 실시간 예약 버전으로 교체됨)
            - booking_keywords: 생성된 실시간 예약 키워드 리스트
            - replaced_keywords: 교체된 원본 키워드 리스트

        Example:
            총 200개 키워드, ratio=0.1 → 20개가 "실시간 예약" 버전으로 교체
            최종 결과: 180개 일반 + 20개 실시간예약 = 200개 (총 개수 유지)
        """
        # 기본 반환값 (변경 없음)
        if not keywords:
            return list(keywords), [], []

        # 업종 확인: restaurant 계열이 아니면 변경 없이 반환
        category = ""
        if place_info:
            category = place_info.category or ""
        elif rank_results:
            # rank_results에서 query_type 확인
            for r in rank_results:
                if r.query_type:
                    category = r.query_type
                    break

        if not self._is_restaurant_category(category):
            return list(keywords), [], []

        ratio = ratio if ratio is not None else self.booking_keyword_ratio

        # 신지도 리스트 키워드만 필터링
        eligible_keywords = []

        if rank_results:
            # rank_results에서 신지도 리스트인 키워드만 추출
            keyword_to_result = {r.keyword: r for r in rank_results}
            for kw in keywords:
                result = keyword_to_result.get(kw)
                if result:
                    # 신지도(map_type="신지도")이고 리스트 형태(result_count > 1)인 경우
                    is_new_map = result.map_type == "신지도" or map_type == "신지도"
                    is_list_type = result.result_count > 1

                    if is_new_map and is_list_type:
                        if "예약" not in kw:  # 이미 예약이 포함된 키워드 제외
                            eligible_keywords.append(kw)
        else:
            # rank_results가 없으면 map_type이 신지도일 때만 모든 키워드 대상
            if map_type == "신지도":
                eligible_keywords = [kw for kw in keywords if "예약" not in kw]

        if not eligible_keywords:
            return list(keywords), [], []

        # 비율에 따라 교체할 키워드 수 계산
        total_keywords = len(keywords)
        booking_count = max(1, int(total_keywords * ratio))  # 최소 1개

        # eligible_keywords에서 booking_count만큼 선택 (교체 대상)
        replaced_keywords = eligible_keywords[:booking_count]

        # "실시간 예약" 접미사 추가
        booking_keywords = [f"{kw} {self.BOOKING_SUFFIX}" for kw in replaced_keywords]

        # 최종 키워드 리스트: 교체 대상 제외 + 실시간 예약 키워드
        replaced_set = set(replaced_keywords)
        remaining_keywords = [kw for kw in keywords if kw not in replaced_set]
        final_keywords = remaining_keywords + booking_keywords

        return final_keywords, booking_keywords, replaced_keywords

    async def full_check(
        self,
        keywords: List[str],
        place_id: str,
        max_rank: int = None,
        auto_booking_keywords: bool = True,
        check_map_type: bool = True,  # 지도 형태 확인 (HTML 요청 1회 추가)
        booking_keyword_ratio: float = None  # 실시간 예약 키워드 비율 (None이면 기본값 사용)
    ) -> Dict[str, Any]:
        """
        통합 체크: 순위 + 형태 + 예약 키워드

        Args:
            keywords: 기본 키워드 리스트
            place_id: 업체 ID
            max_rank: 최대 순위 범위
            auto_booking_keywords: 예약 키워드 자동 생성 여부
            check_map_type: True면 첫 번째 키워드로 지도 형태 확인
            booking_keyword_ratio: 실시간 예약 키워드 비율 (0.0 ~ 1.0, None이면 기본값 0.1)

        Returns:
            {
                "place_info": {...},        # 업체 정보
                "map_type": "신지도",        # 지도 형태
                "ranks": [...],             # 순위 결과 (기본 키워드만)
                "booking_keywords": [...],  # 생성된 실시간 예약 키워드
                "replaced_keywords": [...], # 교체된 원본 키워드
                "all_keywords": [...],      # 최종 키워드 (총 개수 유지, 일부가 실시간 예약으로 교체)
            }

        Example:
            입력: 200개 키워드, ratio=0.1
            출력: all_keywords = 180개 일반 + 20개 실시간예약 = 200개 (총 개수 유지)
        """
        result = {
            "place_info": None,
            "map_type": "",
            "ranks": [],
            "booking_keywords": [],
            "replaced_keywords": [],
            "all_keywords": list(keywords),
        }

        # 0. 지도 형태 확인 (첫 번째 키워드로 1회만)
        map_type = ""
        if check_map_type and keywords:
            map_type = await self.check_map_type(keywords[0])
            result["map_type"] = map_type

        # 1. 기본 키워드로 순위 조회 (+ 업체 정보 추출)
        base_ranks, place_info = await self.batch_check_ranks(
            keywords,
            place_id,
            max_rank,
            map_type=map_type  # 지도 형태 전달
        )

        if place_info:
            result["place_info"] = place_info.to_dict()

        # 2. 신지도 리스트 키워드 일부를 "실시간 예약" 버전으로 교체
        # - restaurant 업종 + 신지도 리스트 키워드만 대상
        # - booking_keyword_ratio 비율만큼 교체 (총 개수는 유지)
        # - 예: 200개 중 10% = 20개가 "실시간 예약" 버전으로 교체
        if auto_booking_keywords:
            final_kws, booking_kws, replaced_kws = self.generate_booking_keywords(
                keywords,
                place_info=place_info,
                rank_results=base_ranks,  # 순위 결과 전달 (신지도 리스트 필터링용)
                ratio=booking_keyword_ratio,  # 비율 파라미터 전달
                map_type=map_type  # 지도 형태 전달
            )
            result["booking_keywords"] = booking_kws
            result["replaced_keywords"] = replaced_kws  # 교체된 원본 키워드
            result["all_keywords"] = final_kws  # 총 개수 유지 (일부가 실시간 예약으로 교체됨)
        else:
            result["all_keywords"] = list(keywords)

        # 순위 결과는 기본 키워드만 (예약 키워드는 순위 조회 안함)
        result["ranks"] = [r.to_dict() for r in base_ranks]

        return result


# 간편 함수
async def quick_check(
    keywords: List[str],
    place_id: str,
    max_rank: int = 30,
    auto_booking: bool = True,
    booking_keyword_ratio: float = 0.1  # 실시간 예약 키워드 비율
) -> Dict[str, Any]:
    """
    간편 통합 체크

    Args:
        keywords: 키워드 리스트
        place_id: 업체 ID
        max_rank: 최대 순위 범위
        auto_booking: 예약 키워드 자동 생성 여부
        booking_keyword_ratio: 실시간 예약 키워드 비율 (0.0 ~ 1.0, 기본 0.1 = 10%)

    Example:
        result = await quick_check(
            keywords=["강남 맛집", "강남역 맛집"],
            place_id="1234567",
            booking_keyword_ratio=0.15  # 15% 비율
        )
    """
    async with KeywordRankChecker(booking_keyword_ratio=booking_keyword_ratio) as checker:
        return await checker.full_check(
            keywords=keywords,
            place_id=place_id,
            max_rank=max_rank,
            auto_booking_keywords=auto_booking
        )


def quick_check_sync(
    keywords: List[str],
    place_id: str,
    max_rank: int = 30,
    auto_booking: bool = True,
    booking_keyword_ratio: float = 0.1
) -> Dict[str, Any]:
    """동기 버전"""
    return asyncio.run(quick_check(keywords, place_id, max_rank, auto_booking, booking_keyword_ratio))


# 테스트
if __name__ == "__main__":
    async def test():
        print("=" * 70)
        print("KeywordRankChecker 통합 테스트")
        print("=" * 70)

        # booking_keyword_ratio: 실시간 예약 키워드 비율 (기본 0.1 = 10%)
        # 33%로 설정하면 3개 중 1개가 실시간 예약으로 교체
        async with KeywordRankChecker(booking_keyword_ratio=0.34) as checker:
            # 테스트: 미도인 강남
            keywords = ["강남 맛집", "강남역 스테이크", "신논현 레스토랑"]
            place_id = "1427134948"

            print(f"\n[테스트] place_id: {place_id}")
            print(f"입력 키워드: {keywords} ({len(keywords)}개)")
            print(f"실시간 예약 키워드 비율: {checker.booking_keyword_ratio * 100:.0f}%")
            print("-" * 50)

            result = await checker.full_check(
                keywords=keywords,
                place_id=place_id,
                max_rank=30,
                auto_booking_keywords=True
            )

            # 지도 형태
            print(f"\n[지도 형태] {result['map_type']}")

            # 업체 정보
            if result["place_info"]:
                info = result["place_info"]
                print(f"\n[업체 정보]")
                print(f"  이름: {info['name']}")
                print(f"  카테고리: {info['category']}")

            # 키워드 교체 결과
            print(f"\n[키워드 교체 결과]")
            print(f"  입력 키워드 수: {len(keywords)}개")
            print(f"  교체된 키워드: {result.get('replaced_keywords', [])}")
            print(f"  실시간 예약 키워드: {result['booking_keywords']}")
            print(f"  최종 키워드 수: {len(result['all_keywords'])}개")

            # 최종 키워드 목록
            print(f"\n[최종 키워드 목록] ({len(result['all_keywords'])}개)")
            for i, kw in enumerate(result['all_keywords'], 1):
                tag = " ← 실시간 예약" if "실시간 예약" in kw else ""
                print(f"  {i}. {kw}{tag}")

            # 검증
            print(f"\n[검증]")
            input_count = len(keywords)
            output_count = len(result['all_keywords'])
            booking_count = len(result['booking_keywords'])
            expected_booking = max(1, int(input_count * checker.booking_keyword_ratio))

            print(f"  입력={input_count}, 출력={output_count}, 실시간예약={booking_count}")
            if input_count == output_count:
                print(f"  ✅ 총 개수 유지됨 ({input_count}개)")
            else:
                print(f"  ❌ 총 개수 불일치 (입력:{input_count} != 출력:{output_count})")

        print("\n" + "=" * 70)
        print("테스트 완료!")

    asyncio.run(test())

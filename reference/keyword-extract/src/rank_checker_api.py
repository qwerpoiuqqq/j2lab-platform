"""
네이버 플레이스 순위 체크 엔진 - API 직접 호출 버전
브라우저 없이 HTTP 요청으로 순위를 확인하여 속도 10배 향상

[주요 개선점]
- Playwright 브라우저 대신 aiohttp 사용
- 키워드당 0.3~0.5초 (기존 3~5초)
- 병렬 처리로 추가 속도 향상
"""

import asyncio
import random
import time
import re
import json
from dataclasses import dataclass
from typing import List, Optional, Dict, Callable
from urllib.parse import quote

try:
    import aiohttp
except ImportError:
    print("[RankCheckerAPI] aiohttp가 설치되지 않았습니다. pip install aiohttp 실행 필요")
    aiohttp = None


@dataclass
class RankResult:
    """순위 체크 결과"""
    keyword: str
    rank: Optional[int] = None  # None = 순위권 외
    map_type: str = ""  # "신지도" or "구지도"
    status: str = "pending"  # pending, found, not_found, error
    error_message: str = ""


@dataclass
class ProxyConfig:
    """프록시 설정"""
    host: str
    port: int
    username: str = ""
    password: str = ""
    proxy_type: str = "datacenter"

    @property
    def url(self) -> str:
        if self.username and self.password:
            return f"http://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"http://{self.host}:{self.port}"

    @property
    def is_decodo(self) -> bool:
        return self.proxy_type.lower() == "decodo"


class RankCheckerAPI:
    """
    네이버 플레이스 순위 체크 엔진 - API 직접 호출 버전

    브라우저 없이 HTTP 요청만으로 순위를 확인합니다.
    """

    # 모바일 User-Agent 목록
    USER_AGENTS = [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
    ]

    # 네이버 플레이스 검색 API 엔드포인트
    # 방법 1: 통합검색 HTML 파싱 (안정적)
    SEARCH_URL = "https://m.search.naver.com/search.naver"

    # 방법 2: 플레이스 리스트 API (더 빠름, 차단 위험 있음)
    PLACE_LIST_API = "https://m.place.naver.com/place/list"

    # 방법 3: 네이버 지도 API (가장 정확, 헤더 필요)
    MAP_SEARCH_API = "https://map.naver.com/p/api/search/allSearch"

    def __init__(
        self,
        proxies: List[ProxyConfig] = None,
        max_workers: int = 5,
        use_api_mode: bool = True,  # True: API 직접, False: HTML 파싱
        debug: bool = False  # 디버그 모드: HTML 응답 저장
    ):
        """
        Args:
            proxies: 프록시 설정 리스트 (None이면 직접 연결)
            max_workers: 최대 동시 워커 수
            use_api_mode: True면 API 직접 호출, False면 HTML 파싱
            debug: True면 HTML 응답을 파일로 저장 (디버깅용)
        """
        self.proxies = proxies or []
        self.max_workers = max_workers
        self.use_api_mode = use_api_mode
        self.debug = debug
        self._progress_callback: Optional[Callable] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._stop_flag = False

        # 디버그 모드 디렉토리 생성
        if self.debug:
            import os
            self._debug_dir = os.path.join(os.path.dirname(__file__), "..", "debug_html")
            os.makedirs(self._debug_dir, exist_ok=True)
            print(f"[RankCheckerAPI] 디버그 모드 활성화. HTML 저장 경로: {self._debug_dir}")

    def set_progress_callback(self, callback: Callable[[int, int, str], None]):
        """진행 상황 콜백 설정 (current, total, message)"""
        self._progress_callback = callback

    def stop(self):
        """작업 중단"""
        self._stop_flag = True

    async def __aenter__(self):
        await self._init_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._close_session()

    async def _init_session(self):
        """aiohttp 세션 초기화"""
        if aiohttp is None:
            raise ImportError("aiohttp가 설치되지 않았습니다. pip install aiohttp")

        # 커넥션 풀 설정
        connector = aiohttp.TCPConnector(
            limit=self.max_workers * 2,
            limit_per_host=self.max_workers,
            ttl_dns_cache=300
        )

        timeout = aiohttp.ClientTimeout(total=15, connect=5)

        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        )

    async def _close_session(self):
        """세션 종료"""
        if self._session:
            await self._session.close()

    def _get_headers(self) -> Dict[str, str]:
        """요청 헤더 생성"""
        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate",  # br(Brotli) 제거 - Brotli 라이브러리 미설치 시 오류 방지
            "Connection": "keep-alive",
            "Referer": "https://m.naver.com/",
        }

    async def _check_single_keyword_html(
        self,
        keyword: str,
        target_place_id: str,
        max_rank: int
    ) -> RankResult:
        """
        단일 키워드 순위 체크 - HTML 파싱 방식 (안정적)

        네이버 모바일 통합검색 결과 HTML에서 플레이스 ID를 찾습니다.
        4가지 지도 형태를 모두 처리합니다.
        """
        result = RankResult(keyword=keyword)

        try:
            # 프록시 선택
            proxy = None
            if self.proxies:
                proxy_config = random.choice(self.proxies)
                proxy = proxy_config.url

            # 검색 요청
            params = {"query": keyword}
            async with self._session.get(
                self.SEARCH_URL,
                params=params,
                headers=self._get_headers(),
                proxy=proxy
            ) as response:
                if response.status != 200:
                    result.status = "error"
                    result.error_message = f"HTTP {response.status}"
                    # 디버그: 에러 응답도 저장
                    if self.debug:
                        error_html = await response.text()
                        self._save_debug_html(keyword, error_html, f"error_{response.status}")
                    return result

                html = await response.text()

            # 디버그 모드: HTML 응답 저장
            if self.debug:
                self._save_debug_html(keyword, html)
                print(f"[DEBUG] {keyword}: HTML 길이={len(html)}, 저장 완료")

            # HTML 길이 체크 (빈 응답 감지)
            if len(html) < 1000:
                result.status = "error"
                result.error_message = f"응답이 너무 짧음 ({len(html)} bytes) - 차단 가능성"
                return result

            # 지도 형태 감지 (4가지 형태 구분)
            map_type, is_single = self._detect_map_type_from_html(html)
            result.map_type = f"{map_type}(단일)" if is_single else map_type

            # === 단일 지도인 경우: 해당 업체가 1위 ===
            if is_single:
                # 단일 상세 페이지에서 place ID 추출
                single_id = self._extract_single_place_id(html)
                if single_id == target_place_id:
                    result.rank = 1
                    result.status = "found"
                    return result
                else:
                    result.status = "not_found"
                    return result

            # === 리스트 지도인 경우: 순위 확인 ===
            # 여러 방법으로 ID 추출 (폴백 체인)

            all_ids = []
            seen = set()

            # 방법 1: data-nmb_res-doc-id 속성 (가장 정확, 광고 제외됨)
            pattern_organic = r'data-nmb_res-doc-id="(\d+)"'
            for pid in re.findall(pattern_organic, html):
                if pid not in seen:
                    all_ids.append(pid)
                    seen.add(pid)

            # 방법 2: place.naver.com URL에서 ID 추출 (단순화된 패턴)
            # hospital, restaurant, place, hairshop, cafe, beauty 등 모든 타입 지원
            pattern_url = r'place\.naver\.com/\w+/(\d+)'
            for pid in re.findall(pattern_url, html):
                if pid not in seen:
                    all_ids.append(pid)
                    seen.add(pid)

            # 광고 ID 제외 (data-nmb_rese-doc-id - 'rese'에 주의)
            pattern_ad = r'data-nmb_rese-doc-id="(\d+)"'
            ad_ids = set(re.findall(pattern_ad, html))
            all_ids = [pid for pid in all_ids if pid not in ad_ids]

            # 순위 확인
            for rank, pid in enumerate(all_ids[:max_rank], 1):
                if pid == target_place_id:
                    result.rank = rank
                    result.status = "found"
                    return result

            result.status = "not_found"

            # 디버그: 추출된 ID 로깅
            if self.debug:
                print(f"[DEBUG] {keyword}: 추출된 ID 수={len(all_ids)}, 광고 ID 수={len(ad_ids)}")
                if all_ids[:5]:
                    print(f"[DEBUG] {keyword}: 상위 5개 ID = {all_ids[:5]}")

        except asyncio.TimeoutError:
            result.status = "error"
            result.error_message = "Timeout (15초 초과)"
        except aiohttp.ClientError as e:
            result.status = "error"
            result.error_message = f"Network: {type(e).__name__} - {str(e)[:100]}"
        except Exception as e:
            result.status = "error"
            result.error_message = f"Unknown: {type(e).__name__} - {str(e)[:100]}"
            if self.debug:
                import traceback
                print(f"[DEBUG ERROR] {keyword}: {traceback.format_exc()}")

        return result

    def _save_debug_html(self, keyword: str, html: str, suffix: str = ""):
        """디버그용 HTML 파일 저장"""
        import os
        import re as regex
        # 파일명에 사용할 수 없는 문자 제거
        safe_keyword = regex.sub(r'[\\/*?:"<>|]', '_', keyword)
        filename = f"debug_{safe_keyword}{f'_{suffix}' if suffix else ''}.html"
        filepath = os.path.join(self._debug_dir, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html)
        except Exception as e:
            print(f"[DEBUG] HTML 저장 실패: {e}")

    def _extract_single_place_id(self, html: str) -> Optional[str]:
        """단일 상세 페이지에서 place ID 추출"""
        # Apollo State에서 PlaceDetailBase:ID 형태로 저장됨
        pattern_apollo = r'PlaceDetailBase:(\d+)'
        match = re.search(pattern_apollo, html)
        if match:
            return match.group(1)

        # URL에서 추출
        pattern_url = r'place\.naver\.com/(?:place|restaurant|hospital|hairshop|cafe|beauty)/(\d+)'
        match = re.search(pattern_url, html)
        if match:
            return match.group(1)

        return None

    async def _check_single_keyword_api(
        self,
        keyword: str,
        target_place_id: str,
        max_rank: int
    ) -> RankResult:
        """
        단일 키워드 순위 체크 - API 직접 호출 방식 (빠름)

        네이버 지도/플레이스 내부 API를 직접 호출합니다.
        4가지 지도 형태를 모두 처리합니다.
        """
        result = RankResult(keyword=keyword)

        try:
            proxy = None
            if self.proxies:
                proxy_config = random.choice(self.proxies)
                proxy = proxy_config.url

            # 플레이스 리스트 API 호출
            params = {
                "query": keyword,
                "display": str(max_rank)
            }

            headers = self._get_headers()
            headers["Referer"] = "https://m.place.naver.com/"

            async with self._session.get(
                self.PLACE_LIST_API,
                params=params,
                headers=headers,
                proxy=proxy
            ) as response:
                if response.status != 200:
                    # API 실패 시 HTML 파싱으로 폴백
                    return await self._check_single_keyword_html(
                        keyword, target_place_id, max_rank
                    )

                html = await response.text()

            # 디버그 모드: HTML 응답 저장 (API 모드)
            if self.debug:
                self._save_debug_html(keyword, html, "api")
                print(f"[DEBUG API] {keyword}: HTML 길이={len(html)}, 저장 완료")

            # HTML 길이 체크 (빈 응답 감지)
            if len(html) < 500:
                result.status = "error"
                result.error_message = f"API 응답이 너무 짧음 ({len(html)} bytes)"
                # HTML 파싱 모드로 폴백
                return await self._check_single_keyword_html(keyword, target_place_id, max_rank)

            # 지도 형태 감지 (4가지 형태 구분)
            map_type, is_single = self._detect_map_type_from_html(html)
            result.map_type = f"{map_type}(단일)" if is_single else map_type

            # 디버그: 감지 결과 출력
            if self.debug:
                print(f"[DEBUG API] {keyword}: 지도형태={map_type}, 단일={is_single}")

            # === 단일 지도인 경우: 해당 업체가 1위 ===
            if is_single:
                single_id = self._extract_single_place_id(html)
                if self.debug:
                    print(f"[DEBUG API] {keyword}: 단일 페이지 ID={single_id}, 타겟={target_place_id}")
                if single_id == target_place_id:
                    result.rank = 1
                    result.status = "found"
                    return result
                else:
                    result.status = "not_found"
                    return result

            # === 리스트 지도인 경우 ===
            # Apollo State 파싱 시도
            apollo_match = re.search(r'window\.__APOLLO_STATE__\s*=\s*(\{.+?\});', html, re.DOTALL)
            if apollo_match:
                try:
                    apollo_data = json.loads(apollo_match.group(1))
                    rank = self._find_place_in_apollo_improved(apollo_data, target_place_id, max_rank)
                    if rank:
                        result.rank = rank
                        result.status = "found"
                        return result
                except json.JSONDecodeError:
                    pass

            # Apollo 파싱 실패 시 HTML에서 직접 찾기 (광고 제외)
            # 여러 방법으로 ID 추출 (폴백 체인)
            all_ids = []
            seen = set()

            # 방법 1: data 속성
            for pid in re.findall(r'data-nmb_res-doc-id="(\d+)"', html):
                if pid not in seen:
                    all_ids.append(pid)
                    seen.add(pid)

            # 방법 2: URL에서 추출 (단순화된 패턴)
            for pid in re.findall(r'place\.naver\.com/\w+/(\d+)', html):
                if pid not in seen:
                    all_ids.append(pid)
                    seen.add(pid)

            # 광고 ID 제외
            ad_ids = set(re.findall(r'data-nmb_rese-doc-id="(\d+)"', html))
            all_ids = [pid for pid in all_ids if pid not in ad_ids]

            for rank, pid in enumerate(all_ids[:max_rank], 1):
                if pid == target_place_id:
                    result.rank = rank
                    result.status = "found"
                    return result

            result.status = "not_found"

        except asyncio.TimeoutError:
            result.status = "error"
            result.error_message = "Timeout"
        except Exception as e:
            result.status = "error"
            result.error_message = str(e)

        return result

    def _find_place_in_apollo_improved(self, apollo_data: dict, target_id: str, max_rank: int) -> Optional[int]:
        """Apollo State에서 플레이스 ID 순위 찾기 (개선 버전)"""
        try:
            # 방법 1: PlaceListItem 키에서 순서대로 찾기
            place_items = []
            for key in apollo_data.keys():
                if key.startswith("PlaceListItem:") or key.startswith("Place:"):
                    item_id = key.split(":")[-1]
                    place_items.append(item_id)

            # ID가 있으면 순위 반환
            if target_id in place_items:
                rank = place_items.index(target_id) + 1
                if rank <= max_rank:
                    return rank

            # 방법 2: ROOT_QUERY에서 리스트 순서 확인
            root = apollo_data.get("ROOT_QUERY", {})
            for key, value in root.items():
                if "placeList" in key.lower() or "search" in key.lower():
                    if isinstance(value, list):
                        for idx, item in enumerate(value[:max_rank], 1):
                            if isinstance(item, dict):
                                ref = item.get("__ref", "")
                                if target_id in ref:
                                    return idx

            # 방법 3: 모든 값에서 items 배열 찾기
            for key, value in apollo_data.items():
                if isinstance(value, dict) and "items" in value:
                    items = value.get("items", [])
                    if isinstance(items, list):
                        for idx, item in enumerate(items[:max_rank], 1):
                            if isinstance(item, dict):
                                ref = item.get("__ref", "")
                                if target_id in ref:
                                    return idx

        except Exception:
            pass

        return None

    def _find_place_in_apollo(self, apollo_data: dict, target_id: str, max_rank: int) -> Optional[int]:
        """Apollo State에서 플레이스 ID 순위 찾기"""
        try:
            # PlaceListResult 또는 SearchResult에서 아이템 찾기
            for key, value in apollo_data.items():
                if not isinstance(value, dict):
                    continue

                # 리스트 아이템에서 ID 확인
                if key.startswith("PlaceListItem:") or key.startswith("Place:"):
                    item_id = key.split(":")[-1]
                    if item_id == target_id:
                        # 순위는 키 순서로 추정 (정확하지 않을 수 있음)
                        return None  # Apollo에서는 순위 추출이 복잡함

            # ROOT_QUERY에서 리스트 순서 확인
            root = apollo_data.get("ROOT_QUERY", {})
            for key, value in root.items():
                if "placeList" in key.lower() or "search" in key.lower():
                    if isinstance(value, list):
                        for idx, item in enumerate(value[:max_rank], 1):
                            if isinstance(item, dict):
                                ref = item.get("__ref", "")
                                if target_id in ref:
                                    return idx

        except Exception:
            pass

        return None

    def _detect_map_type_from_html(self, html: str) -> tuple:
        """
        HTML에서 지도 형태 감지 (4가지 형태 구분)

        우선순위: 리스트 감지 > 단일 감지 (검색 결과는 대부분 리스트)

        Returns:
            tuple: (map_type, is_single)
            - map_type: "신지도" | "구지도" | "알수없음"
            - is_single: True면 단일 업체 상세, False면 리스트
        """
        # === 1. 먼저 리스트 지도 감지 (우선순위 높음) ===
        # URL 패턴으로 리스트 판단 (가장 안정적)
        import re
        place_url_count = len(re.findall(r'place\.naver\.com/\w+/\d+', html))

        # 신지도 리스트 마커 (안정적인 마커 우선)
        new_list_markers = [
            "place_section_content",  # 플레이스 섹션 (안정적)
            "YYh8o",                  # 필터 영역
            "data-nmb_res-doc-id",    # 일반 결과 ID
        ]

        # 구지도 리스트 마커
        old_list_markers = [
            "place_bluelink",         # 구형 링크 (매우 안정적)
        ]

        has_new_list = any(marker in html for marker in new_list_markers)
        has_old_list = any(marker in html for marker in old_list_markers)

        # place URL이 2개 이상이면 리스트로 판단
        if place_url_count >= 2:
            if has_old_list:
                return ("구지도", False)
            elif has_new_list:
                return ("신지도", False)
            else:
                return ("신지도", False)  # URL이 있으면 일단 신지도 리스트로

        # 리스트 마커가 있으면 리스트
        if has_old_list:
            return ("구지도", False)
        if has_new_list:
            return ("신지도", False)

        # === 2. 단일 지도 감지 (리스트가 아닐 때만) ===
        # 단일 신지도: place.naver.com 상세 페이지 전용 마커
        single_new_markers = [
            "PlaceDetailBase",        # Apollo State 키 (상세 페이지 전용)
            '"__typename":"PlaceDetailBase"',  # GraphQL 타입
            "place_detail",           # 상세 페이지 클래스
        ]

        # 단일 구지도: 구형 상세 페이지 특징
        single_old_markers = [
            "biz_name_area",          # 구형 업체명 영역
            "detail_info",            # 구형 상세 정보
        ]

        is_single_new = any(marker in html for marker in single_new_markers)
        is_single_old = any(marker in html for marker in single_old_markers)

        if is_single_new:
            return ("신지도", True)
        if is_single_old:
            return ("구지도", True)

        # URL이 1개면 단일 페이지일 수 있음
        if place_url_count == 1:
            return ("신지도", True)

        return ("알수없음", False)

    def _has_list_markers(self, html: str) -> bool:
        """리스트 형태인지 확인 (단일 vs 리스트 구분용)"""
        import re
        # URL 패턴 개수로 판단 (가장 안정적)
        place_url_count = len(re.findall(r'place\.naver\.com/\w+/\d+', html))
        if place_url_count >= 2:
            return True

        list_markers = [
            "place_section_content",
            "place_bluelink",         # 구지도 리스트 마커 추가
            "VLTHu",
            "fvwqf",
            "_3XAXY",
            "api_more",
        ]
        count = sum(1 for marker in list_markers if marker in html)
        return count >= 1  # 1개 이상이면 리스트로 판단 (기준 완화)

    async def check_keywords(
        self,
        keywords: List[str],
        target_place_id: str,
        max_rank: int = 20
    ) -> List[RankResult]:
        """
        여러 키워드 순위 체크 (병렬 처리)

        Args:
            keywords: 체크할 키워드 리스트
            target_place_id: 찾을 플레이스 ID
            max_rank: 최대 확인 순위

        Returns:
            RankResult 리스트
        """
        self._stop_flag = False
        semaphore = asyncio.Semaphore(self.max_workers)
        completed = 0
        total = len(keywords)

        async def worker(keyword: str) -> RankResult:
            nonlocal completed

            if self._stop_flag:
                return RankResult(keyword=keyword, status="cancelled")

            async with semaphore:
                # 자연스러운 딜레이 (API 모드는 짧게)
                delay = random.uniform(0.2, 0.5) if self.use_api_mode else random.uniform(0.5, 1.0)
                await asyncio.sleep(delay)

                # 순위 체크
                if self.use_api_mode:
                    result = await self._check_single_keyword_api(
                        keyword, target_place_id, max_rank
                    )
                else:
                    result = await self._check_single_keyword_html(
                        keyword, target_place_id, max_rank
                    )

                completed += 1
                if self._progress_callback:
                    status_msg = f"{keyword}: {result.status}"
                    if result.rank:
                        status_msg = f"{keyword}: {result.rank}위 ({result.map_type})"
                    self._progress_callback(completed, total, status_msg)

                return result

        # 모든 키워드 병렬 처리
        tasks = [worker(kw) for kw in keywords]
        results = await asyncio.gather(*tasks)

        return list(results)


def estimate_time_api(keyword_count: int, proxy_count: int, max_rank: int) -> dict:
    """
    API 모드 예상 소요 시간 계산
    """
    # API 모드는 훨씬 빠름
    avg_time_per_keyword = 0.4  # 초
    workers = min(5, max(1, proxy_count + 1))

    total_seconds = (keyword_count * avg_time_per_keyword) / workers

    def format_time(seconds):
        if seconds < 60:
            return f"{int(seconds)}초"
        else:
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{mins}분 {secs}초"

    return {
        "min_seconds": total_seconds * 0.7,
        "max_seconds": total_seconds * 1.3,
        "formatted": f"{format_time(total_seconds * 0.7)} ~ {format_time(total_seconds * 1.3)}"
    }


# 간편 사용 함수
async def check_ranks_api(
    keywords: List[str],
    place_id: str,
    max_rank: int = 20,
    proxies: List[dict] = None,
    progress_callback: Callable = None
) -> List[RankResult]:
    """
    순위 체크 간편 함수 (API 버전)

    Args:
        keywords: 키워드 리스트
        place_id: 플레이스 ID
        max_rank: 최대 순위
        proxies: 프록시 리스트 [{"host": "...", "port": 8080}, ...]
        progress_callback: 진행 콜백 (current, total, message)

    Returns:
        RankResult 리스트
    """
    proxy_configs = []
    if proxies:
        for p in proxies:
            proxy_configs.append(ProxyConfig(
                host=p.get("host", ""),
                port=p.get("port", 8080),
                username=p.get("username", ""),
                password=p.get("password", ""),
                proxy_type=p.get("type", "datacenter")
            ))

    async with RankCheckerAPI(proxies=proxy_configs, use_api_mode=True) as checker:
        if progress_callback:
            checker.set_progress_callback(progress_callback)

        return await checker.check_keywords(keywords, place_id, max_rank)


# 테스트
if __name__ == "__main__":
    async def test():
        keywords = ["강남 피부과", "강남역 피부과", "신논현 피부과"]
        place_id = "12927872"  # 테스트용 피부과 ID

        def progress(current, total, msg):
            print(f"[{current}/{total}] {msg}")

        print("=== API 모드 테스트 ===")
        start = time.time()

        results = await check_ranks_api(
            keywords=keywords,
            place_id=place_id,
            max_rank=20,
            progress_callback=progress
        )

        elapsed = time.time() - start
        print(f"\n소요 시간: {elapsed:.2f}초")

        print("\n=== 결과 ===")
        for r in results:
            if r.rank:
                print(f"✅ {r.keyword}: {r.rank}위 ({r.map_type})")
            else:
                print(f"❌ {r.keyword}: 순위권 외 ({r.status})")

    asyncio.run(test())

"""
네이버 플레이스 순위 체크 엔진
- 프록시 풀 + 라운드 로빈
- 병렬 워커 (동시 처리)
- 조기 종료 (Early Exit)
- 예상 시간 계산
"""

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Callable
from playwright.async_api import async_playwright, Browser, Page


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


class ProxyPool:
    """프록시 풀 관리자 (라운드 로빈 + 쿨다운)"""
    
    def __init__(self, proxies: List[ProxyConfig], cooldown: float = 10.0):
        """
        Args:
            proxies: 프록시 설정 리스트
            cooldown: IP당 최소 재사용 대기 시간 (초)
        """
        self.proxies = proxies
        self.cooldown = cooldown
        self.usage: Dict[str, Dict] = {
            p.url: {"count": 0, "last_used": 0.0} 
            for p in proxies
        }
        self._lock = asyncio.Lock()
    
    async def get_proxy(self) -> Optional[ProxyConfig]:
        """사용 가능한 프록시 반환 (쿨다운 고려)"""
        async with self._lock:
            now = time.time()
            available = []
            
            for proxy in self.proxies:
                stats = self.usage[proxy.url]
                time_since_last = now - stats["last_used"]
                
                if time_since_last >= self.cooldown:
                    available.append((proxy, stats["count"]))
            
            if not available:
                # 모두 쿨다운 중이면 가장 오래된 것 선택
                oldest = min(
                    self.proxies, 
                    key=lambda p: self.usage[p.url]["last_used"]
                )
                wait_time = self.cooldown - (now - self.usage[oldest.url]["last_used"])
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                return oldest
            
            # 사용 횟수 가장 적은 것 선택 (균등 분배)
            selected = min(available, key=lambda x: x[1])[0]
            return selected
    
    def mark_used(self, proxy: ProxyConfig):
        """프록시 사용 완료 표시"""
        self.usage[proxy.url]["count"] += 1
        self.usage[proxy.url]["last_used"] = time.time()


def get_human_delay() -> float:
    """사람처럼 불규칙한 딜레이 생성"""
    base = random.uniform(1.5, 3.0)
    
    # 가끔 더 오래 멈춤 (뭔가 보는 척) - 10% 확률
    if random.random() < 0.1:
        base += random.uniform(2.0, 5.0)
    
    # 아주 가끔 짧은 멈춤 (빠르게 스킵하는 척) - 5% 확률
    if random.random() < 0.05:
        base = random.uniform(0.5, 1.0)
    
    return base


def estimate_time(keyword_count: int, proxy_count: int, max_rank: int) -> dict:
    """
    예상 소요 시간 계산
    
    Args:
        keyword_count: 체크할 키워드 수
        proxy_count: 프록시 수
        max_rank: 최대 순위 (조기 종료용)
    
    Returns:
        dict: {min_seconds, max_seconds, formatted}
    """
    # 기본 가정
    avg_delay = 2.5  # 평균 딜레이 (초)
    page_load_time = 2.0  # 페이지 로드 시간 (초)
    rank_check_time = 0.3 * min(max_rank, 10)  # 순위 확인 시간
    
    # 동시 워커 수 (프록시 수의 절반, 최대 5개)
    workers = min(max(1, proxy_count // 2 + 1), 5)
    
    # 키워드당 예상 시간
    time_per_keyword = avg_delay + page_load_time + rank_check_time
    
    # 조기 종료로 인한 시간 절감 (약 30%)
    early_exit_factor = 0.7
    
    # 병렬 처리로 인한 시간 절감
    parallel_factor = 1 / workers
    
    # 총 예상 시간
    total_min = keyword_count * time_per_keyword * early_exit_factor * parallel_factor * 0.8
    total_max = keyword_count * time_per_keyword * parallel_factor * 1.2
    
    # 포맷팅
    def format_time(seconds):
        if seconds < 60:
            return f"{int(seconds)}초"
        elif seconds < 3600:
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{mins}분 {secs}초"
        else:
            hours = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            return f"{hours}시간 {mins}분"
    
    return {
        "min_seconds": total_min,
        "max_seconds": total_max,
        "formatted": f"{format_time(total_min)} ~ {format_time(total_max)}"
    }


class RankChecker:
    """네이버 플레이스 순위 체크 엔진"""
    
    # 모바일 User-Agent 목록
    USER_AGENTS = [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15",
        "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36",
        "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36",
    ]
    
    def __init__(
        self, 
        proxies: List[ProxyConfig] = None,
        headless: bool = True,
        max_workers: int = 3
    ):
        """
        Args:
            proxies: 프록시 설정 리스트 (None이면 직접 연결)
            headless: 브라우저 숨김 여부
            max_workers: 최대 동시 워커 수
        """
        self.proxies = proxies or []
        self.headless = headless
        self.max_workers = max_workers
        
        self.proxy_pool = ProxyPool(self.proxies) if self.proxies else None
        self._playwright = None
        self._browser = None
        self._progress_callback: Optional[Callable] = None
    
    def set_progress_callback(self, callback: Callable[[int, int, str], None]):
        """진행 상황 콜백 설정 (current, total, message)"""
        self._progress_callback = callback
    
    async def __aenter__(self):
        await self._init_browser()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._close_browser()
    
    async def _init_browser(self):
        """브라우저 초기화"""
        self._playwright = await async_playwright().start()
        
        launch_options = {
            "headless": self.headless,
        }
        
        self._browser = await self._playwright.chromium.launch(**launch_options)
    
    async def _close_browser(self):
        """브라우저 종료"""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
    
    async def _check_single_keyword(
        self, 
        keyword: str, 
        target_place_id: str, 
        max_rank: int
    ) -> RankResult:
        """
        단일 키워드 순위 체크 (통합검색 -> 더보기 -> 심층 탐색)
        """
        result = RankResult(keyword=keyword)
        
        # 프록시 선택 및 페이지 생성
        proxy = None
        if self.proxy_pool:
            proxy = await self.proxy_pool.get_proxy()
        
        context_options = {
            "user_agent": random.choice(self.USER_AGENTS),
            "viewport": {"width": 390, "height": 844},
            "locale": "ko-KR",
        }
        if proxy:
            context_options["proxy"] = {"server": proxy.url}
        
        context = await self._browser.new_context(**context_options)
        page = await context.new_page()
        
        try:
            # 1. 통합검색 확인
            search_url = f"https://m.search.naver.com/search.naver?query={keyword}"
            await page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(1.0)
            
            # 지도 형태 감지
            result.map_type = await self._detect_map_type(page)
            
            # 통합검색 상위 노출 확인
            found_rank = await self._scan_integrated_ranks(page, target_place_id)
            if found_rank:
                result.rank = found_rank
                result.status = "found"
                return result
            
            # 2. 미노출 시 '플레이스 리스트' 직접 진입 (최대 순위 탐색)
            if max_rank > 6:
                # '더보기' 버튼 클릭 대신, 직접 URL로 이동하여 조회 (훨씬 정확함)
                # 예: https://m.place.naver.com/place/list?query=키워드&x=...
                # 좌표(x,y)는 없어도 검색됨. 정확도를 위해 query만 사용.
                
                # 키워드 인코딩은 Playwright가 알아서 처리하거나 f-string으로 주입
                place_list_url = f"https://m.place.naver.com/place/list?query={keyword}&display=100"
                await page.goto(place_list_url, wait_until="networkidle", timeout=15000)
                await asyncio.sleep(1.0)
                
                # 플레이스 리스트에서 심층 탐색
                deep_rank = await self._scan_place_list_ranks(page, target_place_id, max_rank)
                if deep_rank:
                    result.rank = deep_rank # 플레이스 리스트 내 순위
                    result.status = "found"
                else:
                    result.status = "not_found"
            else:
                result.status = "not_found"
            
        except Exception as e:
            result.status = "error"
            result.error_message = str(e)
            # print(f"[DEBUG] 순위 체크 에러 ({keyword}): {e}")
            
        finally:
            await page.close()
            await context.close()
            if proxy and self.proxy_pool:
                self.proxy_pool.mark_used(proxy)
        
        return result

    async def _scan_integrated_ranks(self, page: Page, target_id: str) -> Optional[int]:
        """통합검색 화면에서 순위 확인 (1~6위)"""
        for rank in range(1, 7):
            pid = await self._get_place_id_at_rank(page, rank)
            if pid == target_id:
                return rank
            if pid is None:
                break
        return None

    async def _click_more_button(self, page: Page) -> bool:
        """플레이스 '더보기' 또는 '지도' 버튼 클릭"""
        try:
            # 다양한 '더보기' 셀렉터 시도 (텍스트 포함)
            selectors = [
                ".api_more_bundle_group",  # 일반적인 더보기
                "a.api_more", 
                ".more_btn",
                ".place_section_content .more",
                "xpath=//a[contains(text(), '더보기')]",
                "xpath=//a[contains(text(), '플레이스 더보기')]",
                "xpath=//span[contains(text(), '더보기')]/.."
            ]
            
            print("[DEBUG] Attempting to click 'More' button...")
            for sel in selectors:
                try:
                    btn = await page.query_selector(sel)
                    if btn and await btn.is_visible():
                        await btn.click()
                        print(f"[DEBUG] Clicked 'More' button using selector: {sel}")
                        await page.wait_for_load_state("networkidle", timeout=5000)
                        await asyncio.sleep(1.5)
                        return True
                except:
                    continue
            print("[DEBUG] Failed to find or click 'More' button.")
            return False
        except:
            print("[DEBUG] _click_more_button exception.")
            return False

    async def _scan_place_list_ranks(self, page: Page, target_id: str, max_rank: int) -> Optional[int]:
        """플레이스 리스트(무한 스크롤)에서 순위 확인"""
        
        current_count = 0
        scroll_attempts = 0
        
        last_height = await page.evaluate("document.body.scrollHeight")
        
        while current_count < max_rank:
            # 현재 로드된 리스트에서 ID 찾기
            # 정규식 이스케이프: Python f-string 내에서 \ -> \\ -> JS에서 \
            found_idx = await page.evaluate(f"""(targetId) => {{
                // m.place.naver.com 리스트 아이템: li.VLTHu (또는 일반 li)
                const items = document.querySelectorAll('li.VLTHu, ul > li');
                
                let validCount = 0;
                
                for (let i = 0; i < items.length; i++) {{
                    const li = items[i];
                    // 링크 찾기
                    const link = li.querySelector('a[href*="/place/"], a[href*="/restaurant/"], a[href*="/hospital/"], a[href*="/hairshop/"]');
                    
                    if (!link) continue;
                    
                    validCount++;
                    
                    // ID 추출 (href에서)
                    // 예: .../restaurant/12345678?...
                    const href = link.href;
                    let id = null;
                    const match = href.match(/\\/(place|restaurant|hospital|hairshop)\\/(\\d+)/);
                    if (match) {{
                        id = match[2];
                    }}
                    
                    if (id === targetId) return validCount;
                }}
                return -1;
            }}""", target_id)
            
            if found_idx > 0:
                return found_idx
            
            # 못 찾았으면 스크롤 다운
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1.2)
            
            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                scroll_attempts += 1
                if scroll_attempts > 2: # 더 이상 로드 안 됨
                    break
            else:
                scroll_attempts = 0
            last_height = new_height
            
            # 현재 아이템 개수 업데이트
            current_count = await page.evaluate("""() => {
                return document.querySelectorAll('li.VLTHu, ul > li a[href*="/place/"]').length;
            }""")
            
        return None
    
    async def _detect_map_type(self, page: Page) -> str:
        """
        지도 형태 감지 (브라우저 분석 결과 반영)
        
        1. 신지도 (리스트형): .YYh8o (필터) OR .vEZDX (리스트 저장버튼)
        2. 신지도 (단일 정보형): .D_Xqt (헤더 저장버튼)
        3. 구지도: 위 요소들이 없고 단순 링크(.place_bluelink, .C6RjW)만 존재
        """
        try:
            result = await page.evaluate("""() => {
                // 1. 신지도 리스트형 체크
                const hasFilters = document.querySelector('.YYh8o') !== null;
                const hasListSaveBtn = document.querySelector('.vEZDX') !== null;
                const hasNewDataAttr = document.querySelector('li[data-nmb_res-doc-id]') !== null;
                
                if (hasFilters || hasListSaveBtn || hasNewDataAttr) {
                    return '신지도';
                }
                
                // 2. 신지도 단일 정보형 체크 (헤더 저장 버튼)
                const hasHeaderSaveBtn = document.querySelector('.D_Xqt') !== null;
                if (hasHeaderSaveBtn) {
                    return '신지도';
                }
                
                // 3. 구지도 체크 (단순 링크만 존재)
                const hasPlaceLink = document.querySelector('.place_bluelink, .C6RjW') !== null;
                const hasOldList = document.querySelector('li.VLTHu, .place_section li, ._T0lO') !== null;
                
                if (hasPlaceLink || hasOldList) {
                    return '구지도';
                }
                
                return '알수없음';
            }""")
            
            return result
        except:
            return "알수없음"
    
    async def _get_place_id_at_rank(self, page: Page, rank: int) -> Optional[str]:
        """
        특정 순위의 플레이스 ID 추출 (광고 제외, 일반 결과만)
        
        네이버 모바일 검색 결과 DOM 구조:
        - 리스트 아이템: li.UEzoS (구형) -> data 속성으로 대체
        - 일반 결과: data-nmb_res-doc-id 속성
        - 광고 결과: data-nmb_rese-doc-id 속성
        """
        try:
            # JavaScript로 광고 제외한 일반 결과만 필터링하여 n번째 ID 반환
            script = """
            (rank) => {
                // 광고가 아닌 일반 플레이스 리스트 아이템 선택
                // 1. data-nmb_res-doc-id 속성이 있는 요소 (가장 확실)
                // 2. data-id 속성이 있는 li 요소 (차선)
                const items = Array.from(document.querySelectorAll('li[data-nmb_res-doc-id], li[data-id]'));
                
                // 광고 제외 필터링
                const organic = items.filter(item => {
                    // 네이버 광고는 보통 data-nmb_rese-doc-id 같은 별도 속성을 가짐
                    // 혹은 클래스에 'ad'나 '_ad'가 포함됨
                    const isAd = item.hasAttribute('data-nmb_rese-doc-id') || 
                                 item.classList.contains('type_ad');
                                 
                    // data-nmb_res-doc-id(일반) 만 있고, 광고 속성이 없는 것
                    const hasOrganicId = item.hasAttribute('data-nmb_res-doc-id') || item.hasAttribute('data-id');
                    
                    return hasOrganicId && !isAd;
                });
                
                // rank는 1부터 시작
                const target = organic[rank - 1];
                
                if (!target) return null;
                
                // ID 추출
                return target.getAttribute('data-nmb_res-doc-id') || target.getAttribute('data-id');
            }
            """
            result = await page.evaluate(script, rank)
            return result
        except Exception as e:
            print(f"[DEBUG] _get_place_id_at_rank 오류: {e}")
            return None
    
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
        results = []
        semaphore = asyncio.Semaphore(self.max_workers)
        completed = 0
        total = len(keywords)
        
        async def worker(keyword: str) -> RankResult:
            nonlocal completed
            async with semaphore:
                # 자연스러운 딜레이
                await asyncio.sleep(get_human_delay())
                
                result = await self._check_single_keyword(
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


# 간편 사용 함수
async def check_ranks(
    keywords: List[str],
    place_id: str,
    max_rank: int = 20,
    proxies: List[dict] = None,
    progress_callback: Callable = None
) -> List[RankResult]:
    """
    순위 체크 간편 함수
    
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
    
    async with RankChecker(proxies=proxy_configs) as checker:
        if progress_callback:
            checker.set_progress_callback(progress_callback)
        
        return await checker.check_keywords(keywords, place_id, max_rank)


# 테스트
if __name__ == "__main__":
    import sys
    
    async def test():
        keywords = ["강남 피부과", "강남역 피부과", "신논현 피부과"]
        place_id = "12927872"  # 테스트용 피부과 ID
        
        def progress(current, total, msg):
            print(f"[{current}/{total}] {msg}")
        
        results = await check_ranks(
            keywords=keywords,
            place_id=place_id,
            max_rank=20,
            progress_callback=progress
        )
        
        print("\n=== 결과 ===")
        for r in results:
            if r.rank:
                print(f"✅ {r.keyword}: {r.rank}위 ({r.map_type})")
            else:
                print(f"❌ {r.keyword}: 순위권 외")
    
    asyncio.run(test())

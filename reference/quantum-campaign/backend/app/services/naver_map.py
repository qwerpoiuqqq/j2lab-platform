"""네이버 플레이스 스크래핑 모듈."""

import random
import re
from dataclasses import dataclass
from typing import List, Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page


@dataclass
class PlaceInfo:
    """플레이스 기본 정보 (이름 + 주소)."""

    name: Optional[str] = None
    address: Optional[str] = None

    @property
    def area(self) -> str:
        """주소에서 시/구 레벨 영역 추출.

        예: '부산 수영구 민락동 109' → '부산 수영구'
        """
        if not self.address:
            return ""
        parts = self.address.split()
        if len(parts) >= 2:
            return f"{parts[0]} {parts[1]}"
        return parts[0] if parts else ""


@dataclass
class LandmarkInfo:
    """주변 명소 정보."""

    name: str
    url: Optional[str] = None
    place_id: Optional[str] = None
    distance_m: Optional[int] = None  # 이 장소에서의 거리 (미터)
    index: int = 0  # 명소 목록 내 순번 (1-based)


class NaverMapScraperError(Exception):
    """네이버맵 스크래퍼 관련 에러."""

    pass


class StealthConfig:
    """스텔스 설정."""

    # 모바일 User-Agent 풀
    USER_AGENTS = [
        # iPhone
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 15_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.7 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.3 Mobile/15E148 Safari/604.1",
        # Android
        "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; SM-A546B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Mobile Safari/537.36",
    ]

    # 모바일 뷰포트 풀
    VIEWPORTS = [
        {"width": 375, "height": 812},   # iPhone X/XS/11 Pro
        {"width": 390, "height": 844},   # iPhone 12/13/14
        {"width": 393, "height": 852},   # iPhone 14 Pro
        {"width": 360, "height": 800},   # Android common
        {"width": 412, "height": 915},   # Pixel 7
        {"width": 384, "height": 854},   # Android common
    ]

    # 딜레이 설정 (밀리초)
    MIN_DELAY = 2000
    MAX_DELAY = 5000

    # WebDriver 숨김 스크립트
    STEALTH_SCRIPTS = """
    // WebDriver 속성 숨기기
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    });

    // Chrome 런타임 에뮬레이션
    window.chrome = {
        runtime: {},
        loadTimes: function() {},
        csi: function() {},
        app: {}
    };

    // Permissions API 스푸핑
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
    );

    // Plugins 배열 스푸핑 (모바일은 빈 배열)
    Object.defineProperty(navigator, 'plugins', {
        get: () => []
    });

    // Languages 스푸핑
    Object.defineProperty(navigator, 'languages', {
        get: () => ['ko-KR', 'ko', 'en-US', 'en']
    });

    // Platform 스푸핑 (User-Agent에 맞게)
    // 이 부분은 context 생성 시 설정됨

    // Connection 스푸핑
    Object.defineProperty(navigator, 'connection', {
        get: () => ({
            effectiveType: '4g',
            rtt: 50,
            downlink: 10,
            saveData: false
        })
    });

    // 자동화 탐지 우회
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
    """

    @classmethod
    def get_random_user_agent(cls) -> str:
        """랜덤 User-Agent 반환."""
        return random.choice(cls.USER_AGENTS)

    @classmethod
    def get_random_viewport(cls) -> dict:
        """랜덤 뷰포트 반환."""
        return random.choice(cls.VIEWPORTS)

    @classmethod
    def get_random_delay(cls) -> int:
        """랜덤 딜레이 반환 (밀리초)."""
        return random.randint(cls.MIN_DELAY, cls.MAX_DELAY)


class NaverMapScraper:
    """네이버 플레이스 스크래퍼 (스텔스 모드 지원)."""

    # 셀렉터 상수
    SELECTORS = {
        # 탭 메뉴
        "nearby_tab": 'a[role="tab"]:has-text("주변")',
        "nearby_tab_by_href": 'a[href*="/around"]',
        # 명소 카테고리 탭 (주변 탭 내부)
        "landmark_tab": 'span.Me4yK:has-text("명소"), a.T00ux:has-text("명소")',
        # 주변 장소 목록
        "list_container": "ul.eDFz9",
        "list_item": "li.S0Ns3",
        "place_name": "span.xBZDS",
        "place_link": "a.place_bluelink, a.OiGhS",
        # 길찾기 페이지 셀렉터
        "directions_start_input": ".search_input_box_wrap.start input.input_search",
        "directions_goal_input": ".search_input_box_wrap.goal input.input_search",
        "directions_autocomplete_item": "li.item_place div.link_place",
        "directions_search_btn": "button.btn_direction.search",
        # 걸음수: walk_direction_info 중 "걸음" 단위가 있는 것
        "directions_steps_container": ".walk_direction_info:has(.walk_direction_unit)",
        "directions_steps_value": ".walk_direction_value",
        "directions_steps_unit": ".walk_direction_unit",
    }

    # 광고 URL 패턴 (필터링 대상)
    AD_URL_PATTERNS = ["ader.naver.com", "ad.naver.com", "naver.me/ad"]

    # 길찾기 페이지 URL
    DIRECTIONS_URL = "https://map.naver.com/p/directions/-/-/-/walk?c=15.00,0,0,0,dh"

    # 데스크톱 설정 (길찾기 페이지용)
    DESKTOP_VIEWPORT = {"width": 1280, "height": 900}
    DESKTOP_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    )

    def __init__(self, headless: bool = True, stealth: bool = True):
        """
        Args:
            headless: 헤드리스 모드 여부
            stealth: 스텔스 모드 활성화 여부
        """
        self.headless = headless
        self.stealth = stealth
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._playwright = None
        self._user_agent: Optional[str] = None
        self._viewport: Optional[dict] = None

    async def init_browser(self) -> None:
        """Playwright 브라우저 초기화 (스텔스 설정 포함)."""
        if self._browser is not None:
            return

        self._playwright = await async_playwright().start()

        # 스텔스 모드 설정
        if self.stealth:
            self._user_agent = StealthConfig.get_random_user_agent()
            self._viewport = StealthConfig.get_random_viewport()
        else:
            self._user_agent = StealthConfig.USER_AGENTS[0]
            self._viewport = StealthConfig.VIEWPORTS[0]

        # 브라우저 실행 옵션
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ]

        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=launch_args,
        )

        # 컨텍스트 생성 (스텔스 설정 적용)
        self._context = await self._browser.new_context(
            viewport=self._viewport,
            user_agent=self._user_agent,
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            geolocation={"latitude": 37.5665, "longitude": 126.9780},  # 서울
            permissions=["geolocation"],
            color_scheme="light",
            device_scale_factor=random.choice([2, 3]),  # 모바일 레티나
        )

        # 스텔스 스크립트 주입
        if self.stealth:
            await self._context.add_init_script(StealthConfig.STEALTH_SCRIPTS)

    async def close(self) -> None:
        """브라우저 리소스 정리."""
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입."""
        await self.init_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료."""
        await self.close()

    async def _random_delay(self) -> None:
        """랜덤 딜레이 적용."""
        if self.stealth and self._context:
            page = self._context.pages[0] if self._context.pages else None
            if page:
                delay = StealthConfig.get_random_delay()
                await page.wait_for_timeout(delay)

    async def _human_like_delay(self, page: Page) -> None:
        """인간처럼 보이는 딜레이."""
        if self.stealth:
            delay = StealthConfig.get_random_delay()
            await page.wait_for_timeout(delay)

    def _extract_place_id_from_url(self, url: str) -> Optional[str]:
        """
        플레이스 URL에서 place_id 추출.

        Args:
            url: 플레이스 URL

        Returns:
            place_id 또는 None
        """
        # m.place.naver.com/place/123456 패턴
        match = re.search(r"/place/(\d+)", url)
        if match:
            return match.group(1)

        # m.place.naver.com/restaurant/123456 패턴
        match = re.search(r"/(restaurant|cafe|place)/(\d+)", url)
        if match:
            return match.group(2)

        return None

    # 주변 카테고리 필터 코드
    AROUND_FILTER_LANDMARK = 100  # 명소

    def _build_around_url(self, place_url: str, filter_code: int = 100) -> str:
        """
        플레이스 URL을 주변 탭 URL로 변환.

        Args:
            place_url: 원본 플레이스 URL
            filter_code: 카테고리 필터 코드 (기본 100=명소)

        Returns:
            주변 탭 URL (예: .../around?filter=100)
        """
        # URL 끝의 슬래시 정리
        base_url = place_url.rstrip("/")

        # 기존 /around 이하 경로 및 쿼리 제거
        if "/around" in base_url:
            base_url = base_url.split("/around")[0]

        # /home, /feed 등 다른 탭 경로 제거
        tab_patterns = [
            "/home",
            "/feed",
            "/menu",
            "/booking",
            "/review",
            "/photo",
            "/location",
            "/information",
        ]
        for pattern in tab_patterns:
            if base_url.endswith(pattern):
                base_url = base_url[: -len(pattern)]
                break

        return f"{base_url}/around?filter={filter_code}"

    def _is_ad_url(self, url: str) -> bool:
        """광고 URL인지 확인."""
        if not url:
            return False
        for pattern in self.AD_URL_PATTERNS:
            if pattern in url:
                return True
        return False

    async def _click_landmark_tab(self, page: Page) -> bool:
        """명소 탭 클릭."""
        selectors = [s.strip() for s in self.SELECTORS["landmark_tab"].split(",")]
        for sel in selectors:
            try:
                element = await page.query_selector(sel)
                if element and await element.is_visible():
                    await element.click()
                    await page.wait_for_timeout(2000)
                    return True
            except Exception:
                continue
        return False

    async def get_nearby_landmarks(
        self, place_url: str, max_count: int = 10
    ) -> List[LandmarkInfo]:
        """
        플레이스 URL에서 주변 명소 목록 추출.

        Args:
            place_url: 네이버 플레이스 URL
            max_count: 최대 추출 개수

        Returns:
            주변 명소 목록

        Raises:
            NaverMapScraperError: 스크래핑 실패 시
        """
        await self.init_browser()

        if not self._context:
            raise NaverMapScraperError("브라우저가 초기화되지 않았습니다")

        page: Page = await self._context.new_page()
        landmarks: List[LandmarkInfo] = []

        try:
            # 주변 > 명소 탭으로 직접 접속 (?filter=100)
            around_url = self._build_around_url(place_url)
            await page.goto(around_url, wait_until="domcontentloaded", timeout=60000)

            # 스텔스: 인간처럼 보이는 딜레이
            await self._human_like_delay(page)

            # 리스트 컨테이너 대기
            try:
                await page.wait_for_selector(
                    self.SELECTORS["list_item"], timeout=10000
                )
            except Exception:
                raise NaverMapScraperError(
                    f"명소 목록을 찾을 수 없습니다: {place_url}"
                )

            # 명소 목록 추출
            items = await page.query_selector_all(self.SELECTORS["list_item"])
            landmark_order = 0  # 광고 제외 순번 카운터

            for item in items:
                if len(landmarks) >= max_count:
                    break

                # 장소 이름 추출
                name_element = await item.query_selector(self.SELECTORS["place_name"])
                if not name_element:
                    continue

                name = await name_element.inner_text()
                name = name.strip()

                if not name:
                    continue

                # 링크 및 place_id 추출
                link_element = await item.query_selector(self.SELECTORS["place_link"])
                url = None
                place_id = None

                if link_element:
                    href = await link_element.get_attribute("href")
                    if href:
                        # 광고 링크 필터링
                        if self._is_ad_url(href):
                            continue
                        # 실제 장소 URL만 추출
                        if "m.place.naver.com" in href:
                            url = href
                            place_id = self._extract_place_id_from_url(href)

                # 거리 추출: "이 장소에서 XXm" 또는 "이 장소에서 X.Xkm"
                distance_m = None
                try:
                    item_text = await item.inner_text()
                    dist_match = re.search(
                        r"이 장소에서\s+([\d,.]+)\s*(m|km)", item_text
                    )
                    if dist_match:
                        dist_val = float(dist_match.group(1).replace(",", ""))
                        dist_unit = dist_match.group(2)
                        if dist_unit == "km":
                            distance_m = int(dist_val * 1000)
                        else:
                            distance_m = int(dist_val)
                except Exception:
                    pass

                landmark_order += 1
                landmarks.append(LandmarkInfo(
                    name=name, url=url, place_id=place_id,
                    distance_m=distance_m, index=landmark_order,
                ))

        except NaverMapScraperError:
            raise
        except Exception as e:
            raise NaverMapScraperError(f"스크래핑 중 오류 발생: {str(e)}")
        finally:
            await page.close()

        return landmarks

    async def get_top_landmarks(
        self, place_url: str, count: int = 3
    ) -> List[LandmarkInfo]:
        """
        상위 N개 명소만 추출.

        Args:
            place_url: 네이버 플레이스 URL
            count: 추출할 명소 개수 (기본 3개)

        Returns:
            상위 명소 목록
        """
        landmarks = await self.get_nearby_landmarks(place_url, max_count=count)
        return landmarks[:count]

    async def select_first_landmark(
        self, place_url: str
    ) -> Optional[LandmarkInfo]:
        """
        주변 명소 중 광고 제외 첫 번째 명소 선택.

        주변 → 명소 탭에서 광고를 제외한 1번째 지역을 출발지로 반환합니다.

        Args:
            place_url: 네이버 플레이스 URL

        Returns:
            선택된 명소 정보, 없으면 None
        """
        landmarks = await self.get_nearby_landmarks(place_url, max_count=1)

        if not landmarks:
            return None

        return landmarks[0]

    async def select_landmark_by_min_distance(
        self, place_url: str, min_distance_m: int = 100,
        random_pick: bool = False, max_candidates: int = 5,
    ) -> Optional[LandmarkInfo]:
        """거리 기준으로 명소 선택.

        주변 → 명소 탭에서 '이 장소에서 OOm' 거리가
        min_distance_m 이상인 명소를 반환합니다.

        Args:
            place_url: 네이버 플레이스 URL
            min_distance_m: 최소 거리 (미터, 기본 100m)
            random_pick: True면 조건 만족 명소 중 랜덤 선택 (최대 max_candidates개)
            max_candidates: 랜덤 선택 시 후보 최대 개수

        Returns:
            조건을 만족하는 명소 정보 (index 포함), 없으면 None
        """
        landmarks = await self.get_nearby_landmarks(place_url, max_count=20)

        candidates = [
            lm for lm in landmarks
            if lm.distance_m is not None and lm.distance_m >= min_distance_m
        ]

        if candidates:
            if random_pick:
                pool = candidates[:max_candidates]
                return random.choice(pool)
            return candidates[0]

        # 거리 조건을 만족하는 명소가 없으면 첫 번째 명소 반환 (폴백)
        return landmarks[0] if landmarks else None

    async def select_first_landmark_name(
        self, place_url: str
    ) -> Optional[str]:
        """
        주변 명소 중 광고 제외 첫 번째 명소 이름만 반환.

        Args:
            place_url: 네이버 플레이스 URL

        Returns:
            선택된 명소 이름, 없으면 None
        """
        landmark = await self.select_first_landmark(place_url)
        return landmark.name if landmark else None

    async def get_real_place_name(self, place_url: str) -> Optional[str]:
        """
        플레이스 URL에 접속하여 실제 상호명을 추출.

        네이버 플레이스 페이지의 og:title 또는 페이지 타이틀에서
        실제 등록된 상호명을 가져옵니다.

        Args:
            place_url: 네이버 플레이스 URL

        Returns:
            실제 상호명, 추출 실패 시 None
        """
        await self.init_browser()

        if not self._context:
            return None

        page: Page = await self._context.new_page()

        try:
            # /home, /around 등 서브 경로 제거 → 메인 플레이스 페이지 접속
            base_url = place_url.rstrip("/")
            tab_patterns = [
                "/home", "/feed", "/menu", "/booking", "/review",
                "/photo", "/location", "/information", "/around",
            ]
            for pattern in tab_patterns:
                if base_url.endswith(pattern):
                    base_url = base_url[: -len(pattern)]
                    break

            await page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)

            # 1순위: og:title meta 태그
            og_title = await page.evaluate(
                """() => {
                    const meta = document.querySelector('meta[property="og:title"]');
                    return meta ? meta.getAttribute('content') : null;
                }"""
            )
            if og_title:
                # "상호명 : 네이버" 형태에서 상호명만 추출
                name = og_title.split(" : ")[0].strip()
                if name:
                    return name

            # 2순위: 페이지 title
            title = await page.title()
            if title:
                name = title.split(" : ")[0].strip()
                if name and name != "네이버":
                    return name

            # 3순위: 플레이스 이름 셀렉터
            name_selectors = [
                "span.GHAhO",  # 모바일 플레이스 상호명
                "span.Fc1rA",  # 대체 셀렉터
                "#_title span",
                "span.place_section_header_title",
            ]
            for sel in name_selectors:
                try:
                    el = await page.query_selector(sel)
                    if el:
                        text = await el.inner_text()
                        text = text.strip()
                        if text:
                            return text
                except Exception:
                    continue

            return None

        except Exception as e:
            # 추출 실패 시 None 반환 (치명적 오류 아님)
            return None
        finally:
            await page.close()

    async def get_place_info(self, place_url: str) -> PlaceInfo:
        """플레이스 URL에서 상호명과 주소를 한번에 추출.

        Args:
            place_url: 네이버 플레이스 URL

        Returns:
            PlaceInfo (name, address)
        """
        await self.init_browser()

        if not self._context:
            return PlaceInfo()

        page: Page = await self._context.new_page()
        info = PlaceInfo()

        try:
            # 서브 경로 제거 → 메인 플레이스 페이지 접속
            base_url = place_url.rstrip("/")
            tab_patterns = [
                "/home", "/feed", "/menu", "/booking", "/review",
                "/photo", "/location", "/information", "/around",
            ]
            for pattern in tab_patterns:
                if base_url.endswith(pattern):
                    base_url = base_url[: -len(pattern)]
                    break

            await page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)

            # 이름 추출: og:title
            og_title = await page.evaluate(
                """() => {
                    const meta = document.querySelector('meta[property="og:title"]');
                    return meta ? meta.getAttribute('content') : null;
                }"""
            )
            if og_title:
                name = og_title.split(" : ")[0].strip()
                if name:
                    info.name = name

            # 이름 폴백: page title
            if not info.name:
                title = await page.title()
                if title:
                    name = title.split(" : ")[0].strip()
                    if name and name != "네이버":
                        info.name = name

            # 주소 추출
            address = await page.evaluate(
                """() => {
                    // 주소 셀렉터 우선순위
                    const selectors = ['.PkgBl', '.LDgIH', 'span.LDgIH'];
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el) {
                            const text = el.textContent.trim();
                            if (text) return text;
                        }
                    }
                    return null;
                }"""
            )
            if address:
                # "도로명" / "지번" 접두어 제거
                for prefix in ["도로명", "지번"]:
                    if address.startswith(prefix):
                        address = address[len(prefix):].strip()
                info.address = address

            return info

        except Exception:
            return info
        finally:
            await page.close()

    def get_current_fingerprint(self) -> dict:
        """현재 브라우저 fingerprint 정보 반환 (디버깅용)."""
        return {
            "user_agent": self._user_agent,
            "viewport": self._viewport,
            "stealth_enabled": self.stealth,
        }

    @staticmethod
    def parse_steps(steps_text: str) -> int:
        """
        걸음수 텍스트를 정수로 변환.

        Args:
            steps_text: 걸음수 텍스트 (예: "1,234 걸음", "789걸음", "1234")

        Returns:
            걸음수 정수값

        Raises:
            ValueError: 파싱 실패 시
        """
        if not steps_text:
            raise ValueError("빈 걸음수 텍스트입니다")

        # 숫자와 콤마만 추출
        cleaned = re.sub(r"[^\d,]", "", steps_text)

        # 콤마 제거
        cleaned = cleaned.replace(",", "")

        if not cleaned:
            raise ValueError(f"걸음수를 파싱할 수 없습니다: {steps_text}")

        return int(cleaned)

    async def _click_autocomplete_with_area(
        self,
        page: Page,
        search_term: str,
        area_hint: Optional[str] = None,
    ) -> bool:
        """자동완성 결과 중 주소가 일치하는 항목을 클릭.

        area_hint가 없으면 첫 번째 결과를 클릭합니다.
        area_hint가 있으면 해당 지역이 포함된 결과를 우선 클릭합니다.

        Args:
            page: Playwright 페이지
            search_term: 검색어
            area_hint: 지역 힌트 (예: "부산 수영구")

        Returns:
            클릭 성공 여부
        """
        try:
            # 자동완성 결과 대기
            first_item = page.locator(
                self.SELECTORS["directions_autocomplete_item"]
            ).first
            await first_item.wait_for(state="visible", timeout=5000)
        except Exception:
            return False

        if not area_hint:
            # area_hint 없으면 첫 번째 결과 클릭
            await first_item.click()
            return True

        # 자동완성 항목들에서 주소 매칭 검색
        items = await page.query_selector_all("li.item_place")
        for item in items:
            text = await item.inner_text()
            if area_hint in text:
                # 클릭 가능한 링크 요소 찾기
                link = await item.query_selector("div.link_place")
                if link:
                    await link.click()
                    return True

        # area_hint와 일치하는 항목이 없으면 첫 번째 결과 클릭 (폴백)
        await first_item.click()
        return True

    async def get_walking_steps(
        self,
        start_landmark: str,
        destination_place: str,
        area_hint: Optional[str] = None,
    ) -> int:
        """
        출발지에서 도착지까지의 도보 걸음수 계산.

        Args:
            start_landmark: 출발지 (명소 이름)
            destination_place: 도착지 (플레이스 이름)
            area_hint: 지역 힌트 (예: "부산 수영구") - 자동완성 결과 주소 검증용

        Returns:
            걸음수 (정수)

        Raises:
            NaverMapScraperError: 경로 검색 실패 시
        """
        await self.init_browser()

        if not self._browser:
            raise NaverMapScraperError("브라우저가 초기화되지 않았습니다")

        # 길찾기 페이지는 데스크톱 전용 context 사용
        desktop_context = await self._browser.new_context(
            viewport=self.DESKTOP_VIEWPORT,
            user_agent=self.DESKTOP_USER_AGENT,
            locale="ko-KR",
            timezone_id="Asia/Seoul",
        )

        # 스텔스 스크립트 주입
        if self.stealth:
            await desktop_context.add_init_script(StealthConfig.STEALTH_SCRIPTS)

        page: Page = await desktop_context.new_page()

        try:
            # 길찾기 페이지 접속
            await page.goto(self.DIRECTIONS_URL, wait_until="networkidle", timeout=30000)

            # 스텔스: 인간처럼 보이는 딜레이
            await self._human_like_delay(page)

            # 출발지 입력
            start_input = page.locator(self.SELECTORS["directions_start_input"])
            await start_input.click()
            await start_input.fill(start_landmark)
            await page.wait_for_timeout(1500)

            # 출발지 자동완성 결과에서 주소 일치 항목 클릭
            if not await self._click_autocomplete_with_area(page, start_landmark, area_hint):
                raise NaverMapScraperError(
                    f"출발지 검색 결과를 찾을 수 없습니다: {start_landmark}"
                )

            await page.wait_for_timeout(1000)

            # 도착지 입력
            goal_input = page.locator(self.SELECTORS["directions_goal_input"])
            await goal_input.click()
            await goal_input.fill(destination_place)
            await page.wait_for_timeout(1500)

            # 도착지 자동완성 결과에서 주소 일치 항목 클릭
            if not await self._click_autocomplete_with_area(page, destination_place, area_hint):
                raise NaverMapScraperError(
                    f"도착지 검색 결과를 찾을 수 없습니다: {destination_place}"
                )

            await page.wait_for_timeout(1000)

            # 길찾기 버튼 클릭
            search_btn = page.locator(self.SELECTORS["directions_search_btn"])
            await search_btn.click()

            # 결과 대기
            await page.wait_for_timeout(3000)

            # 걸음수 추출 (추천 경로에서 "걸음" 단위가 있는 값)
            try:
                # walk_direction_info 중 "걸음"이 포함된 요소 찾기
                steps_infos = await page.query_selector_all(".walk_direction_info")
                steps_text = None
                for info in steps_infos:
                    text = await info.inner_text()
                    if "걸음" in text:
                        steps_text = text
                        break
                if not steps_text:
                    # 폴백: 기존 셀렉터 사용
                    steps_element = page.locator(self.SELECTORS["directions_steps_value"]).first
                    await steps_element.wait_for(state="visible", timeout=10000)
                    steps_text = await steps_element.inner_text()
            except Exception:
                raise NaverMapScraperError(
                    f"걸음수를 찾을 수 없습니다: {start_landmark} → {destination_place}"
                )

            # 걸음수 파싱
            try:
                steps = self.parse_steps(steps_text)
            except ValueError as e:
                raise NaverMapScraperError(f"걸음수 파싱 실패: {str(e)}")

            return steps

        except NaverMapScraperError:
            raise
        except Exception as e:
            raise NaverMapScraperError(f"길찾기 중 오류 발생: {str(e)}")
        finally:
            await page.close()
            await desktop_context.close()

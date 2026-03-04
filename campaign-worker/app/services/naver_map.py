"""Naver Place scraper module.

Extracts place info, nearby landmarks, and walking steps from Naver Map.
Ported from reference/quantum-campaign/backend/app/services/naver_map.py.
"""

from __future__ import annotations

import logging
import random
import re
from dataclasses import dataclass
from typing import List, Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

logger = logging.getLogger(__name__)


@dataclass
class PlaceInfo:
    """Place basic info (name + address + representative image)."""

    name: Optional[str] = None
    address: Optional[str] = None
    image_url: Optional[str] = None

    @property
    def area(self) -> str:
        """Extract city/district level area from address.

        e.g. '부산 수영구 민락동 109' -> '부산 수영구'
        """
        if not self.address:
            return ""
        parts = self.address.split()
        if len(parts) >= 2:
            return f"{parts[0]} {parts[1]}"
        return parts[0] if parts else ""


@dataclass
class LandmarkInfo:
    """Nearby landmark info."""

    name: str
    url: Optional[str] = None
    place_id: Optional[str] = None
    distance_m: Optional[int] = None
    index: int = 0  # 1-based position in list


class NaverMapScraperError(Exception):
    """Naver Map scraper error."""


class StealthConfig:
    """Stealth configuration for bot detection evasion."""

    USER_AGENTS = [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 15_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.7 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.3 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; SM-A546B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Mobile Safari/537.36",
    ]

    VIEWPORTS = [
        {"width": 375, "height": 812},
        {"width": 390, "height": 844},
        {"width": 393, "height": 852},
        {"width": 360, "height": 800},
        {"width": 412, "height": 915},
        {"width": 384, "height": 854},
    ]

    MIN_DELAY = 2000
    MAX_DELAY = 5000

    STEALTH_SCRIPTS = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
    );
    Object.defineProperty(navigator, 'plugins', { get: () => [] });
    Object.defineProperty(navigator, 'languages', { get: () => ['ko-KR', 'ko', 'en-US', 'en'] });
    Object.defineProperty(navigator, 'connection', {
        get: () => ({ effectiveType: '4g', rtt: 50, downlink: 10, saveData: false })
    });
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
    """

    @classmethod
    def get_random_user_agent(cls) -> str:
        return random.choice(cls.USER_AGENTS)

    @classmethod
    def get_random_viewport(cls) -> dict:
        return random.choice(cls.VIEWPORTS)

    @classmethod
    def get_random_delay(cls) -> int:
        return random.randint(cls.MIN_DELAY, cls.MAX_DELAY)


class NaverMapScraper:
    """Naver Place scraper with stealth mode support."""

    SELECTORS = {
        "nearby_tab": 'a[role="tab"]:has-text("주변")',
        "nearby_tab_by_href": 'a[href*="/around"]',
        "landmark_tab": 'span.Me4yK:has-text("명소"), a.T00ux:has-text("명소")',
        "list_container": "ul.eDFz9",
        "list_item": "li.S0Ns3",
        "place_name": "span.xBZDS",
        "place_link": "a.place_bluelink, a.OiGhS",
        "directions_start_input": ".search_input_box_wrap.start input.input_search",
        "directions_goal_input": ".search_input_box_wrap.goal input.input_search",
        "directions_autocomplete_item": "li.item_place div.link_place",
        "directions_search_btn": "button.btn_direction.search",
        "directions_steps_container": ".walk_direction_info:has(.walk_direction_unit)",
        "directions_steps_value": ".walk_direction_value",
        "directions_steps_unit": ".walk_direction_unit",
    }

    AD_URL_PATTERNS = ["ader.naver.com", "ad.naver.com", "naver.me/ad"]
    DIRECTIONS_URL = "https://map.naver.com/p/directions/-/-/-/walk?c=15.00,0,0,0,dh"
    DESKTOP_VIEWPORT = {"width": 1280, "height": 900}
    DESKTOP_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    )

    def __init__(self, headless: bool = True, stealth: bool = True):
        self.headless = headless
        self.stealth = stealth
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._playwright = None
        self._user_agent: Optional[str] = None
        self._viewport: Optional[dict] = None

    async def init_browser(self) -> None:
        """Initialize Playwright browser with stealth settings."""
        if self._browser is not None:
            return

        self._playwright = await async_playwright().start()

        if self.stealth:
            self._user_agent = StealthConfig.get_random_user_agent()
            self._viewport = StealthConfig.get_random_viewport()
        else:
            self._user_agent = StealthConfig.USER_AGENTS[0]
            self._viewport = StealthConfig.VIEWPORTS[0]

        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ]

        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=launch_args,
        )

        self._context = await self._browser.new_context(
            viewport=self._viewport,
            user_agent=self._user_agent,
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            geolocation={"latitude": 37.5665, "longitude": 126.9780},
            permissions=["geolocation"],
            color_scheme="light",
            device_scale_factor=random.choice([2, 3]),
        )

        if self.stealth:
            await self._context.add_init_script(StealthConfig.STEALTH_SCRIPTS)

    async def close(self) -> None:
        """Clean up browser resources."""
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
        await self.init_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _human_like_delay(self, page: Page) -> None:
        if self.stealth:
            delay = StealthConfig.get_random_delay()
            await page.wait_for_timeout(delay)

    def _extract_place_id_from_url(self, url: str) -> Optional[str]:
        match = re.search(r"/place/(\d+)", url)
        if match:
            return match.group(1)
        match = re.search(r"/(restaurant|cafe|place)/(\d+)", url)
        if match:
            return match.group(2)
        return None

    AROUND_FILTER_LANDMARK = 100

    def _build_around_url(self, place_url: str, filter_code: int = 100) -> str:
        """Convert place URL to around tab URL with filter."""
        base_url = place_url.rstrip("/")
        if "/around" in base_url:
            base_url = base_url.split("/around")[0]

        tab_patterns = [
            "/home", "/feed", "/menu", "/booking", "/review",
            "/photo", "/location", "/information",
        ]
        for pattern in tab_patterns:
            if base_url.endswith(pattern):
                base_url = base_url[: -len(pattern)]
                break

        return f"{base_url}/around?filter={filter_code}"

    def _is_ad_url(self, url: str) -> bool:
        if not url:
            return False
        return any(pattern in url for pattern in self.AD_URL_PATTERNS)

    async def get_nearby_landmarks(
        self, place_url: str, max_count: int = 10
    ) -> List[LandmarkInfo]:
        """Extract nearby landmarks from place URL."""
        await self.init_browser()
        if not self._context:
            raise NaverMapScraperError("Browser not initialized")

        page: Page = await self._context.new_page()
        landmarks: List[LandmarkInfo] = []

        try:
            around_url = self._build_around_url(place_url)
            await page.goto(around_url, wait_until="domcontentloaded", timeout=60000)
            await self._human_like_delay(page)

            try:
                await page.wait_for_selector(self.SELECTORS["list_item"], timeout=10000)
            except Exception:
                raise NaverMapScraperError(f"Landmark list not found: {place_url}")

            items = await page.query_selector_all(self.SELECTORS["list_item"])
            landmark_order = 0

            for item in items:
                if len(landmarks) >= max_count:
                    break

                name_element = await item.query_selector(self.SELECTORS["place_name"])
                if not name_element:
                    continue

                name = (await name_element.inner_text()).strip()
                if not name:
                    continue

                link_element = await item.query_selector(self.SELECTORS["place_link"])
                url = None
                place_id = None

                if link_element:
                    href = await link_element.get_attribute("href")
                    if href:
                        if self._is_ad_url(href):
                            continue
                        if "m.place.naver.com" in href:
                            url = href
                            place_id = self._extract_place_id_from_url(href)

                distance_m = None
                try:
                    item_text = await item.inner_text()
                    dist_match = re.search(
                        r"이 장소에서\s+([\d,.]+)\s*(m|km)", item_text
                    )
                    if dist_match:
                        dist_val = float(dist_match.group(1).replace(",", ""))
                        dist_unit = dist_match.group(2)
                        distance_m = int(dist_val * 1000) if dist_unit == "km" else int(dist_val)
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
            raise NaverMapScraperError(f"Scraping error: {str(e)}")
        finally:
            await page.close()

        return landmarks

    async def select_landmark_by_min_distance(
        self, place_url: str, min_distance_m: int = 100,
        random_pick: bool = False, max_candidates: int = 5,
    ) -> Optional[LandmarkInfo]:
        """Select landmark by minimum distance criteria."""
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

        return landmarks[0] if landmarks else None

    async def get_place_info(self, place_url: str) -> PlaceInfo:
        """Extract place name, address, and image from place URL."""
        await self.init_browser()
        if not self._context:
            return PlaceInfo()

        page: Page = await self._context.new_page()
        info = PlaceInfo()

        try:
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

            if not info.name:
                title = await page.title()
                if title:
                    name = title.split(" : ")[0].strip()
                    if name and name != "네이버":
                        info.name = name

            address = await page.evaluate(
                """() => {
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
                for prefix in ["도로명", "지번"]:
                    if address.startswith(prefix):
                        address = address[len(prefix):].strip()
                info.address = address

            og_image = await page.evaluate(
                """() => {
                    const meta = document.querySelector('meta[property="og:image"]');
                    return meta ? meta.getAttribute('content') : null;
                }"""
            )
            if og_image and og_image.startswith("http"):
                info.image_url = og_image

            return info

        except Exception:
            return info
        finally:
            await page.close()

    @staticmethod
    def parse_steps(steps_text: str) -> int:
        """Parse steps text to integer (e.g. '1,234 걸음' -> 1234)."""
        if not steps_text:
            raise ValueError("Empty steps text")
        cleaned = re.sub(r"[^\d,]", "", steps_text).replace(",", "")
        if not cleaned:
            raise ValueError(f"Cannot parse steps: {steps_text}")
        return int(cleaned)

    async def _click_autocomplete_with_area(
        self, page: Page, search_term: str, area_hint: Optional[str] = None,
    ) -> bool:
        """Click autocomplete result matching area hint."""
        try:
            first_item = page.locator(self.SELECTORS["directions_autocomplete_item"]).first
            await first_item.wait_for(state="visible", timeout=5000)
        except Exception:
            return False

        if not area_hint:
            await first_item.click()
            return True

        items = await page.query_selector_all("li.item_place")
        for item in items:
            text = await item.inner_text()
            if area_hint in text:
                link = await item.query_selector("div.link_place")
                if link:
                    await link.click()
                    return True

        await first_item.click()
        return True

    async def get_walking_steps(
        self,
        start_landmark: str,
        destination_place: str,
        area_hint: Optional[str] = None,
    ) -> int:
        """Calculate walking steps from start to destination via Naver Map directions."""
        await self.init_browser()
        if not self._browser:
            raise NaverMapScraperError("Browser not initialized")

        desktop_context = await self._browser.new_context(
            viewport=self.DESKTOP_VIEWPORT,
            user_agent=self.DESKTOP_USER_AGENT,
            locale="ko-KR",
            timezone_id="Asia/Seoul",
        )
        if self.stealth:
            await desktop_context.add_init_script(StealthConfig.STEALTH_SCRIPTS)

        page: Page = await desktop_context.new_page()

        try:
            await page.goto(self.DIRECTIONS_URL, wait_until="networkidle", timeout=30000)
            await self._human_like_delay(page)

            # Enter start location
            start_input = page.locator(self.SELECTORS["directions_start_input"])
            await start_input.click()
            await start_input.fill(start_landmark)
            await page.wait_for_timeout(1500)

            if not await self._click_autocomplete_with_area(page, start_landmark, area_hint):
                raise NaverMapScraperError(f"Start location not found: {start_landmark}")
            await page.wait_for_timeout(1000)

            # Enter destination
            goal_input = page.locator(self.SELECTORS["directions_goal_input"])
            await goal_input.click()
            await goal_input.fill(destination_place)
            await page.wait_for_timeout(1500)

            if not await self._click_autocomplete_with_area(page, destination_place, area_hint):
                raise NaverMapScraperError(f"Destination not found: {destination_place}")
            await page.wait_for_timeout(1000)

            # Click search button
            search_btn = page.locator(self.SELECTORS["directions_search_btn"])
            await search_btn.click()
            await page.wait_for_timeout(6000)

            # Extract steps
            steps_text = None
            try:
                steps_infos = await page.query_selector_all(".walk_direction_info")
                for info in steps_infos:
                    text = await info.inner_text()
                    if "걸음" in text:
                        steps_text = text
                        break
                if not steps_text:
                    await page.wait_for_timeout(3000)
                    steps_infos = await page.query_selector_all(".walk_direction_info")
                    for info in steps_infos:
                        text = await info.inner_text()
                        if "걸음" in text:
                            steps_text = text
                            break
                if not steps_text:
                    steps_element = page.locator(self.SELECTORS["directions_steps_value"]).first
                    await steps_element.wait_for(state="visible", timeout=10000)
                    steps_text = await steps_element.inner_text()
            except Exception:
                raise NaverMapScraperError(
                    f"Steps not found: {start_landmark} -> {destination_place}"
                )

            try:
                return self.parse_steps(steps_text)
            except ValueError as e:
                raise NaverMapScraperError(f"Steps parsing failed: {str(e)}")

        except NaverMapScraperError:
            raise
        except Exception as e:
            raise NaverMapScraperError(f"Directions error: {str(e)}")
        finally:
            await page.close()
            await desktop_context.close()

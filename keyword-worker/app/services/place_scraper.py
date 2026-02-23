"""Naver Place data scraper using Playwright.

Extracts business info from Naver Place pages via Apollo State.
Ported from: reference/keyword-extract/src/place_scraper.py

Key data extracted:
- Basic info: name, category, address, phone
- Keywords: representative keywords, menus, review keywords
- Region info: city, gu, dong, stations
- Booking info: has_booking, booking_type
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ==================== Data Models ====================

@dataclass
class RegionInfo:
    """Parsed address region information."""

    city: str = ""
    si: str = ""
    gu: str = ""
    dong: str = ""
    road: str = ""
    si_without_suffix: str = ""
    gu_without_suffix: str = ""
    dong_without_suffix: str = ""
    major_area: str = ""
    stations: List[str] = field(default_factory=list)

    @property
    def station(self) -> str:
        return self.stations[0] if self.stations else ""


@dataclass
class ReviewKeyword:
    """Review keyword with mention count."""

    label: str
    count: int = 0


@dataclass
class PlaceData:
    """Complete Naver Place information."""

    id: str = ""
    name: str = ""
    category: str = ""
    road_address: str = ""
    jibun_address: str = ""
    region: RegionInfo = field(default_factory=RegionInfo)
    phone: str = ""
    virtual_phone: str = ""
    keywords: List[str] = field(default_factory=list)
    conveniences: List[str] = field(default_factory=list)
    micro_reviews: List[str] = field(default_factory=list)
    review_menu_keywords: List[ReviewKeyword] = field(default_factory=list)
    review_theme_keywords: List[ReviewKeyword] = field(default_factory=list)
    voted_keywords: List[ReviewKeyword] = field(default_factory=list)
    payment_info: List[str] = field(default_factory=list)
    seat_items: List[str] = field(default_factory=list)
    specialties: List[str] = field(default_factory=list)
    menus: List[str] = field(default_factory=list)
    medical_subjects: List[str] = field(default_factory=list)
    introduction: str = ""
    has_booking: bool = False
    booking_type: Optional[str] = None
    booking_hub_id: Optional[str] = None
    booking_url: Optional[str] = None
    url: str = ""
    discovered_regions: set = field(default_factory=set)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "road_address": self.road_address,
            "jibun_address": self.jibun_address,
            "region": {
                "city": self.region.city,
                "si": self.region.si,
                "gu": self.region.gu,
                "dong": self.region.dong,
                "road": self.region.road,
                "major_area": self.region.major_area,
                "stations": self.region.stations,
            },
            "phone": self.phone,
            "keywords": self.keywords,
            "conveniences": self.conveniences,
            "review_menu_keywords": [
                {"label": k.label, "count": k.count}
                for k in self.review_menu_keywords
            ],
            "review_theme_keywords": [
                {"label": k.label, "count": k.count}
                for k in self.review_theme_keywords
            ],
            "menus": self.menus,
            "medical_subjects": self.medical_subjects,
            "introduction": self.introduction,
            "has_booking": self.has_booking,
            "booking_type": self.booking_type,
            "url": self.url,
            "discovered_regions": list(self.discovered_regions),
        }


# ==================== Address Parser ====================

class AddressParser:
    """Korean address parser for extracting region info."""

    # Major area mappings: gu name -> major area short name
    MAJOR_AREA_MAP = {
        "일산동구": "일산",
        "일산서구": "일산",
        "덕양구": "고양",
        "기장군": "기장",
        "강화군": "강화",
        "옹진군": "옹진",
    }

    def parse(self, address: str, road_info: str = "") -> RegionInfo:
        """Parse Korean address into RegionInfo components."""
        region = RegionInfo()
        if not address:
            return region

        parts = address.split()

        for i, part in enumerate(parts):
            # City/Province (si/do)
            if part.endswith(("도", "특별시", "광역시", "특별자치시", "특별자치도")):
                region.city = part.replace("특별시", "").replace("광역시", "").replace(
                    "특별자치시", ""
                ).replace("특별자치도", "")
                if region.city.endswith("도"):
                    region.city = region.city[:-1]
            # Si (city within province)
            elif part.endswith("시") and not part.endswith(("특별시", "광역시")):
                region.si = part
                region.si_without_suffix = part[:-1] if len(part) > 2 else part
            # Gu (district)
            elif part.endswith("구"):
                region.gu = part
                region.gu_without_suffix = part[:-1] if len(part) > 2 else part
                # Major area extraction
                if part in self.MAJOR_AREA_MAP:
                    region.major_area = self.MAJOR_AREA_MAP[part]
            # Dong (neighborhood)
            elif part.endswith("동") and len(part) >= 2:
                # Avoid matching "구" patterns inside
                if not any(part.endswith(s) for s in ("동구", "동군")):
                    region.dong = part
                    region.dong_without_suffix = (
                        part[:-1] if len(part) > 2 else part
                    )
            # Road name
            elif part.endswith(("로", "길")) and i > 0:
                # Avoid number-only matches
                if not part[:-1].isdigit():
                    region.road = part

        # Extract station info from road_info
        if road_info:
            station_pattern = r"(\w+역)"
            stations = re.findall(station_pattern, road_info)
            region.stations = list(dict.fromkeys(stations))[:3]

        return region


# ==================== Place Scraper ====================

class PlaceScraper:
    """Naver Place data scraper using Playwright.

    Navigates to a Naver Place URL, extracts window.__APOLLO_STATE__,
    and parses business information.
    """

    USER_AGENTS = [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
        "Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 "
        "Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Linux; Android 13; SM-S918B) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 "
        "Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 12; Pixel 6) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 "
        "Mobile Safari/537.36",
    ]

    VIEWPORTS = [
        {"width": 390, "height": 844},
        {"width": 393, "height": 873},
        {"width": 360, "height": 800},
        {"width": 414, "height": 896},
    ]

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.address_parser = AddressParser()
        self._playwright = None
        self._browser = None

    async def __aenter__(self):
        await self._init_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._close_browser()

    async def _init_browser(self):
        """Initialize Playwright browser with anti-detection settings."""
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless
        )

    async def _close_browser(self):
        """Close browser and Playwright."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def get_place_data_by_url(self, url: str) -> Optional[PlaceData]:
        """Scrape place data from a direct Naver Place URL.

        Args:
            url: Naver Place URL (e.g., https://m.place.naver.com/restaurant/12345/home)

        Returns:
            PlaceData object or None if scraping fails.
        """
        if not self._browser:
            await self._init_browser()

        context = await self._browser.new_context(
            user_agent=random.choice(self.USER_AGENTS),
            viewport=random.choice(self.VIEWPORTS),
            locale="ko-KR",
            extra_http_headers={
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-Mode": "navigate",
            },
        )
        page = await context.new_page()

        # Anti-detection scripts
        await page.add_init_script("""
            Object.defineProperty(document, 'referrer', { get: () => '' });
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(random.uniform(1.5, 2.5))

            # Extract Apollo State
            apollo_state = await self._extract_apollo_state(page)
            if not apollo_state:
                logger.warning("Failed to extract Apollo State from %s", url)
                return None

            place_data = self._parse_apollo_data(apollo_state)

            # Scrape review keywords from DOM for more accurate data
            if place_data:
                await self._scrape_review_keywords_from_dom(page, place_data, url)
                place_data.url = url

            return place_data

        except Exception as e:
            logger.error("Error scraping %s: %s", url, e)
            return None
        finally:
            await page.close()
            await context.close()

    async def _extract_apollo_state(self, page) -> Optional[dict]:
        """Extract window.__APOLLO_STATE__ from page."""
        try:
            apollo_data = await page.evaluate("""
                () => {
                    if (window.__APOLLO_STATE__) {
                        return window.__APOLLO_STATE__;
                    }
                    return null;
                }
            """)
            return apollo_data
        except Exception as e:
            logger.error("Apollo State extraction failed: %s", e)
            return None

    def _parse_apollo_data(self, apollo_state: dict) -> Optional[PlaceData]:
        """Parse Apollo State into PlaceData object."""
        # Find PlaceDetailBase key
        place_key = None
        for key in apollo_state.keys():
            if key.startswith("PlaceDetailBase:"):
                place_key = key
                break

        if not place_key:
            logger.warning("PlaceDetailBase key not found in Apollo State")
            return None

        data = apollo_state[place_key]
        place_id = place_key.split(":")[1]

        # Extract keywords from themes or keywordList
        keyword_data = []
        themes = data.get("themes")
        if themes and isinstance(themes, list):
            keyword_data = [
                t.get("name")
                for t in themes
                if isinstance(t, dict) and t.get("name")
            ]
        if not keyword_data:
            keyword_data = data.get("keywords") or data.get("keywordList") or []

        place = PlaceData(
            id=place_id,
            name=data.get("name", ""),
            category=data.get("category", ""),
            road_address=data.get("roadAddress", ""),
            jibun_address=data.get("address", ""),
            phone=data.get("phone", ""),
            keywords=keyword_data if isinstance(keyword_data, list) else [],
            conveniences=data.get("conveniences", []) or [],
            payment_info=data.get("paymentInfo", []) or [],
        )

        # Hospital-specific data from ROOT_QUERY
        root_query = apollo_state.get("ROOT_QUERY", {})
        place_detail_key = None
        for key in root_query.keys():
            if "placeDetail" in key:
                place_detail_key = key
                break

        if place_detail_key:
            place_detail = root_query[place_detail_key]
            if isinstance(place_detail, dict):
                # informationTab keywordList
                info_tab_key = None
                for key in place_detail.keys():
                    if key.startswith("informationTab"):
                        info_tab_key = key
                        break

                if info_tab_key:
                    info_tab_ref = place_detail.get(info_tab_key)
                    if isinstance(info_tab_ref, dict):
                        ref_key = info_tab_ref.get("__ref")
                        if ref_key and ref_key in apollo_state:
                            info_tab = apollo_state[ref_key]
                            kw_list = info_tab.get("keywordList", [])
                            if kw_list:
                                place.keywords = kw_list

                # Hospital info (subjects)
                hospital_info_ref = place_detail.get("hospitalInfo")
                if isinstance(hospital_info_ref, dict):
                    ref_key = hospital_info_ref.get("__ref")
                    hospital_info = None
                    if ref_key and ref_key in apollo_state:
                        hospital_info = apollo_state[ref_key]
                    elif "sortedSubjects" in hospital_info_ref:
                        hospital_info = hospital_info_ref

                    if hospital_info:
                        sorted_subjects = (
                            hospital_info.get("sortedSubjects")
                            or hospital_info.get("subjects")
                            or []
                        )
                        place.medical_subjects = [
                            s.get("name")
                            for s in sorted_subjects
                            if isinstance(s, dict) and s.get("name")
                        ]

        # Introduction
        place.introduction = data.get("introduction") or data.get("description") or ""

        # Micro reviews
        micro_reviews = data.get("microReviews", [])
        if micro_reviews:
            for r in micro_reviews:
                if isinstance(r, str):
                    place.micro_reviews.append(r)
                elif isinstance(r, dict) and r.get("name"):
                    place.micro_reviews.append(r.get("name"))

        # Review stats (VisitorReviewStatsResult)
        review_stats_key = None
        for key in apollo_state.keys():
            if key.startswith("VisitorReviewStatsResult:"):
                review_stats_key = key
                break

        if review_stats_key:
            review_data = apollo_state[review_stats_key]
            analysis = review_data.get("analysis") or {}

            menus = analysis.get("menus") or []
            for m in menus:
                if isinstance(m, dict):
                    place.review_menu_keywords.append(
                        ReviewKeyword(label=m.get("label", ""), count=m.get("count", 0))
                    )

            themes_list = analysis.get("themes") or []
            for t in themes_list:
                if isinstance(t, dict):
                    place.review_theme_keywords.append(
                        ReviewKeyword(label=t.get("label", ""), count=t.get("count", 0))
                    )

            voted_keywords = review_data.get("votedKeyword") or []
            for v in voted_keywords:
                if isinstance(v, dict):
                    place.voted_keywords.append(
                        ReviewKeyword(
                            label=v.get("displayName", "") or v.get("label", ""),
                            count=v.get("count", 0),
                        )
                    )

        # Seat items
        for key, value in apollo_state.items():
            if key.startswith("RestaurantSeatItems:"):
                seat_name = value.get("value", "") or value.get("name", "")
                if seat_name:
                    place.seat_items.append(seat_name)

        # Station info (SubwayStationInfo)
        station_name = ""
        for key, value in apollo_state.items():
            if key.startswith("SubwayStationInfo"):
                station_name = value.get("name", "")
                if station_name:
                    break

        # Parse address
        road_info = data.get("road", "")
        place.region = self.address_parser.parse(
            place.jibun_address or place.road_address, road_info=road_info
        )
        if place.road_address and not place.region.road:
            road_region = self.address_parser.parse(place.road_address)
            if road_region.road:
                place.region.road = road_region.road
        if station_name and not place.region.station:
            place.region.stations = [f"{station_name}역"]

        # Menus from review keywords
        place.menus = [rk.label for rk in place.review_menu_keywords if rk.label]

        return place

    async def _scrape_review_keywords_from_dom(
        self, page, place_data: PlaceData, base_url: str
    ):
        """Scrape review keywords from DOM for more accurate data."""
        try:
            review_url = base_url.replace("/home", "/review").replace(
                "/information", "/review"
            )
            if "/review" not in review_url:
                review_url = review_url.rstrip("/") + "/review"

            await page.goto(review_url, wait_until="networkidle", timeout=15000)
            await asyncio.sleep(1)

            keywords_data = await page.evaluate("""
                () => {
                    const result = { menus: [], themes: [] };
                    const containers = document.querySelectorAll('.YYh8o');
                    containers.forEach(container => {
                        const categorySpan = container.querySelector('span');
                        if (!categorySpan) return;
                        const category = categorySpan.textContent.trim();
                        const keywordLinks = container.querySelectorAll('a.T00ux');
                        const keywords = [];
                        keywordLinks.forEach(link => {
                            const spans = link.querySelectorAll('span');
                            if (spans.length >= 2) {
                                keywords.push({
                                    label: spans[0].textContent.trim(),
                                    count: parseInt(spans[1].textContent.replace(/,/g, '')) || 0
                                });
                            }
                        });
                        if (category === '메뉴') result.menus = keywords;
                        else if (category === '특징') result.themes = keywords;
                    });
                    return result;
                }
            """)

            if keywords_data.get("menus"):
                place_data.review_menu_keywords = [
                    ReviewKeyword(label=m["label"], count=m["count"])
                    for m in keywords_data["menus"]
                ]
                place_data.menus = [m["label"] for m in keywords_data["menus"]]

            if keywords_data.get("themes"):
                place_data.review_theme_keywords = [
                    ReviewKeyword(label=t["label"], count=t["count"])
                    for t in keywords_data["themes"]
                ]

        except Exception as e:
            logger.debug("Review tab scraping failed: %s", e)

"""superap.io Playwright automation client.

Manages per-account browser contexts for multi-account support.
Provides campaign registration, editing, keyword changes, and status queries.

Ported from reference/quantum-campaign/backend/app/services/superap.py
with adaptations for the integrated platform's async PostgreSQL architecture.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

logger = logging.getLogger(__name__)


# ============================================================
# Campaign type selection mapping
# ============================================================

CAMPAIGN_TYPE_SELECTION_MAP: Dict[str, str] = {
    # Place
    "기본 플레이스 저장하기": "place_save_default",
    "플레이스 URL 공유하기": "place_save_share",
    "컵페 클릭 후 저장": "place_save_click",
    "플레이스 방문 & 저장": "place_save_home",
    "keep 공유": "place_save_keep",
    "알림받기": "place_save_noti",
    "검색 후 정답 입력": "place_save_tab",
    "서치 커스텀 미션(스크린샷 제출 타입)": "place_save_search",
    # Quiz
    "대표자명 맞추기": "cpc_detail_ceo_name",
    "상품 클릭 후 태그 단어 맞추기": "cpc_detail_click_tag",
    "상품 클릭 후 대표자명 맞추기": "cpc_detail_click_ceo_name",
    "플레이스 퀴즈": "cpc_detail_place",
    "서치 플레이스 퀴즈": "cpc_detail_place_quiz",
    # Product click
    "기본 상품클릭": "pick_shop_default",
    "상품 클릭 후 상품평": "pick_shop_click",
    "무신사 상품 평하기": "pick_shop_musinsa_like",
    "카카오톡 선물하기 평하기": "pick_shop_kakao_like",
    # Notification
    "기본 알림받기": "receive_notification_default",
    "상품 클릭 후 알림받기": "receive_notification_click",
    # YouTube
    "시청하기": "video_length_default",
    "구독하기": "youtube_subs_default",
    "쇼츠 좋아요": "short_like_default",
    "영상 좋아요": "youtube_like_default",
    "영상 좋아요 & 채널 구독": "youtube_like_subs_default",
    # SNS
    "인스타그램 팔로우": "sns_instagram_follow",
    "인스타그램 게시물 좋아요": "sns_instagram_like",
}


def resolve_campaign_type_value(campaign_type_selection: str) -> Optional[str]:
    """Convert Korean label or radio value to superap.io radio value."""
    if not campaign_type_selection:
        return None
    if campaign_type_selection in CAMPAIGN_TYPE_SELECTION_MAP.values():
        return campaign_type_selection
    return CAMPAIGN_TYPE_SELECTION_MAP.get(campaign_type_selection)


# ============================================================
# Data classes
# ============================================================


@dataclass
class CampaignFormData:
    """Campaign registration form data."""

    campaign_name: str
    place_name: str
    landmark_name: str
    participation_guide: str
    keywords: List[str]
    hint: str
    walking_steps: int = 0
    conversion_text: Optional[str] = None

    start_date: Optional[Union[date, datetime, str]] = None
    end_date: Optional[Union[date, datetime, str]] = None

    daily_limit: int = 300
    total_limit: Optional[int] = None

    links: List[str] = field(default_factory=list)
    campaign_type: str = "traffic"

    _processed_guide: str = field(default="", init=False, repr=False)
    _processed_keywords: str = field(default="", init=False, repr=False)

    def __post_init__(self) -> None:
        self._process_templates()
        self._process_keywords()
        self._calculate_total_limit()

    def _process_templates(self) -> None:
        guide = self.participation_guide
        masked_place_name = self._mask_place_name(self.place_name)
        guide = guide.replace("&상호명&", masked_place_name)
        guide = guide.replace("&명소명&", self.landmark_name)
        self._processed_guide = guide

    def _mask_place_name(self, name: str) -> str:
        """Mask every 2nd character with X.

        Example: "일류곱창 마포공덕본점" -> "일X곱X 마X공X본X"
        """
        if not name:
            return name
        result = []
        char_count = 0
        for char in name:
            if char == " ":
                result.append(char)
            else:
                char_count += 1
                if char_count % 2 == 0:
                    result.append("X")
                else:
                    result.append(char)
        return "".join(result)

    def _process_keywords(self) -> None:
        if not self.keywords:
            self._processed_keywords = ""
            return
        cleaned = [kw.strip() for kw in self.keywords if kw.strip()]
        random.shuffle(cleaned)
        result: list[str] = []
        current_length = 0
        for keyword in cleaned:
            separator = "," if result else ""
            new_length = current_length + len(separator) + len(keyword)
            if new_length <= 255:
                result.append(keyword)
                current_length = new_length
            else:
                break
        self._processed_keywords = ",".join(result)

    def _calculate_total_limit(self) -> None:
        if self.total_limit is not None:
            return
        if self.start_date and self.end_date:
            start = self._normalize_date(self.start_date)
            end = self._normalize_date(self.end_date)
            days = (end - start).days + 1
            self.total_limit = days * self.daily_limit

    def _normalize_date(self, d: Union[date, datetime, str]) -> date:
        if isinstance(d, datetime):
            return d.date()
        if isinstance(d, date):
            return d
        if isinstance(d, str):
            return datetime.strptime(d, "%Y-%m-%d").date()
        return d

    def get_start_date_str(self) -> str:
        if not self.start_date:
            return ""
        d = self._normalize_date(self.start_date)
        return f"{d.strftime('%Y-%m-%d')} 00:00:00"

    def get_end_date_str(self) -> str:
        if not self.end_date:
            return ""
        d = self._normalize_date(self.end_date)
        return f"{d.strftime('%Y-%m-%d')} 23:59:59"

    def generate_campaign_name(self) -> str:
        name_chars = [c for c in self.place_name if c != " "]
        if len(name_chars) <= 2:
            prefix = name_chars[0] if name_chars else ""
        else:
            prefix = "".join(name_chars[:2])
        if self.campaign_type == "save":
            return f"{prefix} 저장 퀴즈 맞추기"
        return f"{prefix} 퀴즈 맞추기"

    @property
    def processed_guide(self) -> str:
        return self._processed_guide

    @property
    def processed_keywords(self) -> str:
        return self._processed_keywords

    def get_keywords_count(self) -> int:
        if not self._processed_keywords:
            return 0
        return len(self._processed_keywords.split(","))


@dataclass
class CampaignFormResult:
    """Campaign form fill result."""

    success: bool
    screenshot_path: Optional[str] = None
    filled_fields: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class SubmitResult:
    """Campaign submit result."""

    success: bool
    campaign_code: Optional[str] = None
    error_message: Optional[str] = None
    redirect_url: Optional[str] = None


# ============================================================
# Exceptions
# ============================================================


class SuperapError(Exception):
    pass


class SuperapLoginError(SuperapError):
    pass


class SuperapCampaignError(SuperapError):
    pass


# ============================================================
# Stealth configuration
# ============================================================


class StealthConfig:
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) "
        "Gecko/20100101 Firefox/122.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    ]
    VIEWPORTS = [
        {"width": 1920, "height": 1080},
        {"width": 1680, "height": 1050},
        {"width": 1440, "height": 900},
        {"width": 1536, "height": 864},
    ]
    MIN_DELAY = 1000
    MAX_DELAY = 3000
    STEALTH_SCRIPTS = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
    );
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    Object.defineProperty(navigator, 'languages', { get: () => ['ko-KR', 'ko', 'en-US', 'en'] });
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


# ============================================================
# SuperapClient
# ============================================================


class SuperapClient:
    """superap.io Playwright automation client.

    Manages per-account browser contexts for multi-account login.
    Provides campaign registration, editing, keyword changes, and status queries.
    """

    BASE_URL = "https://superap.io"
    LOGIN_URL = "https://superap.io"
    DASHBOARD_URL = "https://superap.io/service/reward/adver/report"
    CAMPAIGN_CREATE_URL = "https://superap.io/service/reward/adver/add?mode=add"
    CAMPAIGN_EDIT_URL = (
        "https://superap.io/service/reward/adver/add?mode=modify&id={campaign_code}"
    )
    CAMPAIGN_LIST_URL = "https://superap.io/service/reward/adver/report"

    SELECTORS = {
        "login_form": 'form[action="/j_spring_security_check"]',
        "username_input": 'input[name="j_username"]',
        "password_input": 'input[name="j_password"]',
        "login_button": 'button[type="submit"]',
        "logout_link": 'a[href*="logout"]',
        "error_message": '.error, .alert-danger, [class*="error"]',
    }

    CAMPAIGN_SELECTORS = {
        "campaign_name": 'input[name="ad_title"]',
        "participation_guide": 'textarea[name="description"]',
        "keywords": 'input[name="search_keyword"]',
        "hint": 'input[name="target_package"], input#inp_product_name',
        "total_budget": 'input#total_budget, input[name="total_budget"]',
        "day_budget": 'input#day_budget, input[name="day_budget"]',
        "begin_date": 'input#begin_date, input[name="begin_date"]',
        "end_date": 'input#end_date, input[name="end_date"]',
        "conversion_input": "input.ad_event_name-input",
        "conversion_hidden": 'input#ad_event_name, input[name="ad_event_name"]',
        "conversion_add_btn": "button.btn-add-event",
        "link_add_btn": "button.btn-add-url",
        "link_inputs": 'input[name^="url_"], input.url-input',
        "campaign_type_traffic": 'input[name="rdo_cpa_type"][value="cpc_detail_place"]',
        "campaign_type_save": 'input[name="rdo_cpa_type"][value="place_save_search"]',
        "submit_button": (
            'button:has-text("수정"), button:has-text("등록"), '
            'input[type="submit"], button.btn-submit'
        ),
        "form_container": "form",
        "campaign_table": "table.table, .campaign-list, #campaign-table",
        "campaign_row": "table.table tbody tr, .campaign-item",
        "campaign_code_cell": "td:first-child, .campaign-code",
        "success_message": '.success, .alert-success, [class*="success"]',
        "error_alert": '.alert-danger, .error-message, [class*="error"]',
    }

    SCREENSHOT_DIR = "screenshots/campaigns"

    def __init__(self, headless: bool = True, stealth: bool = True) -> None:
        self.headless = headless
        self.stealth = stealth
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._contexts: Dict[str, BrowserContext] = {}
        self._pages: Dict[str, Page] = {}

    async def initialize(self) -> None:
        if self._browser is not None:
            return
        self._playwright = await async_playwright().start()
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ]
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=launch_args,
        )

    async def close(self) -> None:
        for account_id in list(self._contexts.keys()):
            await self.close_context(account_id)
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def __aenter__(self) -> "SuperapClient":
        await self.initialize()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def get_context(self, account_id: str) -> BrowserContext:
        await self.initialize()
        if account_id in self._contexts:
            return self._contexts[account_id]
        if self.stealth:
            user_agent = StealthConfig.get_random_user_agent()
            viewport = StealthConfig.get_random_viewport()
        else:
            user_agent = StealthConfig.USER_AGENTS[0]
            viewport = StealthConfig.VIEWPORTS[0]
        context = await self._browser.new_context(
            viewport=viewport,
            user_agent=user_agent,
            locale="ko-KR",
            timezone_id="Asia/Seoul",
        )
        if self.stealth:
            await context.add_init_script(StealthConfig.STEALTH_SCRIPTS)
        self._contexts[account_id] = context
        return context

    async def close_context(self, account_id: str) -> None:
        if account_id in self._pages:
            try:
                await self._pages[account_id].close()
            except Exception:
                pass
            del self._pages[account_id]
        if account_id in self._contexts:
            await self._contexts[account_id].close()
            del self._contexts[account_id]

    async def _human_like_delay(self, page: Page) -> None:
        if self.stealth:
            delay = StealthConfig.get_random_delay()
            await page.wait_for_timeout(delay)

    async def is_logged_in(self, page: Page) -> bool:
        current_url = page.url
        if "/service/" in current_url or "/dashboard" in current_url.lower():
            return True
        login_form = await page.query_selector(self.SELECTORS["login_form"])
        return login_form is None

    async def login(
        self,
        account_id: str,
        username: str,
        password: str,
        force: bool = False,
    ) -> bool:
        """Login to superap.io with the given credentials."""
        context = await self.get_context(account_id)
        if account_id in self._pages and not force:
            page = self._pages[account_id]
            if await self.is_logged_in(page):
                return True
            await page.close()
            del self._pages[account_id]
        page = await context.new_page()
        try:
            await page.goto(self.LOGIN_URL, wait_until="networkidle", timeout=30000)
            await self._human_like_delay(page)
            if not force and await self.is_logged_in(page):
                self._pages[account_id] = page
                return True
            try:
                await page.wait_for_selector(
                    self.SELECTORS["login_form"], timeout=10000
                )
            except Exception:
                if await self.is_logged_in(page):
                    self._pages[account_id] = page
                    return True
                await page.close()
                return False
            username_input = page.locator(self.SELECTORS["username_input"])
            await username_input.click()
            await username_input.fill(username)
            await self._human_like_delay(page)
            password_input = page.locator(self.SELECTORS["password_input"])
            await password_input.click()
            await password_input.fill(password)
            await self._human_like_delay(page)
            login_button = page.locator(self.SELECTORS["login_button"])
            await login_button.click()
            await page.wait_for_timeout(3000)
            if await self.is_logged_in(page):
                self._pages[account_id] = page
                return True
            error_element = await page.query_selector(
                self.SELECTORS["error_message"]
            )
            if error_element:
                error_text = await error_element.inner_text()
                await page.close()
                raise SuperapLoginError(f"Login failed: {error_text}")
            await page.close()
            raise SuperapLoginError("Login failed: unknown error")
        except SuperapLoginError:
            raise
        except Exception as e:
            await page.close()
            raise SuperapLoginError(f"Login error: {str(e)}")

    async def get_page(self, account_id: str) -> Page:
        if account_id in self._pages:
            page = self._pages[account_id]
            if await self.is_logged_in(page):
                return page
            await page.close()
            del self._pages[account_id]
        raise SuperapError(
            f"Account {account_id} is not logged in. Call login() first."
        )

    def get_active_accounts(self) -> list:
        return list(self._contexts.keys())

    # ============================================================
    # Form helpers
    # ============================================================

    async def _find_element(self, page: Page, selector: str) -> Any:
        """Find the first matching element from comma-separated selectors."""
        selectors = [s.strip() for s in selector.split(",")]
        for sel in selectors:
            element = await page.query_selector(sel)
            if element:
                return element
        return None

    async def _fill_input_field(
        self, page: Page, selector: str, value: str, field_name: str
    ) -> bool:
        try:
            selectors = [s.strip() for s in selector.split(",")]
            element = None
            for sel in selectors:
                element = await page.query_selector(sel)
                if element:
                    break
            if not element:
                return False
            await element.click()
            await page.wait_for_timeout(100)
            await element.evaluate("el => el.select && el.select()")
            await page.keyboard.press("Backspace")
            await element.fill(value)
            await self._human_like_delay(page)
            return True
        except Exception:
            return False

    async def _fill_autonumeric_field(
        self, page: Page, selector: str, value: int
    ) -> bool:
        try:
            result = await page.evaluate(
                """({selector, value}) => {
                const selectors = selector.split(',').map(s => s.trim());
                let el = null;
                for (const sel of selectors) {
                    el = document.querySelector(sel);
                    if (el) break;
                }
                if (!el) return false;
                if (window.AutoNumeric && AutoNumeric.getAutoNumericElement(el)) {
                    AutoNumeric.getAutoNumericElement(el).set(value);
                } else {
                    el.value = value;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }
                return true;
            }""",
                {"selector": selector, "value": value},
            )
            return bool(result)
        except Exception:
            return False

    async def _set_campaign_dates(
        self, page: Page, form_data: CampaignFormData
    ) -> tuple[bool, bool]:
        start_success = False
        end_success = False
        try:
            start_date_str = form_data.get_start_date_str()
            if start_date_str:
                result = await page.evaluate(
                    """(args) => {
                    var dateStr = args.dateStr;
                    var el = document.querySelector('input#begin_date') ||
                             document.querySelector('input[name="begin_date"]');
                    if (!el) return false;
                    if (window.jQuery && window.moment) {
                        var $el = jQuery(el);
                        var picker = $el.data('daterangepicker');
                        if (picker) {
                            var m = moment(dateStr, 'YYYY-MM-DD HH:mm:ss');
                            if (m.isValid()) {
                                picker.setStartDate(m); picker.setEndDate(m);
                                if (typeof picker.callback === 'function')
                                    picker.callback(m, m, picker.chosenLabel);
                                el.value = dateStr;
                                $el.val(dateStr).trigger('change');
                                return true;
                            }
                        }
                    }
                    el.removeAttribute('readonly');
                    el.value = dateStr;
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                    return true;
                }""",
                    {"dateStr": start_date_str},
                )
                start_success = bool(result)

            end_date_str = form_data.get_end_date_str()
            if end_date_str:
                result = await page.evaluate(
                    """(args) => {
                    var dateStr = args.dateStr;
                    var el = document.querySelector('input#end_date') ||
                             document.querySelector('input[name="end_date"]');
                    if (!el) return false;
                    if (window.jQuery && window.moment) {
                        var $el = jQuery(el);
                        var picker = $el.data('daterangepicker');
                        if (picker) {
                            var m = moment(dateStr, 'YYYY-MM-DD HH:mm:ss');
                            if (m.isValid()) {
                                picker.setStartDate(m); picker.setEndDate(m);
                                if (typeof picker.callback === 'function')
                                    picker.callback(m, m, picker.chosenLabel);
                                el.value = dateStr;
                                $el.val(dateStr).trigger('change');
                                return true;
                            }
                        }
                    }
                    el.removeAttribute('readonly');
                    el.value = dateStr;
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                    return true;
                }""",
                    {"dateStr": end_date_str},
                )
                end_success = bool(result)
            await self._human_like_delay(page)
        except Exception:
            pass
        return start_success, end_success

    async def _add_campaign_links(
        self, page: Page, links: List[str]
    ) -> int:
        if not links:
            return 0
        max_links = min(len(links), 3)
        added_count = 0
        try:
            detail_type = await page.evaluate(
                "document.getElementById('detail_type') "
                "? document.getElementById('detail_type').value : ''"
            )
            for i in range(max_links - 1):
                add_btn = await self._find_element(
                    page, self.CAMPAIGN_SELECTORS["link_add_btn"]
                )
                if add_btn:
                    await add_btn.click()
                    await page.wait_for_timeout(300)
            await page.wait_for_timeout(500)
            link_inputs = await page.query_selector_all(
                'input.url-input, input[name^="url_"]'
            )
            for i in range(min(len(link_inputs), max_links)):
                if i < len(links):
                    url = links[i]
                    if detail_type and "#" not in url:
                        url = f"{url}#{detail_type}"
                    await link_inputs[i].click()
                    await link_inputs[i].fill(url)
                    added_count += 1
                    await page.wait_for_timeout(200)
        except Exception:
            pass
        return added_count

    async def _set_conversion_criteria(
        self, page: Page, walking_steps: int
    ) -> bool:
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(500)
            conversion_input = await self._find_element(
                page, self.CAMPAIGN_SELECTORS["conversion_input"]
            )
            if conversion_input:
                await conversion_input.click()
                await conversion_input.fill(str(walking_steps))
                await self._human_like_delay(page)
                return True
            return False
        except Exception:
            return False

    async def _set_conversion_text(self, page: Page, text: str) -> bool:
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(500)
            conversion_input = await self._find_element(
                page, self.CAMPAIGN_SELECTORS["conversion_input"]
            )
            if conversion_input:
                await conversion_input.click()
                await conversion_input.fill(text)
                await self._human_like_delay(page)
                return True
            return False
        except Exception:
            return False

    async def _set_campaign_type(
        self, page: Page, campaign_type: str
    ) -> bool:
        try:
            legacy_map = {"traffic": "cpc_detail_place", "save": "place_save_tab"}
            radio_value = legacy_map.get(campaign_type)
            if not radio_value:
                radio_value = resolve_campaign_type_value(campaign_type)
            if not radio_value:
                logger.warning(f"Unknown campaign type: {campaign_type}")
                return False
            selector = f'input[name="rdo_cpa_type"][value="{radio_value}"]'
            radio = await page.query_selector(selector)
            if radio:
                await radio.click()
                await self._human_like_delay(page)
                return True
            logger.warning(f"Campaign type radio not found: {selector}")
            return False
        except Exception:
            return False

    async def _navigate_to_campaign_form(self, page: Page) -> bool:
        try:
            await page.goto(
                self.CAMPAIGN_CREATE_URL, wait_until="networkidle", timeout=30000
            )
            await self._human_like_delay(page)
            url_lower = page.url.lower()
            return "/adver/add" in url_lower or "/campaign" in url_lower
        except Exception:
            return False

    async def _save_screenshot(
        self, page: Page, prefix: str = "campaign_form"
    ) -> Optional[str]:
        try:
            os.makedirs(self.SCREENSHOT_DIR, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{prefix}_{timestamp}.png"
            filepath = os.path.join(self.SCREENSHOT_DIR, filename)
            await page.screenshot(path=filepath, full_page=True)
            return filepath
        except Exception:
            return None

    # ============================================================
    # Campaign form fill & submit
    # ============================================================

    async def fill_campaign_form(
        self,
        account_id: str,
        form_data: CampaignFormData,
        take_screenshot: bool = True,
    ) -> CampaignFormResult:
        """Fill the campaign registration form on superap.io."""
        result = CampaignFormResult(success=False)
        page = await self.get_page(account_id)
        try:
            if not await self._navigate_to_campaign_form(page):
                result.errors.append("Failed to navigate to campaign form page")
                return result

            if await self._set_campaign_type(page, form_data.campaign_type):
                result.filled_fields.append("campaign_type")
            else:
                result.errors.append("Campaign type selection failed")

            await page.wait_for_timeout(500)

            if await self._fill_input_field(
                page,
                self.CAMPAIGN_SELECTORS["campaign_name"],
                form_data.campaign_name,
                "campaign_name",
            ):
                result.filled_fields.append("campaign_name")
            else:
                result.errors.append("Campaign name input failed")

            if await self._fill_input_field(
                page,
                self.CAMPAIGN_SELECTORS["participation_guide"],
                form_data.processed_guide,
                "participation_guide",
            ):
                result.filled_fields.append("participation_guide")
            else:
                result.errors.append("Participation guide input failed")

            if await self._fill_input_field(
                page,
                self.CAMPAIGN_SELECTORS["keywords"],
                form_data.processed_keywords,
                "keywords",
            ):
                result.filled_fields.append("keywords")
            else:
                result.errors.append("Keywords input failed")

            if await self._fill_input_field(
                page,
                self.CAMPAIGN_SELECTORS["hint"],
                form_data.hint,
                "hint",
            ):
                result.filled_fields.append("hint")
            else:
                result.errors.append("Hint input failed")

            await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            await page.wait_for_timeout(500)

            if form_data.total_limit:
                if await self._fill_autonumeric_field(
                    page, self.CAMPAIGN_SELECTORS["total_budget"], form_data.total_limit
                ):
                    result.filled_fields.append("total_budget")
                else:
                    result.errors.append("Total budget input failed")

            if await self._fill_autonumeric_field(
                page, self.CAMPAIGN_SELECTORS["day_budget"], form_data.daily_limit
            ):
                result.filled_fields.append("day_budget")
            else:
                result.errors.append("Daily budget input failed")

            start_ok, end_ok = await self._set_campaign_dates(page, form_data)
            if start_ok:
                result.filled_fields.append("start_date")
            else:
                result.errors.append("Start date setting failed")
            if end_ok:
                result.filled_fields.append("end_date")
            else:
                result.errors.append("End date setting failed")

            if form_data.links:
                links_added = await self._add_campaign_links(page, form_data.links)
                if links_added > 0:
                    result.filled_fields.append(f"links({links_added})")
                else:
                    result.errors.append("Link addition failed")

            if form_data.conversion_text:
                if await self._set_conversion_text(page, form_data.conversion_text):
                    result.filled_fields.append("conversion_text")
                else:
                    result.errors.append("Conversion text input failed")
            elif form_data.walking_steps:
                if await self._set_conversion_criteria(
                    page, form_data.walking_steps
                ):
                    result.filled_fields.append("walking_steps")
                else:
                    result.errors.append("Walking steps input failed")

            if take_screenshot:
                screenshot_path = await self._save_screenshot(page)
                if screenshot_path:
                    result.screenshot_path = screenshot_path

            if len(result.filled_fields) >= 5:
                result.success = True
            else:
                result.errors.append(
                    f"Not enough fields filled: {len(result.filled_fields)}/10"
                )
            return result
        except SuperapError:
            raise
        except Exception as e:
            result.errors.append(f"Form fill error: {str(e)}")
            return result

    async def submit_campaign(
        self, account_id: str, campaign_name: Optional[str] = None
    ) -> SubmitResult:
        """Click the submit button and capture the campaign code.

        If DRY_RUN is enabled, skips actual submission and returns a fake code.
        """
        from app.core.config import settings as worker_settings

        page = await self.get_page(account_id)
        result = SubmitResult(success=False)

        # --- DRY_RUN: 실제 제출 스킵 ---
        if worker_settings.DRY_RUN:
            import secrets
            fake_code = f"DRY{secrets.token_hex(3).upper()}"
            logger.info(f"[DRY_RUN] submit_campaign skipped — fake code: {fake_code}")
            await self._save_screenshot(page, f"dryrun_submit_{account_id}")
            result.success = True
            result.campaign_code = fake_code
            return result

        try:
            selectors = [
                s.strip()
                for s in self.CAMPAIGN_SELECTORS["submit_button"].split(",")
            ]
            submit_button = None
            for sel in selectors:
                submit_button = await page.query_selector(sel)
                if submit_button:
                    break
            if not submit_button:
                result.error_message = "Submit button not found"
                return result

            dialog_messages: list[str] = []

            def on_dialog(dialog: Any) -> None:
                dialog_messages.append(dialog.message)
                asyncio.ensure_future(dialog.accept())

            page.on("dialog", on_dialog)

            captured_code: Optional[str] = None

            async def on_response(response: Any) -> None:
                nonlocal captured_code
                if captured_code:
                    return
                url = response.url
                if "report/list" in url:
                    try:
                        body = await response.text()
                        data = json.loads(body)
                        if data.get("data"):
                            max_entry = max(
                                data["data"],
                                key=lambda x: int(x.get("ad_idx", 0)),
                            )
                            captured_code = str(max_entry["ad_idx"])
                    except Exception:
                        pass

            page.on("response", on_response)
            await submit_button.click()
            await page.wait_for_timeout(8000)
            page.remove_listener("dialog", on_dialog)
            page.remove_listener("response", on_response)

            current_url = page.url
            result.redirect_url = current_url

            if "/add" in current_url and "/report" not in current_url:
                if dialog_messages:
                    result.error_message = f"Registration failed: {dialog_messages[-1]}"
                else:
                    result.error_message = "Registration result unclear (still on form page)"
                return result

            if "/report" in current_url or "/list" in current_url:
                result.success = True
                if captured_code:
                    result.campaign_code = captured_code
                if campaign_name:
                    search_code = await self._search_campaign_code(
                        page, campaign_name
                    )
                    if search_code:
                        result.campaign_code = search_code
                return result

            result.success = True
            if captured_code:
                result.campaign_code = captured_code
            return result
        except SuperapCampaignError:
            raise
        except Exception as e:
            result.error_message = f"Campaign submit error: {str(e)}"
            return result

    async def _search_campaign_code(
        self, page: Page, campaign_name: str
    ) -> Optional[str]:
        """Search for a campaign by name on the report page."""
        try:
            api_data: list = []

            async def on_response(response: Any) -> None:
                if "report/list" in response.url:
                    try:
                        body = await response.text()
                        data = json.loads(body)
                        if data.get("data"):
                            api_data.extend(data["data"])
                    except Exception:
                        pass

            page.on("response", on_response)
            search_input = await page.query_selector(
                '#search_text, input[name="search_text"]'
            )
            if not search_input:
                page.remove_listener("response", on_response)
                return None
            await search_input.fill(campaign_name)
            await page.wait_for_timeout(300)
            search_btn = await page.query_selector(
                "button#btn_search, .btn-search"
            )
            if search_btn:
                await search_btn.click()
            else:
                await search_input.press("Enter")
            await page.wait_for_timeout(3000)
            page.remove_listener("response", on_response)
            if not api_data:
                return None
            max_entry = max(api_data, key=lambda x: int(x.get("ad_idx", 0)))
            return str(max_entry["ad_idx"])
        except Exception as e:
            logger.warning(f"Campaign code search failed: {e}")
            return None

    async def extract_campaign_code(
        self, account_id: str, campaign_name: Optional[str] = None
    ) -> str:
        """Extract the campaign code from the report page."""
        page = await self.get_page(account_id)
        try:
            current_url = page.url
            if "/report" not in current_url and "/list" not in current_url:
                await page.goto(
                    self.CAMPAIGN_LIST_URL,
                    wait_until="networkidle",
                    timeout=30000,
                )
                await self._human_like_delay(page)
            if campaign_name:
                code = await self._search_campaign_code(page, campaign_name)
                if code:
                    return code
            try:
                await page.wait_for_selector(
                    "table, .kt-datatable__table", timeout=10000
                )
            except Exception:
                pass
            max_code = await page.evaluate(
                """() => {
                let maxCode = 0;
                const cells = document.querySelectorAll('td[data-field="ad_idx"]');
                for (const cell of cells) {
                    const num = parseInt(cell.textContent.trim(), 10);
                    if (!isNaN(num) && num > maxCode) maxCode = num;
                }
                return maxCode > 0 ? String(maxCode) : null;
            }"""
            )
            if max_code:
                return str(max_code)
            raise SuperapCampaignError("Cannot extract campaign code")
        except SuperapCampaignError:
            raise
        except Exception as e:
            raise SuperapCampaignError(f"Campaign code extraction error: {str(e)}")

    # ============================================================
    # Campaign edit
    # ============================================================

    async def _search_on_report_page(
        self, page: Page, campaign_code: str
    ) -> bool:
        """Search for a campaign by code on the report page."""
        await page.goto(
            self.CAMPAIGN_LIST_URL, wait_until="networkidle", timeout=30000
        )
        await self._human_like_delay(page)
        search_input = await self._find_element(
            page,
            'input[type="search"], input[name="search"], input[name="keyword"], '
            'input[name="query"], input[placeholder*="검색"], input[placeholder*="번호"], '
            'input[placeholder*="캠페인"], #searchInput, .search-input',
        )
        if not search_input:
            return False
        await search_input.click()
        await search_input.fill("")
        await page.wait_for_timeout(200)
        await search_input.fill(campaign_code)
        search_btn = await self._find_element(
            page, 'button:has-text("검색"), button.btn-search'
        )
        if search_btn:
            await search_btn.click()
        else:
            await page.keyboard.press("Enter")
        await page.wait_for_timeout(2000)
        await self._human_like_delay(page)
        return True

    async def edit_campaign_keywords(
        self,
        account_id: str,
        campaign_code: str,
        new_keywords: str,
    ) -> bool:
        """Edit campaign keywords on superap.io.

        If DRY_RUN is enabled, skips actual edit and returns True.
        """
        from app.core.config import settings as worker_settings

        if worker_settings.DRY_RUN:
            logger.info(f"[DRY_RUN] edit_campaign_keywords skipped for campaign {campaign_code}")
            return True

        page = await self.get_page(account_id)
        try:
            if not await self._search_on_report_page(page, campaign_code):
                return False

            campaign_clicked = await page.evaluate(
                r"""(code) => {
                const rows = document.querySelectorAll('table tbody tr');
                for (const row of rows) {
                    if (row.textContent && row.textContent.includes(code)) {
                        const cells = row.querySelectorAll('td');
                        for (const cell of cells) {
                            const link = cell.querySelector('a');
                            if (link && link.textContent.trim().length > 0) {
                                const text = link.textContent.trim();
                                if (!/^\d+$/.test(text)) {
                                    link.click(); return 'name_link';
                                }
                            }
                        }
                        const anyLink = row.querySelector('a');
                        if (anyLink) { anyLink.click(); return 'any_link'; }
                        row.click(); return 'row';
                    }
                }
                return null;
            }""",
                campaign_code,
            )
            if not campaign_clicked:
                return False

            await page.wait_for_timeout(2000)
            await self._human_like_delay(page)

            edit_btn = await self._find_element(
                page,
                'a:has-text("수정"), button:has-text("수정"), '
                'a[href*="mode=modify"], a.btn-edit, button.btn-edit',
            )
            if not edit_btn:
                return False

            await edit_btn.click()
            await page.wait_for_timeout(2000)
            await self._human_like_delay(page)

            if not await self._fill_input_field(
                page, self.CAMPAIGN_SELECTORS["keywords"], new_keywords, "keywords"
            ):
                return False

            await self._human_like_delay(page)

            submit_btn = await self._find_element(
                page, self.CAMPAIGN_SELECTORS["submit_button"]
            )
            if not submit_btn:
                return False

            await submit_btn.click()
            await page.wait_for_timeout(3000)

            current_url = page.url
            if "/report" in current_url or "/list" in current_url:
                return True
            if "/add" in current_url:
                return False
            return True
        except Exception as e:
            logger.error(f"Campaign {campaign_code} keyword edit error: {e}")
            return False

    async def edit_campaign(
        self,
        account_id: str,
        campaign_code: str,
        new_total_limit: Optional[int] = None,
        new_daily_limit: Optional[int] = None,
        new_end_date: Optional[Union[date, datetime, str]] = None,
        new_keywords: Optional[str] = None,
    ) -> bool:
        """Edit an existing campaign (total limit, daily limit, end date, keywords).

        If DRY_RUN is enabled, skips actual edit and returns True.
        """
        from app.core.config import settings as worker_settings

        if worker_settings.DRY_RUN:
            logger.info(f"[DRY_RUN] edit_campaign skipped for campaign {campaign_code}")
            return True

        page = await self.get_page(account_id)
        try:
            if not await self._search_on_report_page(page, campaign_code):
                return False

            campaign_clicked = await page.evaluate(
                r"""(code) => {
                const rows = document.querySelectorAll('table tbody tr');
                for (const row of rows) {
                    if (row.textContent && row.textContent.includes(code)) {
                        const cells = row.querySelectorAll('td');
                        for (const cell of cells) {
                            const link = cell.querySelector('a');
                            if (link && link.textContent.trim().length > 0) {
                                const text = link.textContent.trim();
                                if (!/^\d+$/.test(text)) {
                                    link.click(); return 'name_link';
                                }
                            }
                        }
                        const anyLink = row.querySelector('a');
                        if (anyLink) { anyLink.click(); return 'any_link'; }
                        row.click(); return 'row';
                    }
                }
                return null;
            }""",
                campaign_code,
            )
            if not campaign_clicked:
                return False

            await page.wait_for_timeout(2000)
            await self._human_like_delay(page)

            edit_btn = await self._find_element(
                page,
                'a:has-text("수정"), button:has-text("수정"), '
                'a[href*="mode=modify"], a.btn-edit, button.btn-edit',
            )
            if not edit_btn:
                return False

            await edit_btn.click()
            await page.wait_for_timeout(3000)
            await self._human_like_delay(page)

            if new_total_limit is not None:
                if not await self._fill_autonumeric_field(
                    page,
                    self.CAMPAIGN_SELECTORS["total_budget"],
                    new_total_limit,
                ):
                    return False

            if new_daily_limit is not None:
                if not await self._fill_autonumeric_field(
                    page,
                    self.CAMPAIGN_SELECTORS["day_budget"],
                    new_daily_limit,
                ):
                    return False

            if new_keywords is not None:
                if not await self._fill_input_field(
                    page,
                    self.CAMPAIGN_SELECTORS["keywords"],
                    new_keywords,
                    "keywords",
                ):
                    return False

            if new_end_date is not None:
                if isinstance(new_end_date, (date, datetime)):
                    end_str = f"{new_end_date.strftime('%Y-%m-%d')} 23:59:59"
                else:
                    end_str = new_end_date.strip()
                    if len(end_str) == 10:
                        end_str = f"{end_str} 23:59:59"
                await page.evaluate(
                    """(dateStr) => {
                    var el = document.querySelector('input#end_date') ||
                             document.querySelector('input[name="end_date"]');
                    if (!el) return;
                    if (window.jQuery && window.moment) {
                        var $el = jQuery(el);
                        var picker = $el.data('daterangepicker');
                        if (picker) {
                            var m = moment(dateStr, 'YYYY-MM-DD HH:mm:ss');
                            if (m.isValid()) {
                                picker.setStartDate(m); picker.setEndDate(m);
                                if (typeof picker.callback === 'function')
                                    picker.callback(m, m, picker.chosenLabel);
                                el.value = dateStr;
                                $el.val(dateStr).trigger('change');
                                return;
                            }
                        }
                    }
                    el.removeAttribute('readonly');
                    el.value = dateStr;
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                }""",
                    end_str,
                )
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(300)

            await self._human_like_delay(page)

            submit_button = await self._find_element(
                page, self.CAMPAIGN_SELECTORS["submit_button"]
            )
            if not submit_button:
                return False

            await submit_button.click()
            await page.wait_for_timeout(3000)

            current_url = page.url
            if "/report" in current_url or "/list" in current_url:
                return True
            if "/add" in current_url:
                return False
            return True
        except Exception as e:
            logger.error(f"Campaign {campaign_code} edit error: {e}")
            return False

    # ============================================================
    # Campaign status queries
    # ============================================================

    async def get_campaign_status(
        self, account_id: str, campaign_code: str
    ) -> Optional[str]:
        """Get campaign status from superap.io report page."""
        page = await self.get_page(account_id)
        try:
            if not await self._search_on_report_page(page, campaign_code):
                return None
            status = await page.evaluate(
                r"""(campaignCode) => {
                const rows = document.querySelectorAll('table tbody tr, table tr');
                for (const row of rows) {
                    const cells = row.querySelectorAll('td');
                    if (cells.length < 9) continue;
                    const code = cells[0].textContent.trim();
                    if (code !== campaignCode && !row.textContent.includes(campaignCode))
                        continue;
                    const badge = cells[8].querySelector('.kt-badge');
                    if (badge) return badge.textContent.trim();
                    const cellText = cells[8].textContent.trim();
                    if (cellText) return cellText;
                }
                return null;
            }""",
                campaign_code,
            )
            return status
        except Exception:
            return None

    async def get_campaign_status_with_conversions(
        self, account_id: str, campaign_code: str
    ) -> Optional[dict]:
        """Get campaign status and conversion counts."""
        page = await self.get_page(account_id)
        try:
            if not await self._search_on_report_page(page, campaign_code):
                return None
            result = await page.evaluate(
                r"""(campaignCode) => {
                const rows = document.querySelectorAll('table tbody tr, table tr');
                for (const row of rows) {
                    const cells = row.querySelectorAll('td');
                    if (cells.length < 9) continue;
                    const code = cells[0].textContent.trim();
                    if (code !== campaignCode && !row.textContent.includes(campaignCode))
                        continue;
                    let status = null;
                    const badge = cells[8].querySelector('.kt-badge');
                    if (badge) status = badge.textContent.trim();
                    else {
                        const cellText = cells[8].textContent.trim();
                        if (cellText) status = cellText;
                    }
                    let currentCount = 0, totalCount = 0;
                    const convText = cells[7].textContent.trim();
                    const slashMatch = convText.match(/^([\d,]+)\s*\/\s*([\d,]+)$/);
                    if (slashMatch) {
                        currentCount = parseInt(slashMatch[1].replace(/,/g, ''), 10) || 0;
                        totalCount = parseInt(slashMatch[2].replace(/,/g, ''), 10) || 0;
                    }
                    return { status, current_count: currentCount, total_count: totalCount };
                }
                return null;
            }""",
                campaign_code,
            )
            return result
        except Exception:
            return None

"""superap.io 컨트롤러 모듈.

계정별 브라우저 컨텍스트 분리를 통한 다중 계정 관리 및 로그인 자동화.
캠페인 등록 폼 입력 자동화.
"""

import asyncio
import json
import logging
import os
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Union

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
)

logger = logging.getLogger(__name__)


# 프론트엔드 한국어 라벨 → superap.io 라디오 value 매핑
CAMPAIGN_TYPE_SELECTION_MAP: Dict[str, str] = {
    # 플레이스
    "기본 플레이스 저장하기": "place_save_default",
    "플레이스 URL 공유하기": "place_save_share",
    "컵페 클릭 후 저장": "place_save_click",
    "플레이스 방문 & 저장": "place_save_home",
    "keep 공유": "place_save_keep",
    "알림받기": "place_save_noti",
    "검색 후 정답 입력": "place_save_tab",
    "서치 커스텀 미션(스크린샷 제출 타입)": "place_save_search",
    # 퀴즈 맞추기
    "대표자명 맞추기": "cpc_detail_ceo_name",
    "상품 클릭 후 태그 단어 맞추기": "cpc_detail_click_tag",
    "상품 클릭 후 대표자명 맞추기": "cpc_detail_click_ceo_name",
    "플레이스 퀴즈": "cpc_detail_place",
    "서치 플레이스 퀴즈": "cpc_detail_place_quiz",
    # 상품클릭
    "기본 상품클릭": "pick_shop_default",
    "상품 클릭 후 상품평": "pick_shop_click",
    "무신사 상품 평하기": "pick_shop_musinsa_like",
    "카카오톡 선물하기 평하기": "pick_shop_kakao_like",
    # 알림받기
    "기본 알림받기": "receive_notification_default",
    "상품 클릭 후 알림받기": "receive_notification_click",
    # 유튜브
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
    """한국어 라벨 또는 radio value를 superap.io radio value로 변환."""
    if not campaign_type_selection:
        return None
    # 이미 radio value인 경우 (영문)
    if campaign_type_selection in CAMPAIGN_TYPE_SELECTION_MAP.values():
        return campaign_type_selection
    # 한국어 라벨 → radio value
    return CAMPAIGN_TYPE_SELECTION_MAP.get(campaign_type_selection)


@dataclass
class CampaignFormData:
    """캠페인 등록 폼 데이터."""

    campaign_name: str
    place_name: str
    landmark_name: str
    participation_guide: str
    keywords: List[str]
    hint: str
    walking_steps: int = 0

    # 텍스트 기반 전환 인식 기준 (걸음수 대신 사용)
    conversion_text: Optional[str] = None

    # 날짜 설정
    start_date: Optional[Union[date, datetime, str]] = None
    end_date: Optional[Union[date, datetime, str]] = None

    # 예산 설정
    daily_limit: int = 300
    total_limit: Optional[int] = None  # None이면 자동 계산 (일일한도 * 일수)

    # 링크 목록 (최대 3개)
    links: List[str] = field(default_factory=list)

    # 캠페인 타입: 'traffic' (트래픽/명소), 'save' (저장하기)
    campaign_type: str = "traffic"

    _processed_guide: str = field(default="", init=False, repr=False)
    _processed_keywords: str = field(default="", init=False, repr=False)

    def __post_init__(self):
        self._process_templates()
        self._process_keywords()
        self._calculate_total_limit()

    def _process_templates(self):
        guide = self.participation_guide
        # 상호명 마스킹: 2글자마다 X로 교체
        masked_place_name = self._mask_place_name(self.place_name)
        guide = guide.replace("&상호명&", masked_place_name)
        guide = guide.replace("&명소명&", self.landmark_name)
        self._processed_guide = guide

    def _mask_place_name(self, name: str) -> str:
        """상호명 2글자마다 X로 마스킹.

        예: "일류곱창 마포공덕본점" → "일X곱X 마X공X본X"
        """
        if not name:
            return name
        result = []
        char_count = 0
        for char in name:
            if char == ' ':
                result.append(char)
            else:
                char_count += 1
                if char_count % 2 == 0:
                    result.append('X')
                else:
                    result.append(char)
        return ''.join(result)

    def _process_keywords(self):
        import random

        if not self.keywords:
            self._processed_keywords = ""
            return
        # 키워드를 랜덤 순서로 섞어서 255자 이내로 채움
        cleaned = [kw.strip() for kw in self.keywords if kw.strip()]
        random.shuffle(cleaned)
        result = []
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

    def _calculate_total_limit(self):
        """전체 한도 계산 (일일한도 * 일수)."""
        if self.total_limit is not None:
            return
        if self.start_date and self.end_date:
            start = self._normalize_date(self.start_date)
            end = self._normalize_date(self.end_date)
            days = (end - start).days + 1
            self.total_limit = days * self.daily_limit

    def _normalize_date(self, d: Union[date, datetime, str]) -> date:
        """날짜를 date 객체로 변환."""
        if isinstance(d, datetime):
            return d.date()
        if isinstance(d, date):
            return d
        if isinstance(d, str):
            return datetime.strptime(d, "%Y-%m-%d").date()
        return d

    def get_start_date_str(self) -> str:
        """시작일 문자열 (YYYY-MM-DD 00:00:00)."""
        if not self.start_date:
            return ""
        d = self._normalize_date(self.start_date)
        return f"{d.strftime('%Y-%m-%d')} 00:00:00"

    def get_end_date_str(self) -> str:
        """종료일 문자열 (YYYY-MM-DD 23:59:59)."""
        if not self.end_date:
            return ""
        d = self._normalize_date(self.end_date)
        return f"{d.strftime('%Y-%m-%d')} 23:59:59"

    def generate_campaign_name(self) -> str:
        """캠페인 이름 자동 생성.

        규칙:
        - 트래픽 타입: "XX 퀴즈 맞추기" (상호명 앞 2글자)
        - 저장하기 타입: "XX 저장 퀴즈 맞추기"
        - 상호명 1-2글자면 1글자만 사용
        """
        # 공백 제외한 상호명에서 앞글자 추출
        name_chars = [c for c in self.place_name if c != ' ']
        if len(name_chars) <= 2:
            prefix = name_chars[0] if name_chars else ""
        else:
            prefix = ''.join(name_chars[:2])

        if self.campaign_type == "save":
            return f"{prefix} 저장 퀴즈 맞추기"
        else:
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
    """캠페인 폼 입력 결과."""
    success: bool
    screenshot_path: Optional[str] = None
    filled_fields: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class SubmitResult:
    """캠페인 제출 결과."""
    success: bool
    campaign_code: Optional[str] = None  # POST 응답에서 캡처된 캠페인 코드
    error_message: Optional[str] = None
    redirect_url: Optional[str] = None


class SuperapError(Exception):
    pass


class SuperapLoginError(SuperapError):
    pass


class SuperapCampaignError(SuperapError):
    pass


class StealthConfig:
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
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


class SuperapController:
    """superap.io 컨트롤러."""

    BASE_URL = "https://superap.io"
    LOGIN_URL = "https://superap.io"
    DASHBOARD_URL = "https://superap.io/service/reward/adver/report"
    CAMPAIGN_CREATE_URL = "https://superap.io/service/reward/adver/add?mode=add"
    CAMPAIGN_EDIT_URL = "https://superap.io/service/reward/adver/add?mode=modify&id={campaign_code}"
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
        # 기본 폼 필드
        "campaign_name": 'input[name="ad_title"]',
        "participation_guide": 'textarea[name="description"]',
        "keywords": 'input[name="search_keyword"]',  # input 필드 (textarea 아님, 255자 제한)
        "hint": 'input[name="target_package"], input#inp_product_name',  # input 필드!

        # 예산 설정 (autoNumeric 클래스 사용)
        "total_budget": 'input#total_budget, input[name="total_budget"]',
        "day_budget": 'input#day_budget, input[name="day_budget"]',

        # 날짜 설정
        "begin_date": 'input#begin_date, input[name="begin_date"]',
        "end_date": 'input#end_date, input[name="end_date"]',
        "date_add_7": 'button.btn-date-add[data-days="7"]',
        "date_add_15": 'button.btn-date-add[data-days="15"]',
        "date_add_30": 'button.btn-date-add[data-days="30"]',

        # 전환 인식 기준 (걸음수) - visible input으로 입력
        "conversion_input": 'input.ad_event_name-input',
        "conversion_hidden": 'input#ad_event_name, input[name="ad_event_name"]',
        "conversion_add_btn": 'button.btn-add-event',

        # 링크 추가
        "link_add_btn": 'button.btn-add-url',
        "link_inputs": 'input[name^="url_"], input.url-input',

        # 캠페인 타입 라디오 버튼
        # 트래픽 타입 = '플레이스 퀴즈' (cpc_detail_place)
        "campaign_type_traffic": 'input[name="rdo_cpa_type"][value="cpc_detail_place"]',
        # 저장하기 타입 = '검색 후 정답 입력' (place_save_search)
        "campaign_type_save": 'input[name="rdo_cpa_type"][value="place_save_search"]',

        # 제출 버튼
        "submit_button": 'button:has-text("수정"), button:has-text("등록"), input[type="submit"], button.btn-submit',
        "form_container": 'form',

        # 캠페인 목록 관련 (등록 후 캠페인 코드 추출용)
        "campaign_table": 'table.table, .campaign-list, #campaign-table',
        "campaign_row": 'table.table tbody tr, .campaign-item',
        "campaign_code_cell": 'td:first-child, .campaign-code',
        "success_message": '.success, .alert-success, [class*="success"]',
        "error_alert": '.alert-danger, .error-message, [class*="error"]',
    }

    SCREENSHOT_DIR = "screenshots/campaigns"

    def __init__(self, headless: bool = True, stealth: bool = True):
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

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
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
        if login_form is None:
            return True
        return False

    async def check_login_status(self, account_id: str) -> bool:
        if account_id in self._pages:
            page = self._pages[account_id]
            return await self.is_logged_in(page)
        return False

    async def login(
        self,
        account_id: str,
        username: str,
        password: str,
        force: bool = False,
    ) -> bool:
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
                await page.wait_for_selector(self.SELECTORS["login_form"], timeout=10000)
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
            error_element = await page.query_selector(self.SELECTORS["error_message"])
            if error_element:
                error_text = await error_element.inner_text()
                await page.close()
                raise SuperapLoginError(f"로그인 실패: {error_text}")
            await page.close()
            raise SuperapLoginError("로그인 실패: 알 수 없는 오류")
        except SuperapLoginError:
            raise
        except Exception as e:
            await page.close()
            raise SuperapLoginError(f"로그인 중 오류 발생: {str(e)}")

    async def get_page(self, account_id: str) -> Page:
        if account_id in self._pages:
            page = self._pages[account_id]
            if await self.is_logged_in(page):
                return page
            await page.close()
            del self._pages[account_id]
        raise SuperapError(f"계정 {account_id}이(가) 로그인 상태가 아닙니다. login()을 먼저 호출하세요.")

    def get_active_accounts(self) -> list:
        return list(self._contexts.keys())

    def get_context_count(self) -> int:
        return len(self._contexts)

    async def _navigate_to_campaign_form(self, page: Page) -> bool:
        try:
            await page.goto(self.CAMPAIGN_CREATE_URL, wait_until="networkidle", timeout=30000)
            await self._human_like_delay(page)
            # URL 검증: /service/reward/adver/add 또는 /campaign
            url_lower = page.url.lower()
            if "/adver/add" in url_lower or "/campaign" in url_lower:
                return True
            return False
        except Exception:
            return False

    async def _fill_input_field(
        self,
        page: Page,
        selector: str,
        value: str,
        field_name: str,
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

    async def _set_campaign_dates(
        self,
        page: Page,
        form_data: "CampaignFormData",
    ) -> tuple[bool, bool]:
        """캠페인 날짜 설정 (daterangepicker singleDatePicker + timePicker 지원).

        Returns:
            tuple[bool, bool]: (시작일 설정 성공, 종료일 설정 성공)
        """
        start_success = False
        end_success = False

        try:
            # 시작일 설정
            start_date_str = form_data.get_start_date_str()
            if start_date_str:
                result = await page.evaluate("""(args) => {
                    var dateStr = args.dateStr;
                    var selector = args.selector;
                    var el = document.querySelector(selector.split(', ')[0]) ||
                             document.querySelector(selector.split(', ')[1]);
                    if (!el) return false;

                    if (window.jQuery && window.moment) {
                        var $el = jQuery(el);
                        var picker = $el.data('daterangepicker');
                        if (picker) {
                            var m = moment(dateStr, 'YYYY-MM-DD HH:mm:ss');
                            if (m.isValid()) {
                                picker.setStartDate(m);
                                picker.setEndDate(m);
                                if (typeof picker.callback === 'function') {
                                    picker.callback(m, m, picker.chosenLabel);
                                }
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
                }""", {"dateStr": start_date_str, "selector": "input#begin_date, input[name=\"begin_date\"]"})
                start_success = bool(result)

            # 종료일 설정
            end_date_str = form_data.get_end_date_str()
            if end_date_str:
                result = await page.evaluate("""(args) => {
                    var dateStr = args.dateStr;
                    var selector = args.selector;
                    var el = document.querySelector(selector.split(', ')[0]) ||
                             document.querySelector(selector.split(', ')[1]);
                    if (!el) return false;

                    if (window.jQuery && window.moment) {
                        var $el = jQuery(el);
                        var picker = $el.data('daterangepicker');
                        if (picker) {
                            var m = moment(dateStr, 'YYYY-MM-DD HH:mm:ss');
                            if (m.isValid()) {
                                picker.setStartDate(m);
                                picker.setEndDate(m);
                                if (typeof picker.callback === 'function') {
                                    picker.callback(m, m, picker.chosenLabel);
                                }
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
                }""", {"dateStr": end_date_str, "selector": "input#end_date, input[name=\"end_date\"]"})
                end_success = bool(result)

            await self._human_like_delay(page)
        except Exception:
            pass

        return start_success, end_success

    async def _add_campaign_links(
        self,
        page: Page,
        links: List[str],
    ) -> int:
        """캠페인 링크 추가 (최대 3개).

        1. 먼저 필요한 개수만큼 + 버튼 클릭하여 슬롯 생성
        2. 그 다음 각 슬롯에 링크 입력
        3. URL에 #detail_type 해시가 없으면 자동 추가 (validation 통과 필수)

        Returns:
            int: 성공적으로 추가된 링크 수
        """
        if not links:
            return 0

        max_links = min(len(links), 3)
        added_count = 0

        try:
            # detail_type 값 가져오기 (URL validation에 필요)
            detail_type = await page.evaluate(
                "document.getElementById('detail_type') ? document.getElementById('detail_type').value : ''"
            )

            # 1단계: 슬롯 먼저 생성 (첫 번째 슬롯은 이미 있으므로 max_links-1번 클릭)
            for i in range(max_links - 1):
                add_btn = await self._find_element(page, self.CAMPAIGN_SELECTORS["link_add_btn"])
                if add_btn:
                    await add_btn.click()
                    await page.wait_for_timeout(300)

            await page.wait_for_timeout(500)

            # 2단계: 링크 입력 필드 찾아서 채우기
            link_inputs = await page.query_selector_all('input.url-input, input[name^="url_"]')
            for i in range(min(len(link_inputs), max_links)):
                if i < len(links):
                    url = links[i]
                    # URL에 #detail_type 해시 추가 (superap validation 필수 조건)
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
        self,
        page: Page,
        walking_steps: int,
    ) -> bool:
        """전환 인식 기준 (걸음수) 설정.

        Returns:
            bool: 설정 성공 여부
        """
        try:
            # 스크롤 다운 (전환 인식 기준 필드가 하단에 있음)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(500)

            # 걸음수 입력 필드 찾기 (visible input)
            conversion_input = await self._find_element(page, self.CAMPAIGN_SELECTORS["conversion_input"])
            if conversion_input:
                await conversion_input.click()
                await conversion_input.fill(str(walking_steps))
                await self._human_like_delay(page)
                return True

            return False
        except Exception:
            return False

    async def _set_conversion_text(
        self,
        page: Page,
        text: str,
    ) -> bool:
        """전환 인식 기준 (텍스트) 설정.

        걸음수 대신 텍스트를 입력합니다. (예: "마포역 ㄱㄱ")

        Returns:
            bool: 설정 성공 여부
        """
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(500)

            conversion_input = await self._find_element(page, self.CAMPAIGN_SELECTORS["conversion_input"])
            if conversion_input:
                await conversion_input.click()
                await conversion_input.fill(text)
                await self._human_like_delay(page)
                return True

            return False
        except Exception:
            return False

    async def _set_campaign_type(
        self,
        page: Page,
        campaign_type: str,
    ) -> bool:
        """캠페인 타입 설정.

        Args:
            campaign_type: 한국어 라벨('플레이스 퀴즈'), radio value('cpc_detail_place'),
                          또는 레거시 값('traffic', 'save')

        Returns:
            bool: 설정 성공 여부
        """
        try:
            # 레거시 호환: 'traffic' → 'cpc_detail_place', 'save' → 'place_save_tab'
            legacy_map = {"traffic": "cpc_detail_place", "save": "place_save_tab"}
            radio_value = legacy_map.get(campaign_type)

            if not radio_value:
                # 한국어 라벨 또는 radio value 직접 변환
                radio_value = resolve_campaign_type_value(campaign_type)

            if not radio_value:
                logger.warning(f"알 수 없는 캠페인 타입: {campaign_type}")
                return False

            selector = f'input[name="rdo_cpa_type"][value="{radio_value}"]'
            radio = await page.query_selector(selector)
            if radio:
                await radio.click()
                await self._human_like_delay(page)
                return True

            logger.warning(f"캠페인 타입 라디오 버튼을 찾을 수 없음: {selector}")
            return False
        except Exception:
            return False

    async def _find_element(self, page: Page, selector: str):
        """여러 셀렉터 중 첫 번째로 찾은 요소 반환."""
        selectors = [s.strip() for s in selector.split(",")]
        for sel in selectors:
            element = await page.query_selector(sel)
            if element:
                return element
        return None

    async def _fill_autonumeric_field(
        self,
        page: Page,
        selector: str,
        value: int,
    ) -> bool:
        """autoNumeric 필드 입력 (JS로 직접 값 설정).

        autoNumeric 플러그인은 일반 fill()로 입력 시 포맷팅 문제가 발생할 수 있음.
        """
        try:
            result = await page.evaluate("""({selector, value}) => {
                const selectors = selector.split(',').map(s => s.trim());
                let el = null;
                for (const sel of selectors) {
                    el = document.querySelector(sel);
                    if (el) break;
                }
                if (!el) return false;

                // autoNumeric 인스턴스가 있으면 사용, 없으면 직접 값 설정
                if (window.AutoNumeric && AutoNumeric.getAutoNumericElement(el)) {
                    AutoNumeric.getAutoNumericElement(el).set(value);
                } else {
                    el.value = value;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }
                return true;
            }""", {"selector": selector, "value": value})
            return bool(result)
        except Exception:
            return False

    async def _save_screenshot(
        self,
        page: Page,
        prefix: str = "campaign_form",
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

    async def fill_campaign_form(
        self,
        account_id: str,
        form_data: CampaignFormData,
        take_screenshot: bool = True,
    ) -> CampaignFormResult:
        result = CampaignFormResult(success=False)
        page = await self.get_page(account_id)
        try:
            if not await self._navigate_to_campaign_form(page):
                result.errors.append("캠페인 등록 페이지로 이동 실패")
                return result

            # 1. 캠페인 타입 먼저 선택 (오른쪽 퀴즈 맞추기 > 플레이스 퀴즈)
            if await self._set_campaign_type(page, form_data.campaign_type):
                result.filled_fields.append("campaign_type")
            else:
                result.errors.append("캠페인 타입 설정 실패")

            await page.wait_for_timeout(500)

            # 2. 캠페인 이름 (상호명 앞 2글자 + " 퀴즈 맞추기")
            if await self._fill_input_field(page, self.CAMPAIGN_SELECTORS["campaign_name"], form_data.campaign_name, "campaign_name"):
                result.filled_fields.append("campaign_name")
            else:
                result.errors.append("캠페인 이름 입력 실패")

            # 3. 참여 방법 설명 (상호명 마스킹 적용됨)
            if await self._fill_input_field(page, self.CAMPAIGN_SELECTORS["participation_guide"], form_data.processed_guide, "participation_guide"):
                result.filled_fields.append("participation_guide")
            else:
                result.errors.append("참여 방법 설명 입력 실패")

            # 4. 검색 키워드 (255자 제한)
            if await self._fill_input_field(page, self.CAMPAIGN_SELECTORS["keywords"], form_data.processed_keywords, "keywords"):
                result.filled_fields.append("keywords")
            else:
                result.errors.append("검색 키워드 입력 실패")

            # 5. 힌트
            if await self._fill_input_field(page, self.CAMPAIGN_SELECTORS["hint"], form_data.hint, "hint"):
                result.filled_fields.append("hint")
            else:
                result.errors.append("힌트 입력 실패")

            # 스크롤 다운 (하단 필드 접근)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            await page.wait_for_timeout(500)

            # 6. 전체 한도 (autoNumeric 필드)
            if form_data.total_limit:
                if await self._fill_autonumeric_field(page, self.CAMPAIGN_SELECTORS["total_budget"], form_data.total_limit):
                    result.filled_fields.append("total_budget")
                else:
                    result.errors.append("전체 한도 입력 실패")

            # 7. 일일 한도 (autoNumeric 필드)
            if await self._fill_autonumeric_field(page, self.CAMPAIGN_SELECTORS["day_budget"], form_data.daily_limit):
                result.filled_fields.append("day_budget")
            else:
                result.errors.append("일일 한도 입력 실패")

            # 8. 날짜 설정
            start_ok, end_ok = await self._set_campaign_dates(page, form_data)
            if start_ok:
                result.filled_fields.append("start_date")
            else:
                result.errors.append("시작일 설정 실패")
            if end_ok:
                result.filled_fields.append("end_date")
            else:
                result.errors.append("종료일 설정 실패")

            # 9. 링크 추가
            if form_data.links:
                links_added = await self._add_campaign_links(page, form_data.links)
                if links_added > 0:
                    result.filled_fields.append(f"links({links_added})")
                else:
                    result.errors.append("링크 추가 실패")

            # 10. 전환 인식 기준 (텍스트 또는 걸음수)
            if form_data.conversion_text:
                if await self._set_conversion_text(page, form_data.conversion_text):
                    result.filled_fields.append("conversion_text")
                else:
                    result.errors.append("전환 인식 기준(텍스트) 입력 실패")
            elif form_data.walking_steps:
                if await self._set_conversion_criteria(page, form_data.walking_steps):
                    result.filled_fields.append("walking_steps")
                else:
                    result.errors.append("전환 인식 기준 입력 실패")

            # 스크린샷 저장
            if take_screenshot:
                screenshot_path = await self._save_screenshot(page)
                if screenshot_path:
                    result.screenshot_path = screenshot_path

            # 최소 5개 필드 입력 시 성공
            if len(result.filled_fields) >= 5:
                result.success = True
            else:
                result.errors.append(f"입력된 필드 수 부족: {len(result.filled_fields)}/10")

            return result
        except SuperapError:
            raise
        except Exception as e:
            result.errors.append(f"폼 입력 중 오류: {str(e)}")
            return result

    async def submit_campaign(
        self, account_id: str, campaign_name: Optional[str] = None,
    ) -> "SubmitResult":
        """캠페인 등록 버튼 클릭 및 결과 확인.

        제출 성공 시 report 페이지로 리다이렉트되므로, report/list API에서
        캠페인 이름으로 검색하여 방금 생성된 캠페인 코드를 캡처합니다.

        Args:
            account_id: 계정 식별자
            campaign_name: 캠페인 이름 (report 페이지에서 코드 검색용)

        Returns:
            SubmitResult: 제출 결과 (success, campaign_code, error_message, redirect_url)
        """
        page = await self.get_page(account_id)
        result = SubmitResult(success=False)

        try:
            # 등록 버튼 찾기
            selectors = [s.strip() for s in self.CAMPAIGN_SELECTORS["submit_button"].split(",")]
            submit_button = None
            for sel in selectors:
                submit_button = await page.query_selector(sel)
                if submit_button:
                    break

            if not submit_button:
                result.error_message = "등록 버튼을 찾을 수 없습니다"
                return result

            # dialog(alert) 캡처 — validation 에러 감지용
            dialog_messages = []

            def on_dialog(dialog):
                dialog_messages.append(dialog.message)
                asyncio.ensure_future(dialog.accept())

            page.on("dialog", on_dialog)

            # report/list API 응답에서 캠페인 코드 캡처
            captured_code = None

            async def on_response(response):
                nonlocal captured_code
                if captured_code:
                    return
                url = response.url
                # report/list API 응답에서 가장 높은 ad_idx 추출
                if "report/list" in url:
                    try:
                        body = await response.text()
                        data = json.loads(body)
                        if data.get("data"):
                            # 가장 큰 ad_idx = 가장 최근 생성된 캠페인
                            max_entry = max(
                                data["data"],
                                key=lambda x: int(x.get("ad_idx", 0)),
                            )
                            captured_code = str(max_entry["ad_idx"])
                    except Exception:
                        pass

            page.on("response", on_response)

            # 등록 버튼 클릭
            await submit_button.click()

            # 결과 대기 (리다이렉트 + report/list API 로드)
            await page.wait_for_timeout(8000)

            # 리스너 제거
            page.remove_listener("dialog", on_dialog)
            page.remove_listener("response", on_response)

            # 결과 확인
            current_url = page.url
            result.redirect_url = current_url

            # validation 에러 확인 (폼 페이지에 남아 있으면 실패)
            if "/add" in current_url and "/report" not in current_url:
                if dialog_messages:
                    result.error_message = f"등록 실패: {dialog_messages[-1]}"
                else:
                    result.error_message = "등록 결과를 확인할 수 없습니다 (폼 페이지에 남아 있음)"
                return result

            # report 페이지로 리다이렉트되면 성공
            if "/report" in current_url or "/list" in current_url:
                result.success = True

                # report/list API에서 캡처된 코드 사용
                if captured_code:
                    result.campaign_code = captured_code

                # 캠페인 이름으로 검색하여 정확한 코드 확인
                if campaign_name:
                    search_code = await self._search_campaign_code(
                        page, campaign_name,
                    )
                    if search_code:
                        result.campaign_code = search_code

                return result

            # 그 외 URL 변경도 성공으로 간주
            result.success = True
            if captured_code:
                result.campaign_code = captured_code
            return result

        except SuperapCampaignError:
            raise
        except Exception as e:
            result.error_message = f"캠페인 제출 중 오류: {str(e)}"
            return result

    async def _search_campaign_code(
        self, page: Page, campaign_name: str,
    ) -> Optional[str]:
        """report 페이지에서 캠페인 이름으로 검색하여 가장 최근 ad_idx 반환.

        report/list API 응답을 인터셉트하여 구조화된 JSON에서 추출합니다.

        Args:
            page: report 페이지
            campaign_name: 검색할 캠페인 이름

        Returns:
            캠페인 코드 문자열 또는 None
        """
        try:
            # report/list API 응답 인터셉트 준비
            api_data = []

            async def on_response(response):
                if "report/list" in response.url:
                    try:
                        body = await response.text()
                        data = json.loads(body)
                        if data.get("data"):
                            api_data.extend(data["data"])
                    except Exception:
                        pass

            page.on("response", on_response)

            # 검색어 입력
            search_input = await page.query_selector(
                '#search_text, input[name="search_text"]'
            )
            if not search_input:
                page.remove_listener("response", on_response)
                return None

            await search_input.fill(campaign_name)
            await page.wait_for_timeout(300)

            # 검색 실행
            search_btn = await page.query_selector('button#btn_search, .btn-search')
            if search_btn:
                await search_btn.click()
            else:
                await search_input.press("Enter")

            # API 응답 대기
            await page.wait_for_timeout(3000)
            page.remove_listener("response", on_response)

            if not api_data:
                return None

            # 가장 높은 ad_idx (= 가장 최근 생성) 반환
            max_entry = max(api_data, key=lambda x: int(x.get("ad_idx", 0)))
            return str(max_entry["ad_idx"])

        except Exception as e:
            logger.warning(f"캠페인 코드 검색 실패: {e}")
            return None

    async def extract_campaign_code(
        self, account_id: str, campaign_name: Optional[str] = None,
    ) -> str:
        """방금 등록한 캠페인의 캠페인 코드(번호) 추출.

        report 페이지에서 캠페인 이름으로 검색하거나, 검색 불가시
        현재 페이지의 datatable에서 최대 ad_idx를 찾습니다.

        Args:
            account_id: 계정 식별자
            campaign_name: 방금 생성한 캠페인 이름 (검색용)

        Returns:
            캠페인 코드 (문자열)

        Raises:
            SuperapCampaignError: 캠페인 코드를 찾을 수 없는 경우
        """
        page = await self.get_page(account_id)

        try:
            # 현재 URL이 목록 페이지가 아니면 이동
            current_url = page.url
            if "/report" not in current_url and "/list" not in current_url:
                await page.goto(self.CAMPAIGN_LIST_URL, wait_until="networkidle", timeout=30000)
                await self._human_like_delay(page)

            # 방법 1: 캠페인 이름으로 검색 → 가장 높은 ad_idx
            if campaign_name:
                code = await self._search_campaign_code(page, campaign_name)
                if code:
                    return code

            # 방법 2 (폴백): datatable에서 최대 ad_idx 추출
            try:
                await page.wait_for_selector(
                    "table, .kt-datatable__table", timeout=10000,
                )
            except Exception:
                pass

            max_code = await page.evaluate("""() => {
                let maxCode = 0;
                const cells = document.querySelectorAll('td[data-field="ad_idx"]');
                for (const cell of cells) {
                    const num = parseInt(cell.textContent.trim(), 10);
                    if (!isNaN(num) && num > maxCode) maxCode = num;
                }
                return maxCode > 0 ? String(maxCode) : null;
            }""")

            if max_code:
                return str(max_code)

            raise SuperapCampaignError("캠페인 코드를 추출할 수 없습니다")

        except SuperapCampaignError:
            raise
        except Exception as e:
            raise SuperapCampaignError(f"캠페인 코드 추출 중 오류: {str(e)}")

    async def edit_campaign(
        self,
        account_id: str,
        campaign_code: str,
        new_total_limit: Optional[int] = None,
        new_daily_limit: Optional[int] = None,
        new_end_date: Optional[Union[date, datetime, str]] = None,
        new_keywords: Optional[str] = None,
    ) -> bool:
        """기존 캠페인 수정 (총 타수, 일 타수, 만료일, 키워드).

        리포트 페이지에서 캠페인 검색 → 캠페인 클릭 → 수정 버튼 →
        수정 페이지(기존 값 로드된 상태)에서 값 변경 → 등록.

        Args:
            account_id: 계정 식별자
            campaign_code: 수정할 캠페인 코드
            new_total_limit: 새 총 타수 (None이면 변경하지 않음)
            new_daily_limit: 새 일 타수 (None이면 변경하지 않음)
            new_end_date: 새 만료일 (None이면 변경하지 않음)
            new_keywords: 새 키워드 (콤마 구분, None이면 변경하지 않음)

        Returns:
            수정 성공 여부
        """
        page = await self.get_page(account_id)

        try:
            # 1. 리포트 페이지에서 캠페인 검색
            logger.info(f"[캠페인수정] 캠페인 {campaign_code}: 리포트에서 검색")
            if not await self._search_on_report_page(page, campaign_code):
                logger.warning("[캠페인수정] 검색 입력란을 찾을 수 없음")
                return False

            # 2. 검색 결과에서 캠페인 이름 클릭
            campaign_clicked = await page.evaluate("""(code) => {
                const rows = document.querySelectorAll('table tbody tr');
                for (const row of rows) {
                    if (row.textContent && row.textContent.includes(code)) {
                        const cells = row.querySelectorAll('td');
                        for (const cell of cells) {
                            const link = cell.querySelector('a');
                            if (link && link.textContent.trim().length > 0) {
                                const text = link.textContent.trim();
                                if (!/^\\d+$/.test(text)) {
                                    link.click();
                                    return 'name_link: ' + text;
                                }
                            }
                        }
                        const anyLink = row.querySelector('a');
                        if (anyLink) { anyLink.click(); return 'any_link'; }
                        row.click();
                        return 'row';
                    }
                }
                return null;
            }""", campaign_code)

            if not campaign_clicked:
                logger.warning(f"[캠페인수정] 검색 결과에서 캠페인 {campaign_code}을 찾을 수 없음")
                return False

            logger.info(f"[캠페인수정] 캠페인 클릭 ({campaign_clicked})")
            await page.wait_for_timeout(2000)
            await self._human_like_delay(page)

            # 3. 수정 버튼 클릭 → 기존 값이 채워진 수정 페이지로 이동
            edit_btn = await self._find_element(
                page,
                'a:has-text("수정"), button:has-text("수정"), '
                'a[href*="mode=modify"], a.btn-edit, button.btn-edit'
            )
            if not edit_btn:
                logger.warning("[캠페인수정] 수정 버튼을 찾을 수 없음")
                await self._save_screenshot(page, f"edit_no_btn_{campaign_code}")
                return False

            await edit_btn.click()
            logger.info("[캠페인수정] 수정 버튼 클릭, 수정 페이지 대기")
            await page.wait_for_timeout(3000)
            await self._human_like_delay(page)

            # 4. 수정 페이지 검증 - 기존 값이 로드되었는지 확인
            field_check = await page.evaluate("""() => {
                const total = document.querySelector('input#total_budget, input[name="total_budget"]');
                const day = document.querySelector('input#day_budget, input[name="day_budget"]');
                return {
                    total_value: total ? total.value : 'NOT_FOUND',
                    day_value: day ? day.value : 'NOT_FOUND',
                    url: window.location.href,
                };
            }""")
            logger.info(
                f"[캠페인수정] 수정 페이지 현재값: "
                f"total={field_check.get('total_value')}, "
                f"day={field_check.get('day_value')}, "
                f"url={field_check.get('url')}"
            )

            # 5. 총 타수 수정
            if new_total_limit is not None:
                if not await self._fill_autonumeric_field(
                    page, self.CAMPAIGN_SELECTORS["total_budget"], new_total_limit
                ):
                    logger.warning(f"[캠페인수정] 총 타수 입력 실패: {new_total_limit}")
                    return False
                logger.info(f"[캠페인수정] 총 타수 설정: {new_total_limit}")

            # 6. 일 타수 수정
            if new_daily_limit is not None:
                if not await self._fill_autonumeric_field(
                    page, self.CAMPAIGN_SELECTORS["day_budget"], new_daily_limit
                ):
                    logger.warning(f"[캠페인수정] 일 타수 입력 실패: {new_daily_limit}")
                    return False
                logger.info(f"[캠페인수정] 일 타수 설정: {new_daily_limit}")

            # 7. 키워드 수정
            if new_keywords is not None:
                if not await self._fill_input_field(
                    page, self.CAMPAIGN_SELECTORS["keywords"], new_keywords, "keywords"
                ):
                    logger.warning("[캠페인수정] 키워드 입력 실패")
                    return False
                logger.info(f"[캠페인수정] 키워드 설정: {new_keywords[:50]}...")

            # 8. 만료일 수정
            if new_end_date is not None:
                if isinstance(new_end_date, (date, datetime)):
                    end_str = f"{new_end_date.strftime('%Y-%m-%d')} 23:59:59"
                else:
                    end_str = new_end_date.strip()
                    if len(end_str) == 10:
                        end_str = f"{end_str} 23:59:59"

                # daterangepicker(singleDatePicker + timePicker)를 통한 날짜 설정
                date_result = await page.evaluate("""(dateStr) => {
                    var el = document.querySelector('input#end_date') ||
                             document.querySelector('input[name="end_date"]');
                    if (!el) return {success: false, error: 'end_date 필드 없음'};

                    var result = {before: el.value};

                    if (window.jQuery && window.moment) {
                        var $el = jQuery(el);
                        var picker = $el.data('daterangepicker');
                        if (picker) {
                            var m = moment(dateStr, 'YYYY-MM-DD HH:mm:ss');
                            if (m.isValid()) {
                                // singleDatePicker: startDate = endDate = 같은 값
                                picker.setStartDate(m);
                                picker.setEndDate(m);
                                // picker 내부 콜백 실행 → input 값 자동 갱신
                                if (typeof picker.callback === 'function') {
                                    picker.callback(m, m, picker.chosenLabel);
                                }
                                // input 값 직접 설정 (콜백이 안 먹힐 경우 보완)
                                el.value = dateStr;
                                $el.val(dateStr);
                                $el.trigger('change');
                                result.method = 'daterangepicker';
                                result.after = el.value;
                                result.pickerStart = picker.startDate.format('YYYY-MM-DD HH:mm:ss');
                                result.pickerEnd = picker.endDate.format('YYYY-MM-DD HH:mm:ss');
                                result.success = true;
                                return result;
                            }
                        }
                    }

                    // fallback: 직접 값 설정
                    el.removeAttribute('readonly');
                    el.value = dateStr;
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                    result.method = 'direct';
                    result.after = el.value;
                    result.success = true;
                    return result;
                }""", end_str)

                logger.info(f"[캠페인수정] 만료일 설정 결과: {date_result}")

                if not date_result.get("success"):
                    logger.warning(f"[캠페인수정] 만료일 입력 실패: {date_result}")
                    return False

                # ESC로 열려있을 수 있는 datepicker 닫기
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(300)

                # 실제 값 검증
                final_val = await page.evaluate("""() => {
                    var el = document.querySelector('input#end_date') ||
                             document.querySelector('input[name="end_date"]');
                    return el ? el.value : null;
                }""")
                logger.info(f"[캠페인수정] 만료일 최종 값: {final_val} (목표: {end_str})")

            await self._human_like_delay(page)

            # 9. 수정 전 스크린샷
            await self._save_screenshot(page, f"edit_before_submit_{campaign_code}")

            # 10. 등록/수정 버튼 클릭
            submit_button = await self._find_element(
                page, self.CAMPAIGN_SELECTORS["submit_button"]
            )
            if not submit_button:
                logger.warning("[캠페인수정] 등록 버튼을 찾을 수 없음")
                return False

            logger.info("[캠페인수정] 등록 버튼 클릭")
            await submit_button.click()
            await page.wait_for_timeout(3000)

            # 11. 결과 확인
            current_url = page.url
            logger.info(f"[캠페인수정] 제출 후 URL: {current_url}")

            if "/report" in current_url or "/list" in current_url:
                logger.info(f"[캠페인수정] 캠페인 {campaign_code} 수정 성공 (리다이렉트)")
                return True

            success_el = await self._find_element(
                page, self.CAMPAIGN_SELECTORS["success_message"]
            )
            if success_el:
                logger.info(f"[캠페인수정] 캠페인 {campaign_code} 수정 성공 (성공 메시지)")
                return True

            error_el = await self._find_element(
                page, self.CAMPAIGN_SELECTORS["error_alert"]
            )
            if error_el:
                error_text = await error_el.text_content() if error_el else ""
                logger.warning(f"[캠페인수정] 에러 발생: {error_text}")
                await self._save_screenshot(page, f"edit_error_{campaign_code}")
                return False

            if "/add" in current_url:
                await self._save_screenshot(page, f"edit_still_form_{campaign_code}")
                logger.warning(f"[캠페인수정] 수정 폼에 남아있음: {current_url}")
                return False

            logger.info(f"[캠페인수정] 캠페인 {campaign_code} 수정 완료")
            return True

        except Exception as e:
            logger.error(f"[캠페인수정] 캠페인 {campaign_code} 수정 중 예외: {e}")
            try:
                await self._save_screenshot(page, f"edit_exception_{campaign_code}")
            except Exception:
                pass
            return False

    async def _search_on_report_page(
        self,
        page: "Page",
        campaign_code: str,
    ) -> bool:
        """리포트 페이지에서 캠페인 번호 검색.

        Returns:
            검색 실행 성공 여부
        """
        await page.goto(self.CAMPAIGN_LIST_URL, wait_until="networkidle", timeout=30000)
        await self._human_like_delay(page)

        search_input = await self._find_element(
            page,
            'input[type="search"], input[name="search"], input[name="keyword"], '
            'input[name="query"], input[placeholder*="검색"], input[placeholder*="번호"], '
            'input[placeholder*="캠페인"], #searchInput, .search-input'
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
        """캠페인 키워드 수정.

        리포트 페이지에서 캠페인 검색 → 업체 클릭 → 수정 버튼 → 키워드 변경 → 등록.

        Args:
            account_id: 계정 식별자
            campaign_code: 캠페인 코드
            new_keywords: 새 키워드 문자열 (쉼표 구분, 255자 이내)

        Returns:
            수정 성공 여부
        """
        _logger = logging.getLogger(__name__)
        page = await self.get_page(account_id)

        try:
            # 1. 리포트 페이지에서 캠페인 번호 검색
            _logger.info(f"[키워드수정] 캠페인 {campaign_code}: 리포트에서 검색")
            if not await self._search_on_report_page(page, campaign_code):
                _logger.warning("[키워드수정] 검색 입력란을 찾을 수 없음")
                await self._save_screenshot(page, f"kw_no_search_{campaign_code}")
                return False

            # 2. 검색 결과에서 캠페인 이름 클릭
            _logger.info("[키워드수정] 검색 결과에서 캠페인 이름 클릭")
            campaign_clicked = await page.evaluate("""(code) => {
                const rows = document.querySelectorAll('table tbody tr');
                for (const row of rows) {
                    if (row.textContent && row.textContent.includes(code)) {
                        // 캠페인 이름 링크 찾기 (td 안의 a 태그)
                        const cells = row.querySelectorAll('td');
                        for (const cell of cells) {
                            const link = cell.querySelector('a');
                            if (link && link.textContent.trim().length > 0) {
                                // 숫자만 있는 링크(번호)가 아닌 이름 링크 클릭
                                const text = link.textContent.trim();
                                if (!/^\\d+$/.test(text)) {
                                    link.click();
                                    return 'name_link: ' + text;
                                }
                            }
                        }
                        // 이름 링크를 못 찾으면 첫 번째 링크라도 클릭
                        const anyLink = row.querySelector('a');
                        if (anyLink) { anyLink.click(); return 'any_link'; }
                        row.click();
                        return 'row';
                    }
                }
                return null;
            }""", campaign_code)

            if not campaign_clicked:
                _logger.warning(f"[키워드수정] 검색 결과에서 캠페인 {campaign_code}을 찾을 수 없음")
                await self._save_screenshot(page, f"kw_no_result_{campaign_code}")
                return False

            _logger.info(f"[키워드수정] 업체 클릭 완료 ({campaign_clicked})")
            await page.wait_for_timeout(2000)
            await self._human_like_delay(page)

            # 3. 상단 '수정' 버튼 클릭
            _logger.info("[키워드수정] 수정 버튼 찾는 중")
            edit_btn = await self._find_element(
                page,
                'a:has-text("수정"), button:has-text("수정"), '
                'a[href*="mode=modify"], a.btn-edit, button.btn-edit'
            )
            if not edit_btn:
                _logger.warning("[키워드수정] 수정 버튼을 찾을 수 없음")
                await self._save_screenshot(page, f"kw_no_edit_btn_{campaign_code}")
                return False

            await edit_btn.click()
            _logger.info("[키워드수정] 수정 버튼 클릭, 수정 페이지 대기")
            await page.wait_for_timeout(2000)
            await self._human_like_delay(page)

            # 4. 키워드 필드 변경
            _logger.info(f"[키워드수정] 키워드 입력 ({len(new_keywords)}자)")
            if not await self._fill_input_field(
                page, self.CAMPAIGN_SELECTORS["keywords"], new_keywords, "keywords"
            ):
                _logger.warning("[키워드수정] 키워드 입력 실패")
                await self._save_screenshot(page, f"kw_fill_fail_{campaign_code}")
                return False

            await self._human_like_delay(page)

            # 5. 등록 버튼 클릭
            submit_btn = await self._find_element(
                page, self.CAMPAIGN_SELECTORS["submit_button"]
            )
            if not submit_btn:
                _logger.warning("[키워드수정] 등록 버튼을 찾을 수 없음")
                await self._save_screenshot(page, f"kw_no_submit_{campaign_code}")
                return False

            _logger.info("[키워드수정] 등록 버튼 클릭")
            await submit_btn.click()
            await page.wait_for_timeout(3000)

            # 6. 결과 확인
            current_url = page.url
            _logger.info(f"[키워드수정] 제출 후 URL: {current_url}")

            if "/report" in current_url or "/list" in current_url:
                _logger.info(f"[키워드수정] 캠페인 {campaign_code} 키워드 수정 성공")
                return True

            success_el = await self._find_element(page, self.CAMPAIGN_SELECTORS["success_message"])
            if success_el:
                _logger.info(f"[키워드수정] 성공 (성공 메시지)")
                return True

            error_el = await self._find_element(page, self.CAMPAIGN_SELECTORS["error_alert"])
            if error_el:
                error_text = await error_el.inner_text()
                _logger.warning(f"[키워드수정] 오류: {error_text}")
                await self._save_screenshot(page, f"kw_error_{campaign_code}")
                return False

            if "/add" in current_url:
                _logger.warning("[키워드수정] 수정 페이지에 남아있음")
                await self._save_screenshot(page, f"kw_stuck_{campaign_code}")
                return False

            _logger.info(f"[키워드수정] 캠페인 {campaign_code} 키워드 수정 성공")
            return True

        except Exception as e:
            _logger.error(f"[키워드수정] 캠페인 {campaign_code} 오류: {e}")
            try:
                await self._save_screenshot(page, f"kw_exception_{campaign_code}")
            except Exception:
                pass
            return False

    async def get_campaign_status(
        self,
        account_id: str,
        campaign_code: str,
    ) -> Optional[str]:
        """캠페인 상태 조회 (검색 방식).

        리포트 페이지에서 캠페인 번호를 검색하여 상태를 확인합니다.

        Args:
            account_id: 계정 식별자
            campaign_code: 캠페인 코드

        Returns:
            상태 문자열 ('진행중', '일일소진', '캠페인소진' 등) 또는 None
        """
        page = await self.get_page(account_id)

        try:
            if not await self._search_on_report_page(page, campaign_code):
                return None

            status = await page.evaluate(r"""(campaignCode) => {
                const rows = document.querySelectorAll('table tbody tr, table tr');
                for (const row of rows) {
                    const cells = row.querySelectorAll('td');
                    if (cells.length < 9) continue;
                    const code = cells[0].textContent.trim();
                    if (code !== campaignCode && !row.textContent.includes(campaignCode)) continue;

                    // cell[8] = 상태 컬럼 (kt-badge 요소에서 직접 추출)
                    const badge = cells[8].querySelector('.kt-badge');
                    if (badge) return badge.textContent.trim();
                    // fallback: cell 텍스트
                    const cellText = cells[8].textContent.trim();
                    if (cellText) return cellText;
                }
                return null;
            }""", campaign_code)

            return status
        except Exception:
            return None

    async def get_campaign_status_with_conversions(
        self,
        account_id: str,
        campaign_code: str,
    ) -> Optional[dict]:
        """캠페인 상태 + 전환수 조회.

        리포트 페이지에서 캠페인 번호를 검색하여 상태와 전환수를 확인합니다.

        Args:
            account_id: 계정 식별자
            campaign_code: 캠페인 코드

        Returns:
            {"status": str, "current_count": int, "total_count": int} 또는 None
        """
        page = await self.get_page(account_id)

        try:
            if not await self._search_on_report_page(page, campaign_code):
                return None

            result = await page.evaluate(r"""(campaignCode) => {
                const rows = document.querySelectorAll('table tbody tr, table tr');
                for (const row of rows) {
                    const cells = row.querySelectorAll('td');
                    if (cells.length < 9) continue;
                    const code = cells[0].textContent.trim();
                    if (code !== campaignCode && !row.textContent.includes(campaignCode)) continue;

                    // cell[8] = 상태 컬럼 (kt-badge 요소에서 직접 추출)
                    let status = null;
                    const badge = cells[8].querySelector('.kt-badge');
                    if (badge) {
                        status = badge.textContent.trim();
                    } else {
                        const cellText = cells[8].textContent.trim();
                        if (cellText) status = cellText;
                    }

                    // cell[7] = 전환수 컬럼 ("현재 / 총" 형식)
                    let currentCount = 0;
                    let totalCount = 0;
                    const convText = cells[7].textContent.trim();
                    const slashMatch = convText.match(/^([\d,]+)\s*\/\s*([\d,]+)$/);
                    if (slashMatch) {
                        currentCount = parseInt(slashMatch[1].replace(/,/g, ''), 10) || 0;
                        totalCount = parseInt(slashMatch[2].replace(/,/g, ''), 10) || 0;
                    }

                    return {
                        status: status,
                        current_count: currentCount,
                        total_count: totalCount,
                    };
                }
                return null;
            }""", campaign_code)

            return result
        except Exception:
            return None

    async def get_all_campaign_statuses(
        self,
        account_id: str,
        campaign_codes: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """캠페인 상태 일괄 조회 (검색 방식).

        각 캠페인 번호를 검색창에 검색하여 상태를 확인합니다.

        Args:
            account_id: 계정 식별자
            campaign_codes: 조회할 캠페인 코드 목록

        Returns:
            {campaign_code: status} 딕셔너리
        """
        if not campaign_codes:
            return {}

        _logger = logging.getLogger(__name__)
        result: Dict[str, str] = {}

        for code in campaign_codes:
            try:
                status = await self.get_campaign_status(account_id, code)
                if status:
                    result[code] = status
                    _logger.info(f"캠페인 {code} 상태: {status}")
                else:
                    _logger.warning(f"캠페인 {code} 상태 확인 불가")
            except Exception as e:
                _logger.warning(f"캠페인 {code} 상태 조회 오류: {e}")

        return result

    async def get_form_field_values(self, account_id: str) -> Dict[str, str]:
        page = await self.get_page(account_id)
        values = {}
        field_mappings = {
            "campaign_name": self.CAMPAIGN_SELECTORS["campaign_name"],
            "participation_guide": self.CAMPAIGN_SELECTORS["participation_guide"],
            "keywords": self.CAMPAIGN_SELECTORS["keywords"],
            "hint": self.CAMPAIGN_SELECTORS["hint"],
            "walking_steps": self.CAMPAIGN_SELECTORS["conversion_input"],
            "total_budget": self.CAMPAIGN_SELECTORS["total_budget"],
            "day_budget": self.CAMPAIGN_SELECTORS["day_budget"],
            "begin_date": self.CAMPAIGN_SELECTORS["begin_date"],
            "end_date": self.CAMPAIGN_SELECTORS["end_date"],
        }
        for field_name, selector in field_mappings.items():
            try:
                selectors = [s.strip() for s in selector.split(",")]
                for sel in selectors:
                    element = await page.query_selector(sel)
                    if element:
                        value = await element.input_value()
                        values[field_name] = value
                        break
            except Exception:
                values[field_name] = ""
        return values

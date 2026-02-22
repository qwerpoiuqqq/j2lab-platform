"""네이버맵 스크래퍼 테스트."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.naver_map import (
    NaverMapScraper,
    NaverMapScraperError,
    LandmarkInfo,
    StealthConfig,
)


# 테스트용 플레이스 URL
TEST_PLACE_URL = "https://m.place.naver.com/restaurant/1724563569"
TEST_AROUND_URL = "https://m.place.naver.com/restaurant/1724563569/around"


class TestLandmarkInfo:
    """LandmarkInfo 데이터 클래스 테스트."""

    def test_create_with_all_fields(self):
        """모든 필드가 있는 경우."""
        landmark = LandmarkInfo(
            name="테스트 명소",
            url="https://m.place.naver.com/place/12345",
            place_id="12345",
        )
        assert landmark.name == "테스트 명소"
        assert landmark.url == "https://m.place.naver.com/place/12345"
        assert landmark.place_id == "12345"

    def test_create_with_name_only(self):
        """이름만 있는 경우."""
        landmark = LandmarkInfo(name="명소 이름")
        assert landmark.name == "명소 이름"
        assert landmark.url is None
        assert landmark.place_id is None


class TestStealthConfig:
    """StealthConfig 스텔스 설정 테스트."""

    def test_user_agents_not_empty(self):
        """User-Agent 풀이 비어있지 않음."""
        assert len(StealthConfig.USER_AGENTS) > 0

    def test_user_agents_contain_mobile(self):
        """User-Agent가 모바일 브라우저임."""
        for ua in StealthConfig.USER_AGENTS:
            assert "Mobile" in ua or "Android" in ua

    def test_viewports_not_empty(self):
        """뷰포트 풀이 비어있지 않음."""
        assert len(StealthConfig.VIEWPORTS) > 0

    def test_viewports_have_dimensions(self):
        """뷰포트에 width/height가 있음."""
        for vp in StealthConfig.VIEWPORTS:
            assert "width" in vp
            assert "height" in vp
            assert vp["width"] > 0
            assert vp["height"] > 0

    def test_get_random_user_agent(self):
        """랜덤 User-Agent가 풀에서 나옴."""
        ua = StealthConfig.get_random_user_agent()
        assert ua in StealthConfig.USER_AGENTS

    def test_get_random_viewport(self):
        """랜덤 뷰포트가 풀에서 나옴."""
        vp = StealthConfig.get_random_viewport()
        assert vp in StealthConfig.VIEWPORTS

    def test_get_random_delay_range(self):
        """랜덤 딜레이가 범위 내."""
        for _ in range(10):
            delay = StealthConfig.get_random_delay()
            assert StealthConfig.MIN_DELAY <= delay <= StealthConfig.MAX_DELAY

    def test_stealth_scripts_defined(self):
        """스텔스 스크립트가 정의됨."""
        assert StealthConfig.STEALTH_SCRIPTS
        assert "webdriver" in StealthConfig.STEALTH_SCRIPTS
        assert "chrome" in StealthConfig.STEALTH_SCRIPTS


class TestNaverMapScraperStealth:
    """NaverMapScraper 스텔스 모드 테스트."""

    def test_default_stealth_enabled(self):
        """기본값으로 스텔스 활성화."""
        scraper = NaverMapScraper()
        assert scraper.stealth is True

    def test_stealth_disabled(self):
        """스텔스 비활성화 옵션."""
        scraper = NaverMapScraper(stealth=False)
        assert scraper.stealth is False

    def test_get_fingerprint_before_init(self):
        """브라우저 초기화 전 fingerprint."""
        scraper = NaverMapScraper()
        fp = scraper.get_current_fingerprint()
        assert fp["user_agent"] is None
        assert fp["viewport"] is None
        assert fp["stealth_enabled"] is True


class TestNaverMapScraperUnit:
    """NaverMapScraper 단위 테스트 (브라우저 없이)."""

    def test_extract_place_id_from_url_place_pattern(self):
        """place 패턴에서 ID 추출."""
        scraper = NaverMapScraper()
        url = "https://m.place.naver.com/place/12345678"
        assert scraper._extract_place_id_from_url(url) == "12345678"

    def test_extract_place_id_from_url_restaurant_pattern(self):
        """restaurant 패턴에서 ID 추출."""
        scraper = NaverMapScraper()
        url = "https://m.place.naver.com/restaurant/1724563569"
        assert scraper._extract_place_id_from_url(url) == "1724563569"

    def test_extract_place_id_from_url_cafe_pattern(self):
        """cafe 패턴에서 ID 추출."""
        scraper = NaverMapScraper()
        url = "https://m.place.naver.com/cafe/98765432"
        assert scraper._extract_place_id_from_url(url) == "98765432"

    def test_extract_place_id_from_url_with_query(self):
        """쿼리 스트링이 포함된 URL."""
        scraper = NaverMapScraper()
        url = "https://m.place.naver.com/place/12345?entry=par"
        assert scraper._extract_place_id_from_url(url) == "12345"

    def test_extract_place_id_from_url_invalid(self):
        """잘못된 URL."""
        scraper = NaverMapScraper()
        url = "https://example.com/invalid"
        assert scraper._extract_place_id_from_url(url) is None

    def test_build_around_url_basic(self):
        """기본 URL에서 around URL 생성."""
        scraper = NaverMapScraper()
        url = "https://m.place.naver.com/restaurant/1724563569"
        expected = "https://m.place.naver.com/restaurant/1724563569/around?filter=100"
        assert scraper._build_around_url(url) == expected

    def test_build_around_url_with_home(self):
        """home 탭 URL에서 around URL 생성."""
        scraper = NaverMapScraper()
        url = "https://m.place.naver.com/restaurant/1724563569/home"
        expected = "https://m.place.naver.com/restaurant/1724563569/around?filter=100"
        assert scraper._build_around_url(url) == expected

    def test_build_around_url_already_around(self):
        """이미 around URL인 경우."""
        scraper = NaverMapScraper()
        url = "https://m.place.naver.com/restaurant/1724563569/around"
        expected = "https://m.place.naver.com/restaurant/1724563569/around?filter=100"
        assert scraper._build_around_url(url) == expected

    def test_build_around_url_with_trailing_slash(self):
        """끝에 슬래시가 있는 경우."""
        scraper = NaverMapScraper()
        url = "https://m.place.naver.com/restaurant/1724563569/"
        expected = "https://m.place.naver.com/restaurant/1724563569/around?filter=100"
        assert scraper._build_around_url(url) == expected

    def test_build_around_url_with_other_tabs(self):
        """다른 탭 URL에서 around URL 생성."""
        scraper = NaverMapScraper()
        tabs = ["feed", "menu", "booking", "review", "photo", "location", "information"]
        for tab in tabs:
            url = f"https://m.place.naver.com/restaurant/123/{tab}"
            expected = "https://m.place.naver.com/restaurant/123/around?filter=100"
            assert scraper._build_around_url(url) == expected

    def test_selectors_defined(self):
        """셀렉터 상수가 정의되어 있는지 확인."""
        assert "nearby_tab" in NaverMapScraper.SELECTORS
        assert "list_container" in NaverMapScraper.SELECTORS
        assert "list_item" in NaverMapScraper.SELECTORS
        assert "place_name" in NaverMapScraper.SELECTORS
        assert "place_link" in NaverMapScraper.SELECTORS


class TestNaverMapScraperMocked:
    """NaverMapScraper 모킹 테스트."""

    @pytest.fixture
    def mock_page(self):
        """Mock page 객체."""
        page = AsyncMock()
        return page

    @pytest.fixture
    def mock_browser_context(self, mock_page):
        """Mock browser context."""
        context = AsyncMock()
        context.new_page.return_value = mock_page
        return context

    @pytest.fixture
    def scraper_with_mock(self, mock_browser_context):
        """Mock이 설정된 스크래퍼."""
        scraper = NaverMapScraper()
        scraper._context = mock_browser_context
        scraper._browser = AsyncMock()
        return scraper

    @pytest.mark.asyncio
    async def test_get_nearby_landmarks_success(
        self, scraper_with_mock, mock_page
    ):
        """주변 명소 추출 성공."""
        # Mock 설정
        mock_page.wait_for_selector.return_value = None

        # 명소 아이템 Mock
        mock_item1 = AsyncMock()
        mock_name1 = AsyncMock()
        mock_name1.inner_text.return_value = "명소1"
        mock_item1.query_selector.side_effect = [mock_name1, None]

        mock_item2 = AsyncMock()
        mock_name2 = AsyncMock()
        mock_name2.inner_text.return_value = "명소2"
        mock_link2 = AsyncMock()
        mock_link2.get_attribute.return_value = "https://m.place.naver.com/place/123"
        mock_item2.query_selector.side_effect = [mock_name2, mock_link2]

        mock_page.query_selector_all.return_value = [mock_item1, mock_item2]

        # 실행
        landmarks = await scraper_with_mock.get_nearby_landmarks(TEST_PLACE_URL)

        # 검증
        assert len(landmarks) == 2
        assert landmarks[0].name == "명소1"
        assert landmarks[1].name == "명소2"
        assert landmarks[1].url == "https://m.place.naver.com/place/123"
        assert landmarks[1].place_id == "123"

    @pytest.mark.asyncio
    async def test_get_nearby_landmarks_no_list(self, scraper_with_mock, mock_page):
        """리스트 컨테이너가 없는 경우."""
        from playwright.async_api import TimeoutError as PlaywrightTimeout

        mock_page.wait_for_selector.side_effect = PlaywrightTimeout("Timeout")

        with pytest.raises(NaverMapScraperError) as exc_info:
            await scraper_with_mock.get_nearby_landmarks(TEST_PLACE_URL)

        assert "명소 목록을 찾을 수 없습니다" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_top_landmarks(self, scraper_with_mock, mock_page):
        """상위 N개 명소 추출."""
        # Mock 설정
        mock_page.wait_for_selector.return_value = None

        mock_items = []
        for i in range(5):
            mock_item = AsyncMock()
            mock_name = AsyncMock()
            mock_name.inner_text.return_value = f"명소{i + 1}"
            mock_item.query_selector.side_effect = [mock_name, None]
            mock_items.append(mock_item)

        mock_page.query_selector_all.return_value = mock_items

        # count=3으로 호출
        landmarks = await scraper_with_mock.get_top_landmarks(TEST_PLACE_URL, count=3)

        # 상위 3개만 반환
        assert len(landmarks) == 3
        assert landmarks[0].name == "명소1"
        assert landmarks[2].name == "명소3"

    @pytest.mark.asyncio
    async def test_select_first_landmark(self, scraper_with_mock, mock_page):
        """광고 제외 첫 번째 명소 선택."""
        # Mock 설정
        mock_page.wait_for_selector.return_value = None

        mock_items = []
        for i in range(3):
            mock_item = AsyncMock()
            mock_name = AsyncMock()
            mock_name.inner_text.return_value = f"명소{i + 1}"
            mock_item.query_selector.side_effect = [mock_name, None]
            mock_items.append(mock_item)

        mock_page.query_selector_all.return_value = mock_items

        # 첫 번째 선택
        landmark = await scraper_with_mock.select_first_landmark(TEST_PLACE_URL)

        # 결과 검증 - 항상 첫 번째
        assert landmark is not None
        assert landmark.name == "명소1"

    @pytest.mark.asyncio
    async def test_select_first_landmark_empty_list(
        self, scraper_with_mock, mock_page
    ):
        """명소가 없는 경우."""
        mock_page.wait_for_selector.return_value = None
        mock_page.query_selector_all.return_value = []

        result = await scraper_with_mock.select_first_landmark(TEST_PLACE_URL)
        assert result is None

    @pytest.mark.asyncio
    async def test_select_first_landmark_name(self, scraper_with_mock, mock_page):
        """첫 번째 명소 이름만 반환."""
        mock_page.wait_for_selector.return_value = None

        mock_item = AsyncMock()
        mock_name = AsyncMock()
        mock_name.inner_text.return_value = "테스트 명소"
        mock_item.query_selector.side_effect = [mock_name, None]

        mock_page.query_selector_all.return_value = [mock_item]

        name = await scraper_with_mock.select_first_landmark_name(TEST_PLACE_URL)
        assert name == "테스트 명소"

    @pytest.mark.asyncio
    async def test_filter_ad_links(self, scraper_with_mock, mock_page):
        """광고 링크 필터링."""
        mock_page.wait_for_selector.return_value = None

        # 광고 링크를 가진 아이템 (필터링되어 결과에서 제외됨)
        mock_ad_item = AsyncMock()
        mock_ad_name = AsyncMock()
        mock_ad_name.inner_text.return_value = "광고 명소"
        mock_ad_link = AsyncMock()
        mock_ad_link.get_attribute.return_value = "https://ader.naver.com/v1/abc123"
        mock_ad_item.query_selector.side_effect = [mock_ad_name, mock_ad_link]

        # 일반 링크를 가진 아이템
        mock_normal_item = AsyncMock()
        mock_normal_name = AsyncMock()
        mock_normal_name.inner_text.return_value = "일반 명소"
        mock_normal_link = AsyncMock()
        mock_normal_link.get_attribute.return_value = "https://m.place.naver.com/place/456"
        mock_normal_item.query_selector.side_effect = [mock_normal_name, mock_normal_link]

        mock_page.query_selector_all.return_value = [mock_ad_item, mock_normal_item]

        landmarks = await scraper_with_mock.get_nearby_landmarks(TEST_PLACE_URL)

        # 광고 아이템은 완전히 제외되고 일반 아이템만 반환됨
        assert len(landmarks) == 1
        assert landmarks[0].name == "일반 명소"
        assert landmarks[0].url == "https://m.place.naver.com/place/456"
        assert landmarks[0].place_id == "456"


class TestNaverMapScraperContextManager:
    """컨텍스트 매니저 테스트."""

    @pytest.mark.asyncio
    async def test_context_manager_init_and_close(self):
        """컨텍스트 매니저로 초기화 및 정리."""
        with patch.object(NaverMapScraper, "init_browser", new_callable=AsyncMock) as mock_init:
            with patch.object(NaverMapScraper, "close", new_callable=AsyncMock) as mock_close:
                async with NaverMapScraper() as scraper:
                    assert scraper is not None
                    mock_init.assert_called_once()

                mock_close.assert_called_once()


# 실제 브라우저 통합 테스트 (선택적 실행)
# 네트워크 의존성이 있으므로 CI에서는 스킵
@pytest.mark.integration
class TestNaverMapScraperIntegration:
    """실제 브라우저 통합 테스트."""

    @pytest.mark.asyncio
    async def test_real_scraping(self):
        """실제 네이버 플레이스 스크래핑."""
        async with NaverMapScraper(headless=True) as scraper:
            landmarks = await scraper.get_nearby_landmarks(TEST_PLACE_URL)

            # 최소 1개 이상의 명소가 있어야 함
            assert len(landmarks) > 0

            # 이름이 있어야 함
            for landmark in landmarks:
                assert landmark.name
                assert len(landmark.name) > 0

    @pytest.mark.asyncio
    async def test_real_top_landmarks(self):
        """실제 상위 명소 추출."""
        async with NaverMapScraper(headless=True) as scraper:
            landmarks = await scraper.get_top_landmarks(TEST_PLACE_URL, count=3)

            # 최대 3개
            assert len(landmarks) <= 3

    @pytest.mark.asyncio
    async def test_real_first_selection(self):
        """실제 첫 번째 명소 선택."""
        async with NaverMapScraper(headless=True) as scraper:
            name = await scraper.select_first_landmark_name(TEST_PLACE_URL)
            assert name is not None
            assert len(name) > 0


class TestParseSteps:
    """parse_steps 정적 메서드 테스트."""

    def test_parse_simple_number(self):
        """단순 숫자 파싱."""
        assert NaverMapScraper.parse_steps("789") == 789

    def test_parse_with_unit(self):
        """단위 포함 파싱."""
        assert NaverMapScraper.parse_steps("789걸음") == 789

    def test_parse_with_space_and_unit(self):
        """공백과 단위 포함 파싱."""
        assert NaverMapScraper.parse_steps("789 걸음") == 789

    def test_parse_with_comma(self):
        """천 단위 콤마 파싱."""
        assert NaverMapScraper.parse_steps("1,234 걸음") == 1234

    def test_parse_large_number(self):
        """큰 숫자 파싱."""
        assert NaverMapScraper.parse_steps("12,345걸음") == 12345

    def test_parse_only_comma_number(self):
        """콤마만 있는 숫자."""
        assert NaverMapScraper.parse_steps("1,234") == 1234

    def test_parse_empty_string_raises(self):
        """빈 문자열은 에러."""
        with pytest.raises(ValueError) as exc_info:
            NaverMapScraper.parse_steps("")
        assert "빈 걸음수 텍스트" in str(exc_info.value)

    def test_parse_no_number_raises(self):
        """숫자 없는 문자열은 에러."""
        with pytest.raises(ValueError) as exc_info:
            NaverMapScraper.parse_steps("걸음")
        assert "파싱할 수 없습니다" in str(exc_info.value)


class TestDirectionsSelectors:
    """길찾기 관련 셀렉터 상수 테스트."""

    def test_directions_selectors_defined(self):
        """길찾기 셀렉터가 정의되어 있는지 확인."""
        assert "directions_start_input" in NaverMapScraper.SELECTORS
        assert "directions_goal_input" in NaverMapScraper.SELECTORS
        assert "directions_autocomplete_item" in NaverMapScraper.SELECTORS
        assert "directions_search_btn" in NaverMapScraper.SELECTORS
        assert "directions_steps_value" in NaverMapScraper.SELECTORS
        assert "directions_steps_unit" in NaverMapScraper.SELECTORS

    def test_directions_url_defined(self):
        """길찾기 URL이 정의되어 있는지 확인."""
        assert NaverMapScraper.DIRECTIONS_URL
        assert "map.naver.com" in NaverMapScraper.DIRECTIONS_URL
        assert "walk" in NaverMapScraper.DIRECTIONS_URL

    def test_desktop_viewport_defined(self):
        """데스크톱 뷰포트가 정의되어 있는지 확인."""
        assert NaverMapScraper.DESKTOP_VIEWPORT
        assert "width" in NaverMapScraper.DESKTOP_VIEWPORT
        assert "height" in NaverMapScraper.DESKTOP_VIEWPORT
        assert NaverMapScraper.DESKTOP_VIEWPORT["width"] >= 1024


class TestGetWalkingStepsMocked:
    """get_walking_steps 모킹 테스트."""

    @pytest.fixture
    def mock_page(self):
        """Mock page 객체."""
        page = MagicMock()
        page.set_viewport_size = AsyncMock()
        page.goto = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.close = AsyncMock()
        return page

    @pytest.fixture
    def mock_desktop_context(self, mock_page):
        """Mock desktop context for directions."""
        context = MagicMock()
        context.add_init_script = AsyncMock()
        context.new_page = AsyncMock(return_value=mock_page)
        context.close = AsyncMock()
        return context

    @pytest.fixture
    def mock_browser(self, mock_desktop_context):
        """Mock browser."""
        browser = MagicMock()
        browser.new_context = AsyncMock(return_value=mock_desktop_context)
        return browser

    @pytest.fixture
    def scraper_with_mock(self, mock_browser):
        """Mock이 설정된 스크래퍼."""
        scraper = NaverMapScraper()
        scraper._browser = mock_browser
        scraper._context = AsyncMock()  # 모바일 컨텍스트 (사용 안함)
        scraper.stealth = False  # 스텔스 딜레이 비활성화
        return scraper

    @pytest.mark.asyncio
    async def test_get_walking_steps_success(
        self, scraper_with_mock, mock_browser, mock_desktop_context, mock_page
    ):
        """걸음수 추출 성공."""
        # Mock locator 설정 (locator는 동기 메서드, 그 메서드들은 비동기)
        mock_locator = MagicMock()
        mock_locator.click = AsyncMock()
        mock_locator.fill = AsyncMock()
        mock_locator.wait_for = AsyncMock()
        mock_locator.inner_text = AsyncMock(return_value="789")
        mock_locator.first = mock_locator

        mock_page.locator.return_value = mock_locator

        # walk_direction_info 요소 mock (query_selector_all은 AsyncMock이어야 함)
        mock_steps_info = AsyncMock()
        mock_steps_info.inner_text = AsyncMock(return_value="789 걸음")
        mock_page.query_selector_all = AsyncMock(return_value=[mock_steps_info])

        # 실행
        steps = await scraper_with_mock.get_walking_steps("서울역", "남대문시장")

        # 검증
        assert steps == 789

    @pytest.mark.asyncio
    async def test_get_walking_steps_with_comma(
        self, scraper_with_mock, mock_browser, mock_desktop_context, mock_page
    ):
        """콤마가 포함된 걸음수 추출."""
        mock_locator = MagicMock()
        mock_locator.click = AsyncMock()
        mock_locator.fill = AsyncMock()
        mock_locator.wait_for = AsyncMock()
        mock_locator.inner_text = AsyncMock(return_value="1,234")
        mock_locator.first = mock_locator

        mock_page.locator.return_value = mock_locator

        # walk_direction_info 요소 mock
        mock_steps_info = AsyncMock()
        mock_steps_info.inner_text = AsyncMock(return_value="1,234 걸음")
        mock_page.query_selector_all = AsyncMock(return_value=[mock_steps_info])

        steps = await scraper_with_mock.get_walking_steps("출발지", "도착지")
        assert steps == 1234

    @pytest.mark.asyncio
    async def test_get_walking_steps_no_start_result(
        self, scraper_with_mock, mock_browser, mock_desktop_context, mock_page
    ):
        """출발지 검색 결과 없음."""
        mock_start_input = MagicMock()
        mock_start_input.click = AsyncMock()
        mock_start_input.fill = AsyncMock()

        mock_autocomplete = MagicMock()
        mock_autocomplete.wait_for = AsyncMock(side_effect=Exception("Timeout"))

        # 첫 번째 locator 호출은 start_input
        # 두 번째 locator 호출은 autocomplete (first를 통해)
        mock_start_input.first = mock_start_input
        mock_autocomplete.first = mock_autocomplete

        call_count = [0]

        def mock_locator_side_effect(selector):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_start_input
            return mock_autocomplete

        mock_page.locator.side_effect = mock_locator_side_effect

        with pytest.raises(NaverMapScraperError) as exc_info:
            await scraper_with_mock.get_walking_steps("없는장소", "도착지")

        assert "출발지 검색 결과를 찾을 수 없습니다" in str(exc_info.value)


# 길찾기 통합 테스트 (선택적 실행)
@pytest.mark.integration
class TestDirectionsIntegration:
    """길찾기 실제 브라우저 통합 테스트."""

    @pytest.mark.asyncio
    async def test_real_walking_steps(self):
        """실제 도보 걸음수 추출."""
        async with NaverMapScraper(headless=True) as scraper:
            steps = await scraper.get_walking_steps("서울역", "남대문시장")

            # 걸음수가 양수
            assert steps > 0
            # 합리적인 범위 (500m~2km 사이의 거리)
            assert 300 < steps < 5000

    @pytest.mark.asyncio
    async def test_real_walking_steps_longer_route(self):
        """더 긴 경로의 걸음수 추출."""
        async with NaverMapScraper(headless=True) as scraper:
            steps = await scraper.get_walking_steps("서울역", "명동역")

            assert steps > 0
            # 더 긴 거리 (명동까지)
            assert steps > 500

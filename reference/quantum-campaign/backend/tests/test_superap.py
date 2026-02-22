"""superap.io 컨트롤러 테스트."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.superap import (
    SuperapController,
    SuperapError,
    SuperapLoginError,
    StealthConfig,
)


class TestStealthConfig:
    """스텔스 설정 테스트."""

    def test_user_agents_not_empty(self):
        """User-Agent 목록이 비어있지 않음."""
        assert len(StealthConfig.USER_AGENTS) > 0

    def test_user_agents_contain_desktop(self):
        """User-Agent가 데스크톱 브라우저 포함."""
        for ua in StealthConfig.USER_AGENTS:
            assert "Windows" in ua or "Macintosh" in ua

    def test_viewports_not_empty(self):
        """뷰포트 목록이 비어있지 않음."""
        assert len(StealthConfig.VIEWPORTS) > 0

    def test_viewports_have_dimensions(self):
        """뷰포트에 width, height 포함."""
        for vp in StealthConfig.VIEWPORTS:
            assert "width" in vp
            assert "height" in vp
            assert vp["width"] >= 1024  # 데스크톱 최소 너비

    def test_get_random_user_agent(self):
        """랜덤 User-Agent 반환."""
        ua = StealthConfig.get_random_user_agent()
        assert ua in StealthConfig.USER_AGENTS

    def test_get_random_viewport(self):
        """랜덤 뷰포트 반환."""
        vp = StealthConfig.get_random_viewport()
        assert vp in StealthConfig.VIEWPORTS

    def test_get_random_delay_range(self):
        """랜덤 딜레이가 설정 범위 내."""
        for _ in range(10):
            delay = StealthConfig.get_random_delay()
            assert StealthConfig.MIN_DELAY <= delay <= StealthConfig.MAX_DELAY


class TestSuperapControllerSelectors:
    """셀렉터 상수 테스트."""

    def test_selectors_defined(self):
        """필수 셀렉터가 정의되어 있는지 확인."""
        assert "login_form" in SuperapController.SELECTORS
        assert "username_input" in SuperapController.SELECTORS
        assert "password_input" in SuperapController.SELECTORS
        assert "login_button" in SuperapController.SELECTORS

    def test_urls_defined(self):
        """URL 상수가 정의되어 있는지 확인."""
        assert SuperapController.BASE_URL
        assert SuperapController.LOGIN_URL
        assert "superap.io" in SuperapController.BASE_URL


class TestSuperapControllerUnit:
    """SuperapController 단위 테스트."""

    def test_default_settings(self):
        """기본 설정 확인."""
        controller = SuperapController()
        assert controller.headless is True
        assert controller.stealth is True
        assert controller._browser is None
        assert controller._contexts == {}

    def test_custom_settings(self):
        """커스텀 설정 확인."""
        controller = SuperapController(headless=False, stealth=False)
        assert controller.headless is False
        assert controller.stealth is False

    def test_get_active_accounts_empty(self):
        """초기 상태에서 활성 계정 없음."""
        controller = SuperapController()
        assert controller.get_active_accounts() == []

    def test_get_context_count_empty(self):
        """초기 상태에서 컨텍스트 수 0."""
        controller = SuperapController()
        assert controller.get_context_count() == 0


class TestSuperapControllerMocked:
    """모킹을 사용한 SuperapController 테스트."""

    @pytest.fixture
    def mock_page(self):
        """Mock page 객체."""
        page = MagicMock()
        page.goto = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.wait_for_selector = AsyncMock()
        page.query_selector = AsyncMock(return_value=None)  # 로그인 상태
        page.close = AsyncMock()
        return page

    @pytest.fixture
    def mock_context(self, mock_page):
        """Mock browser context."""
        context = MagicMock()
        context.new_page = AsyncMock(return_value=mock_page)
        context.add_init_script = AsyncMock()
        context.close = AsyncMock()
        return context

    @pytest.fixture
    def mock_browser(self, mock_context):
        """Mock browser."""
        browser = MagicMock()
        browser.new_context = AsyncMock(return_value=mock_context)
        browser.close = AsyncMock()
        return browser

    @pytest.fixture
    def controller_with_mock(self, mock_browser):
        """Mock이 설정된 컨트롤러."""
        controller = SuperapController()
        controller._browser = mock_browser
        controller._playwright = MagicMock()
        controller._playwright.stop = AsyncMock()
        return controller

    @pytest.mark.asyncio
    async def test_get_context_creates_new(self, controller_with_mock, mock_browser):
        """새 계정에 대해 컨텍스트 생성."""
        context = await controller_with_mock.get_context("account1")

        assert context is not None
        assert "account1" in controller_with_mock._contexts
        mock_browser.new_context.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_context_reuses_existing(self, controller_with_mock, mock_context):
        """기존 계정에 대해 기존 컨텍스트 반환."""
        controller_with_mock._contexts["account1"] = mock_context

        context = await controller_with_mock.get_context("account1")

        assert context is mock_context

    @pytest.mark.asyncio
    async def test_close_context(self, controller_with_mock, mock_context):
        """컨텍스트 닫기."""
        controller_with_mock._contexts["account1"] = mock_context

        await controller_with_mock.close_context("account1")

        assert "account1" not in controller_with_mock._contexts
        mock_context.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_context_with_stored_page(
        self, controller_with_mock, mock_context, mock_page
    ):
        """컨텍스트 닫을 때 저장된 페이지도 정리."""
        controller_with_mock._contexts["account1"] = mock_context
        controller_with_mock._pages["account1"] = mock_page

        await controller_with_mock.close_context("account1")

        assert "account1" not in controller_with_mock._contexts
        assert "account1" not in controller_with_mock._pages
        mock_page.close.assert_called_once()
        mock_context.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_context_nonexistent(self, controller_with_mock):
        """존재하지 않는 컨텍스트 닫기 (에러 없음)."""
        await controller_with_mock.close_context("nonexistent")
        # 에러 없이 완료

    @pytest.mark.asyncio
    async def test_is_logged_in_true(self, controller_with_mock, mock_page):
        """로그인 상태 확인 - 로그인됨."""
        mock_page.query_selector.return_value = None  # 로그인 폼 없음

        result = await controller_with_mock.is_logged_in(mock_page)

        assert result is True

    @pytest.mark.asyncio
    async def test_is_logged_in_false(self, controller_with_mock, mock_page):
        """로그인 상태 확인 - 로그인 안됨."""
        mock_page.query_selector.return_value = MagicMock()  # 로그인 폼 있음

        result = await controller_with_mock.is_logged_in(mock_page)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_login_status_with_stored_page(
        self, controller_with_mock, mock_page
    ):
        """저장된 페이지로 로그인 상태 확인."""
        mock_page.url = "https://superap.io/service/dashboard"
        mock_page.query_selector.return_value = None  # 로그인 폼 없음 = 로그인 상태
        controller_with_mock._pages["account1"] = mock_page

        result = await controller_with_mock.check_login_status("account1")

        assert result is True

    @pytest.mark.asyncio
    async def test_check_login_status_no_stored_page(self, controller_with_mock):
        """저장된 페이지가 없으면 로그인 안됨."""
        result = await controller_with_mock.check_login_status("account1")

        assert result is False


class TestSuperapLoginMocked:
    """로그인 기능 모킹 테스트."""

    @pytest.fixture
    def mock_page_for_login(self):
        """로그인용 Mock page."""
        page = MagicMock()
        page.goto = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.wait_for_selector = AsyncMock()
        page.close = AsyncMock()

        # locator 모킹
        mock_locator = MagicMock()
        mock_locator.click = AsyncMock()
        mock_locator.fill = AsyncMock()
        page.locator = MagicMock(return_value=mock_locator)

        return page

    @pytest.fixture
    def mock_context_for_login(self, mock_page_for_login):
        """로그인용 Mock context."""
        context = MagicMock()
        context.new_page = AsyncMock(return_value=mock_page_for_login)
        context.add_init_script = AsyncMock()
        context.close = AsyncMock()
        return context

    @pytest.fixture
    def controller_for_login(self, mock_context_for_login):
        """로그인 테스트용 컨트롤러."""
        controller = SuperapController()
        controller._browser = MagicMock()
        controller._browser.new_context = AsyncMock(return_value=mock_context_for_login)
        controller._playwright = MagicMock()
        controller._playwright.stop = AsyncMock()
        controller.stealth = False  # 딜레이 비활성화
        return controller

    @pytest.mark.asyncio
    async def test_login_success(self, controller_for_login, mock_page_for_login):
        """로그인 성공."""
        # 첫 번째 호출: 로그인 폼 있음 (로그인 필요)
        # 두 번째 호출 (로그인 후): 로그인 폼 없음 (성공)
        call_count = [0]

        async def mock_query_selector(selector):
            call_count[0] += 1
            if call_count[0] <= 1:
                return MagicMock()  # 로그인 폼 있음
            return None  # 로그인 성공

        mock_page_for_login.query_selector = mock_query_selector

        result = await controller_for_login.login(
            account_id="account1",
            username="testuser",
            password="testpass",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_login_already_logged_in(self, controller_for_login, mock_page_for_login):
        """이미 로그인된 상태."""
        mock_page_for_login.query_selector = AsyncMock(return_value=None)

        result = await controller_for_login.login(
            account_id="account1",
            username="testuser",
            password="testpass",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_login_failure_with_error(self, controller_for_login, mock_page_for_login):
        """로그인 실패 - 에러 메시지."""
        # 로그인 폼이 계속 존재 + 에러 메시지
        error_element = MagicMock()
        error_element.inner_text = AsyncMock(return_value="Invalid credentials")

        async def mock_query_selector(selector):
            if "error" in selector:
                return error_element
            return MagicMock()  # 로그인 폼 있음

        mock_page_for_login.query_selector = mock_query_selector

        with pytest.raises(SuperapLoginError) as exc_info:
            await controller_for_login.login(
                account_id="account1",
                username="wronguser",
                password="wrongpass",
            )

        assert "Invalid credentials" in str(exc_info.value)


class TestSuperapControllerContextManager:
    """컨텍스트 매니저 테스트."""

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """컨텍스트 매니저로 초기화 및 정리."""
        with patch.object(SuperapController, "initialize", new_callable=AsyncMock) as mock_init:
            with patch.object(SuperapController, "close", new_callable=AsyncMock) as mock_close:
                async with SuperapController() as controller:
                    assert controller is not None
                    mock_init.assert_called_once()

                mock_close.assert_called_once()


class TestGetPageMocked:
    """get_page 메서드 테스트."""

    @pytest.fixture
    def mock_page(self):
        """Mock page 객체."""
        page = MagicMock()
        page.url = "https://superap.io/service/dashboard"
        page.query_selector = AsyncMock(return_value=None)  # 로그인 상태
        page.close = AsyncMock()
        return page

    @pytest.mark.asyncio
    async def test_get_page_with_stored_page(self, mock_page):
        """저장된 페이지 반환."""
        controller = SuperapController()
        controller._pages["account1"] = mock_page

        page = await controller.get_page("account1")

        assert page is mock_page

    @pytest.mark.asyncio
    async def test_get_page_no_stored_page(self):
        """저장된 페이지 없으면 예외 발생."""
        controller = SuperapController()

        with pytest.raises(SuperapError) as exc_info:
            await controller.get_page("account1")

        assert "로그인 상태가 아닙니다" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_page_expired_session(self, mock_page):
        """저장된 페이지가 로그아웃 되었으면 예외 발생."""
        controller = SuperapController()
        mock_page.url = "https://superap.io"  # 로그인 페이지
        mock_page.query_selector = AsyncMock(return_value=MagicMock())  # 로그인 폼 있음
        controller._pages["account1"] = mock_page

        with pytest.raises(SuperapError) as exc_info:
            await controller.get_page("account1")

        assert "로그인 상태가 아닙니다" in str(exc_info.value)
        mock_page.close.assert_called_once()


class TestMultiAccountContext:
    """다중 계정 컨텍스트 테스트."""

    @pytest.mark.asyncio
    async def test_multiple_accounts_separate_contexts(self):
        """여러 계정이 독립적인 컨텍스트를 가짐."""
        controller = SuperapController()

        # Mock 설정
        mock_browser = MagicMock()
        contexts_created = []

        async def create_context(*args, **kwargs):
            ctx = MagicMock()
            ctx.add_init_script = AsyncMock()
            ctx.close = AsyncMock()
            contexts_created.append(ctx)
            return ctx

        mock_browser.new_context = create_context
        controller._browser = mock_browser
        controller._playwright = MagicMock()

        # 3개의 계정에 대해 컨텍스트 생성
        ctx1 = await controller.get_context("account1")
        ctx2 = await controller.get_context("account2")
        ctx3 = await controller.get_context("account3")

        # 각각 다른 컨텍스트인지 확인
        assert len(contexts_created) == 3
        assert ctx1 is not ctx2
        assert ctx2 is not ctx3
        assert controller.get_context_count() == 3
        assert set(controller.get_active_accounts()) == {"account1", "account2", "account3"}


# 통합 테스트 (선택적 실행)
@pytest.mark.integration
class TestSuperapIntegration:
    """실제 브라우저 통합 테스트."""

    @pytest.mark.asyncio
    async def test_real_page_load(self):
        """실제 페이지 로딩."""
        async with SuperapController(headless=True) as controller:
            context = await controller.get_context("test_account")
            page = await context.new_page()

            try:
                await page.goto("https://superap.io", wait_until="networkidle")

                # 로그인 폼 존재 확인
                login_form = await page.query_selector(
                    SuperapController.SELECTORS["login_form"]
                )
                assert login_form is not None

                # 아이디 입력 필드 존재 확인
                username_input = await page.query_selector(
                    SuperapController.SELECTORS["username_input"]
                )
                assert username_input is not None
            finally:
                await page.close()

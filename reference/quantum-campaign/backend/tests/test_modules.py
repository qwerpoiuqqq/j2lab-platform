"""모듈 시스템 테스트."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.modules.base import BaseModule, ModuleError
from app.modules.landmark import LandmarkModule
from app.modules.steps import StepsModule
from app.modules.registry import ModuleRegistry, register_default_modules
from app.services.naver_map import LandmarkInfo


class TestBaseModule:
    """BaseModule 추상 클래스 테스트."""

    def test_cannot_instantiate_directly(self):
        """BaseModule은 직접 인스턴스화할 수 없음."""
        with pytest.raises(TypeError):
            BaseModule()

    def test_get_info(self):
        """모듈 정보 반환."""
        module = LandmarkModule()
        info = module.get_info()

        assert info["module_id"] == "landmark"
        assert info["description"] == "플레이스 주변 명소 중 광고 제외 첫 번째 추출 + 실제 상호명/주소 추출"
        assert "landmark_name" in info["output_variables"]
        assert "landmark_id" in info["output_variables"]
        assert info["dependencies"] == []

    def test_validate_context_success(self):
        """컨텍스트 검증 성공."""
        module = LandmarkModule()
        context = {"place_url": "https://example.com"}

        # 예외 없이 통과
        module.validate_context(context, ["place_url"])

    def test_validate_context_missing_key(self):
        """컨텍스트에 필수 키 없음."""
        module = LandmarkModule()
        context = {}

        with pytest.raises(ModuleError) as exc_info:
            module.validate_context(context, ["place_url"])

        assert "place_url" in str(exc_info.value)

    def test_repr(self):
        """모듈 문자열 표현."""
        module = LandmarkModule()
        assert "LandmarkModule" in repr(module)
        assert "landmark" in repr(module)


class TestLandmarkModule:
    """LandmarkModule 테스트."""

    def test_module_attributes(self):
        """모듈 속성 확인."""
        module = LandmarkModule()

        assert module.module_id == "landmark"
        assert module.description == "플레이스 주변 명소 중 광고 제외 첫 번째 추출 + 실제 상호명/주소 추출"
        assert "landmark_name" in module.output_variables
        assert "landmark_id" in module.output_variables
        assert module.dependencies == []

    def test_init_with_options(self):
        """옵션으로 초기화."""
        module = LandmarkModule(headless=False, stealth=False)

        assert module.headless is False
        assert module.stealth is False

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """명소 추출 성공."""
        module = LandmarkModule()
        context = {"place_url": "https://m.place.naver.com/restaurant/123"}

        # NaverMapScraper 모킹
        mock_landmark = LandmarkInfo(
            name="테스트 명소",
            url="https://m.place.naver.com/place/456",
            place_id="456",
        )

        with patch("app.modules.landmark.NaverMapScraper") as MockScraper:
            mock_instance = AsyncMock()
            mock_instance.select_first_landmark.return_value = mock_landmark
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            MockScraper.return_value = mock_instance

            result = await module.execute(context)

        assert result["landmark_name"] == "테스트 명소"
        assert result["landmark_id"] == "456"

    @pytest.mark.asyncio
    async def test_execute_no_landmarks(self):
        """명소가 없는 경우."""
        module = LandmarkModule()
        context = {"place_url": "https://m.place.naver.com/restaurant/123"}

        with patch("app.modules.landmark.NaverMapScraper") as MockScraper:
            mock_instance = AsyncMock()
            mock_instance.select_first_landmark.return_value = None
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            MockScraper.return_value = mock_instance

            with pytest.raises(ModuleError) as exc_info:
                await module.execute(context)

            assert "주변 명소를 찾을 수 없습니다" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_missing_place_url(self):
        """place_url이 없는 경우."""
        module = LandmarkModule()
        context = {}

        with pytest.raises(ModuleError) as exc_info:
            await module.execute(context)

        assert "place_url" in str(exc_info.value)


class TestStepsModule:
    """StepsModule 테스트."""

    def test_module_attributes(self):
        """모듈 속성 확인."""
        module = StepsModule()

        assert module.module_id == "steps"
        assert module.description == "명소→업체 도보 걸음수 계산"
        assert "steps" in module.output_variables
        assert "landmark" in module.dependencies

    def test_init_with_options(self):
        """옵션으로 초기화."""
        module = StepsModule(headless=False, stealth=False)

        assert module.headless is False
        assert module.stealth is False

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """걸음수 계산 성공."""
        module = StepsModule()
        context = {
            "landmark_name": "마포역 2번출구",
            "place_name": "일류곱창 마포공덕본점",
        }

        with patch("app.modules.steps.NaverMapScraper") as MockScraper:
            mock_instance = AsyncMock()
            mock_instance.get_walking_steps.return_value = 863
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            MockScraper.return_value = mock_instance

            result = await module.execute(context)

        assert result["steps"] == 863

    @pytest.mark.asyncio
    async def test_execute_missing_landmark_name(self):
        """landmark_name이 없는 경우."""
        module = StepsModule()
        context = {"place_name": "테스트 가게"}

        with pytest.raises(ModuleError) as exc_info:
            await module.execute(context)

        assert "landmark_name" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_missing_place_name(self):
        """place_name이 없는 경우."""
        module = StepsModule()
        context = {"landmark_name": "테스트 명소"}

        with pytest.raises(ModuleError) as exc_info:
            await module.execute(context)

        assert "place_name" in str(exc_info.value)


class TestModuleRegistry:
    """ModuleRegistry 테스트."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """각 테스트 전후로 레지스트리 초기화."""
        ModuleRegistry.clear()
        yield
        ModuleRegistry.clear()

    def test_register_and_get(self):
        """모듈 등록 및 조회."""
        module = LandmarkModule()
        ModuleRegistry.register(module)

        retrieved = ModuleRegistry.get("landmark")
        assert retrieved is module

    def test_get_nonexistent(self):
        """존재하지 않는 모듈 조회."""
        result = ModuleRegistry.get("nonexistent")
        assert result is None

    def test_unregister(self):
        """모듈 등록 해제."""
        module = LandmarkModule()
        ModuleRegistry.register(module)

        ModuleRegistry.unregister("landmark")
        assert ModuleRegistry.get("landmark") is None

    def test_clear(self):
        """모든 모듈 제거."""
        ModuleRegistry.register(LandmarkModule())
        ModuleRegistry.register(StepsModule())

        ModuleRegistry.clear()
        assert len(ModuleRegistry.get_all()) == 0

    def test_get_all(self):
        """모든 모듈 조회."""
        landmark = LandmarkModule()
        steps = StepsModule()
        ModuleRegistry.register(landmark)
        ModuleRegistry.register(steps)

        all_modules = ModuleRegistry.get_all()
        assert len(all_modules) == 2
        assert landmark in all_modules
        assert steps in all_modules

    def test_get_all_info(self):
        """모든 모듈 정보 조회."""
        ModuleRegistry.register(LandmarkModule())
        ModuleRegistry.register(StepsModule())

        all_info = ModuleRegistry.get_all_info()
        assert len(all_info) == 2

        module_ids = [info["module_id"] for info in all_info]
        assert "landmark" in module_ids
        assert "steps" in module_ids

    def test_sort_by_dependencies_single(self):
        """의존성 없는 단일 모듈 정렬."""
        ModuleRegistry.register(LandmarkModule())

        sorted_ids = ModuleRegistry._sort_by_dependencies(["landmark"])
        assert sorted_ids == ["landmark"]

    def test_sort_by_dependencies_with_deps(self):
        """의존성이 있는 모듈 정렬."""
        ModuleRegistry.register(LandmarkModule())
        ModuleRegistry.register(StepsModule())

        # steps는 landmark에 의존하므로 landmark가 먼저 와야 함
        sorted_ids = ModuleRegistry._sort_by_dependencies(["steps", "landmark"])
        assert sorted_ids.index("landmark") < sorted_ids.index("steps")

    def test_sort_by_dependencies_unknown_module(self):
        """등록되지 않은 모듈 정렬 시도."""
        with pytest.raises(ModuleError) as exc_info:
            ModuleRegistry._sort_by_dependencies(["unknown"])

        assert "등록되지 않은 모듈" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_modules_empty(self):
        """빈 모듈 목록 실행."""
        initial = {"place_url": "https://example.com"}
        result = await ModuleRegistry.execute_modules([], initial)

        assert result == initial

    @pytest.mark.asyncio
    async def test_execute_modules_single(self):
        """단일 모듈 실행."""
        ModuleRegistry.register(LandmarkModule())

        initial_context = {"place_url": "https://m.place.naver.com/restaurant/123"}
        mock_landmark = LandmarkInfo(name="테스트명소", place_id="456")

        with patch("app.modules.landmark.NaverMapScraper") as MockScraper:
            mock_instance = AsyncMock()
            mock_instance.select_first_landmark.return_value = mock_landmark
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            MockScraper.return_value = mock_instance

            result = await ModuleRegistry.execute_modules(
                ["landmark"], initial_context
            )

        assert result["place_url"] == initial_context["place_url"]
        assert result["landmark_name"] == "테스트명소"
        assert result["landmark_id"] == "456"

    @pytest.mark.asyncio
    async def test_execute_modules_with_dependencies(self):
        """의존성 있는 모듈들 실행."""
        ModuleRegistry.register(LandmarkModule())
        ModuleRegistry.register(StepsModule())

        initial_context = {
            "place_url": "https://m.place.naver.com/restaurant/123",
            "place_name": "테스트 가게",
        }

        mock_landmark = LandmarkInfo(name="마포역", place_id="789")

        with patch("app.modules.landmark.NaverMapScraper") as MockLandmarkScraper:
            mock_landmark_instance = AsyncMock()
            mock_landmark_instance.select_first_landmark.return_value = mock_landmark
            mock_landmark_instance.__aenter__.return_value = mock_landmark_instance
            mock_landmark_instance.__aexit__.return_value = None
            MockLandmarkScraper.return_value = mock_landmark_instance

            with patch("app.modules.steps.NaverMapScraper") as MockStepsScraper:
                mock_steps_instance = AsyncMock()
                mock_steps_instance.get_walking_steps.return_value = 500
                mock_steps_instance.__aenter__.return_value = mock_steps_instance
                mock_steps_instance.__aexit__.return_value = None
                MockStepsScraper.return_value = mock_steps_instance

                result = await ModuleRegistry.execute_modules(
                    ["steps", "landmark"],  # steps가 먼저 있어도 landmark 먼저 실행
                    initial_context,
                )

        # 원본 컨텍스트 유지
        assert result["place_url"] == initial_context["place_url"]
        assert result["place_name"] == initial_context["place_name"]
        # landmark 모듈 결과
        assert result["landmark_name"] == "마포역"
        assert result["landmark_id"] == "789"
        # steps 모듈 결과
        assert result["steps"] == 500


class TestRegisterDefaultModules:
    """register_default_modules 함수 테스트."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """각 테스트 전후로 레지스트리 초기화."""
        ModuleRegistry.clear()
        yield
        ModuleRegistry.clear()

    def test_register_default_modules(self):
        """기본 모듈 등록."""
        register_default_modules()

        assert ModuleRegistry.get("landmark") is not None
        assert ModuleRegistry.get("steps") is not None

    def test_register_default_modules_types(self):
        """기본 모듈 타입 확인."""
        register_default_modules()

        landmark = ModuleRegistry.get("landmark")
        steps = ModuleRegistry.get("steps")

        assert isinstance(landmark, LandmarkModule)
        assert isinstance(steps, StepsModule)


# 통합 테스트 (선택적 실행)
@pytest.mark.integration
class TestModulesIntegration:
    """모듈 시스템 통합 테스트."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """각 테스트 전후로 레지스트리 초기화."""
        ModuleRegistry.clear()
        yield
        ModuleRegistry.clear()

    @pytest.mark.asyncio
    async def test_full_flow_landmark_only(self):
        """명소 모듈만 실행하는 전체 플로우."""
        register_default_modules()

        context = await ModuleRegistry.execute_modules(
            module_ids=["landmark"],
            initial_context={
                "place_url": "https://m.place.naver.com/restaurant/1724563569",
            },
        )

        assert "landmark_name" in context
        assert context["landmark_name"]  # 비어있지 않음

    @pytest.mark.asyncio
    async def test_full_flow_both_modules(self):
        """명소 + 걸음수 모듈 전체 플로우."""
        register_default_modules()

        context = await ModuleRegistry.execute_modules(
            module_ids=["landmark", "steps"],
            initial_context={
                "place_url": "https://m.place.naver.com/restaurant/1724563569",
                "place_name": "일류곱창 마포공덕본점",
            },
        )

        assert "landmark_name" in context
        assert "steps" in context
        assert isinstance(context["steps"], int)
        assert context["steps"] > 0

"""모듈 레지스트리 - 모듈 등록 및 실행 관리."""

from typing import Any, Dict, List, Optional, Type

from app.modules.base import BaseModule, ModuleError


class ModuleRegistry:
    """모듈 레지스트리.

    모든 모듈을 등록하고 관리하며, 의존성 순서에 따라 모듈을 실행합니다.
    """

    _modules: Dict[str, BaseModule] = {}

    @classmethod
    def register(cls, module: BaseModule) -> None:
        """모듈 등록.

        Args:
            module: 등록할 모듈 인스턴스
        """
        cls._modules[module.module_id] = module

    @classmethod
    def unregister(cls, module_id: str) -> None:
        """모듈 등록 해제.

        Args:
            module_id: 해제할 모듈 ID
        """
        if module_id in cls._modules:
            del cls._modules[module_id]

    @classmethod
    def clear(cls) -> None:
        """모든 모듈 등록 해제."""
        cls._modules.clear()

    @classmethod
    def get(cls, module_id: str) -> Optional[BaseModule]:
        """모듈 ID로 모듈 조회.

        Args:
            module_id: 조회할 모듈 ID

        Returns:
            모듈 인스턴스 또는 None
        """
        return cls._modules.get(module_id)

    @classmethod
    def get_all(cls) -> List[BaseModule]:
        """등록된 모든 모듈 반환.

        Returns:
            모듈 인스턴스 리스트
        """
        return list(cls._modules.values())

    @classmethod
    def get_all_info(cls) -> List[Dict[str, Any]]:
        """등록된 모든 모듈의 정보 반환.

        Returns:
            모듈 정보 딕셔너리 리스트
        """
        return [module.get_info() for module in cls._modules.values()]

    @classmethod
    def _sort_by_dependencies(cls, module_ids: List[str]) -> List[str]:
        """모듈 ID를 의존성 순서대로 정렬.

        Args:
            module_ids: 정렬할 모듈 ID 목록

        Returns:
            의존성 순서로 정렬된 모듈 ID 목록

        Raises:
            ModuleError: 등록되지 않은 모듈이 있거나, 순환 의존성이 있는 경우
        """
        # 존재 여부 확인
        for module_id in module_ids:
            if module_id not in cls._modules:
                raise ModuleError(f"등록되지 않은 모듈입니다: {module_id}")

        # 위상 정렬 (Kahn's Algorithm)
        # 의존성 그래프 구성 (module_ids에 포함된 모듈만)
        in_degree: Dict[str, int] = {mid: 0 for mid in module_ids}
        graph: Dict[str, List[str]] = {mid: [] for mid in module_ids}

        for module_id in module_ids:
            module = cls._modules[module_id]
            for dep_id in module.dependencies:
                if dep_id in module_ids:
                    graph[dep_id].append(module_id)
                    in_degree[module_id] += 1

        # 진입 차수가 0인 노드부터 시작
        queue: List[str] = [mid for mid in module_ids if in_degree[mid] == 0]
        result: List[str] = []

        while queue:
            current = queue.pop(0)
            result.append(current)

            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # 순환 의존성 체크
        if len(result) != len(module_ids):
            remaining = set(module_ids) - set(result)
            raise ModuleError(f"순환 의존성이 감지되었습니다: {remaining}")

        return result

    @classmethod
    async def execute_modules(
        cls,
        module_ids: List[str],
        initial_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """모듈들을 의존성 순서대로 실행.

        Args:
            module_ids: 실행할 모듈 ID 목록
            initial_context: 초기 데이터 (place_url, place_name 등)

        Returns:
            모든 모듈 결과를 합친 컨텍스트 딕셔너리

        Raises:
            ModuleError: 모듈 실행 실패 시
        """
        if not module_ids:
            return initial_context.copy()

        # 의존성 순서대로 정렬
        sorted_modules = cls._sort_by_dependencies(module_ids)

        # 컨텍스트 초기화
        context = initial_context.copy()

        # 모듈 순차 실행
        for module_id in sorted_modules:
            module = cls.get(module_id)
            if module is None:
                raise ModuleError(f"등록되지 않은 모듈입니다: {module_id}")

            try:
                result = await module.execute(context)
                context.update(result)
            except ModuleError:
                raise
            except Exception as e:
                raise ModuleError(
                    f"모듈 '{module_id}' 실행 중 예기치 않은 오류: {str(e)}"
                )

        return context


def register_default_modules() -> None:
    """기본 모듈들을 레지스트리에 등록.

    애플리케이션 시작 시 호출하여 기본 모듈들을 등록합니다.
    """
    from app.modules.place_info import PlaceInfoModule
    from app.modules.landmark import LandmarkModule
    from app.modules.steps import StepsModule

    ModuleRegistry.register(PlaceInfoModule())
    ModuleRegistry.register(LandmarkModule())
    ModuleRegistry.register(StepsModule())

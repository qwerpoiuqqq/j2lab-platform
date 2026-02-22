"""모듈 기본 클래스 정의."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class ModuleError(Exception):
    """모듈 실행 중 발생하는 에러."""

    pass


class BaseModule(ABC):
    """모듈 기본 추상 클래스.

    모든 모듈은 이 클래스를 상속받아 구현해야 합니다.
    개발자만 새로운 모듈을 구현할 수 있으며, 사용자는 템플릿에서 모듈을 켜고 끄기만 합니다.

    Attributes:
        module_id: 모듈 고유 ID (템플릿에서 참조)
        description: 모듈 설명 (UI 표시용)
        output_variables: 반환하는 변수명 목록 (템플릿에서 &변수명& 형태로 사용)
        dependencies: 의존하는 다른 모듈 ID 목록 (해당 모듈이 먼저 실행되어야 함)
    """

    # 모듈 고유 ID (서브클래스에서 정의 필수)
    module_id: str = ""

    # 모듈 설명 (UI 표시용)
    description: str = ""

    # 반환하는 변수명 목록
    output_variables: List[str] = []

    # 의존하는 다른 모듈 ID 목록
    dependencies: List[str] = []

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """모듈 실행.

        Args:
            context: 입력 데이터 딕셔너리
                - place_url: 플레이스 URL
                - place_name: 플레이스 상호명
                - 이전 모듈 결과들 (예: landmark_name, landmark_id 등)

        Returns:
            output_variables에 정의된 키-값 딕셔너리

        Raises:
            ModuleError: 모듈 실행 실패 시
        """
        pass

    def get_info(self) -> Dict[str, Any]:
        """모듈 정보 반환.

        Returns:
            모듈 메타데이터 딕셔너리
        """
        return {
            "module_id": self.module_id,
            "description": self.description,
            "output_variables": self.output_variables,
            "dependencies": self.dependencies,
        }

    def validate_context(self, context: Dict[str, Any], required_keys: List[str]) -> None:
        """컨텍스트에 필수 키가 있는지 검증.

        Args:
            context: 검증할 컨텍스트
            required_keys: 필수 키 목록

        Raises:
            ModuleError: 필수 키가 없는 경우
        """
        missing_keys = [key for key in required_keys if key not in context]
        if missing_keys:
            raise ModuleError(
                f"모듈 '{self.module_id}' 실행에 필요한 데이터가 없습니다: {missing_keys}"
            )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.module_id})>"

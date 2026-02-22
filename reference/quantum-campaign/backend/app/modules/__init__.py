"""모듈 시스템 패키지.

이 패키지는 캠페인 등록에 필요한 정보를 수집하는 모듈들을 제공합니다.
개발자만 새로운 모듈을 추가할 수 있으며, 사용자는 템플릿에서 모듈을 켜고 끄기만 합니다.
"""

from app.modules.base import BaseModule, ModuleError
from app.modules.landmark import LandmarkModule
from app.modules.steps import StepsModule
from app.modules.registry import ModuleRegistry

__all__ = [
    "BaseModule",
    "ModuleError",
    "LandmarkModule",
    "StepsModule",
    "ModuleRegistry",
]

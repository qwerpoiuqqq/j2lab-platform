"""걸음수 계산 모듈."""

from typing import Any, Dict, List

from app.modules.base import BaseModule, ModuleError
from app.services.naver_map import NaverMapScraper, NaverMapScraperError


class StepsModule(BaseModule):
    """출발지에서 업체까지 도보 걸음수 계산 모듈.

    네이버맵 길찾기를 통해 출발지에서 플레이스까지의 도보 걸음수를 계산합니다.

    출발지 우선순위:
        1. context["steps_start"] (직접 지정)
        2. context["landmark_name"] (landmark 모듈 결과)

    Input (context):
        - place_name: 도착지 플레이스 상호명 (필수)
        - landmark_name 또는 steps_start: 출발지 (하나 이상 필수)
        - real_place_name: 실제 상호명 (있으면 도착지에 우선 사용)
        - place_area: 지역 힌트 (선택, 자동완성 검증용)

    Output:
        - steps: 도보 걸음수 (정수)
    """

    module_id: str = "steps"
    description: str = "출발지→업체 도보 걸음수 계산"
    output_variables: List[str] = ["steps"]
    dependencies: List[str] = ["landmark", "place_info"]

    def __init__(self, headless: bool = True, stealth: bool = True):
        self.headless = headless
        self.stealth = stealth

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """걸음수 계산 실행."""
        self.validate_context(context, ["place_name"])

        # 출발지: steps_start > landmark_name
        start = context.get("steps_start") or context.get("landmark_name")
        if not start:
            raise ModuleError(
                "출발지를 결정할 수 없습니다: steps_start 또는 landmark_name이 필요합니다"
            )

        # 도착지: real_place_name > place_name
        destination = context.get("real_place_name") or context["place_name"]
        # 주소 검증용 지역 힌트
        area_hint = context.get("place_area")

        try:
            async with NaverMapScraper(
                headless=self.headless, stealth=self.stealth
            ) as scraper:
                steps = await scraper.get_walking_steps(
                    start, destination, area_hint=area_hint,
                )

            return {"steps": steps}

        except NaverMapScraperError as e:
            raise ModuleError(f"걸음수 계산 실패: {str(e)}")
        except ModuleError:
            raise
        except Exception as e:
            raise ModuleError(f"걸음수 모듈 실행 중 오류: {str(e)}")

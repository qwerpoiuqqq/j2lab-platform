"""명소 추출 모듈."""

from typing import Any, Dict, List

from app.modules.base import BaseModule, ModuleError
from app.services.naver_map import NaverMapScraper, NaverMapScraperError


class LandmarkModule(BaseModule):
    """플레이스 주변 명소 선택 모듈.

    네이버맵에서 플레이스 주변 → 명소 탭에서 명소를 선택합니다.

    선택 전략 (context로 제어):
        - landmark_strategy = "random": 1~5개 명소 중 랜덤 (명소 퀴즈용)
        - landmark_strategy = "min_distance": 100m 이상 첫 번째 (트래픽/걸음수용)
        - 기본값: "random"

    Input (context):
        - place_url: 플레이스 URL (필수)
        - landmark_strategy: 선택 전략 (선택)
        - landmark_min_distance: 최소 거리 (선택, min_distance 전략용)

    Output:
        - landmark_name: 선택된 명소 이름
        - landmark_index: 명소 목록 내 순번 (1-based)
    """

    module_id: str = "landmark"
    description: str = "플레이스 주변 명소 선택"
    output_variables: List[str] = ["landmark_name", "landmark_index"]
    dependencies: List[str] = []

    def __init__(self, headless: bool = True, stealth: bool = True):
        self.headless = headless
        self.stealth = stealth

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """명소 선택 실행."""
        self.validate_context(context, ["place_url"])

        place_url = context["place_url"]
        strategy = context.get("landmark_strategy", "random")
        min_distance = context.get("landmark_min_distance", 100)

        try:
            async with NaverMapScraper(
                headless=self.headless, stealth=self.stealth
            ) as scraper:
                if strategy == "min_distance":
                    landmark = await scraper.select_landmark_by_min_distance(
                        place_url, min_distance_m=min_distance,
                        random_pick=False, max_candidates=1,
                    )
                else:
                    # random: 1~5개 중 랜덤 (거리 제한 없음)
                    landmark = await scraper.select_landmark_by_min_distance(
                        place_url, min_distance_m=0,
                        random_pick=True, max_candidates=5,
                    )

            if landmark is None:
                raise ModuleError(f"주변 명소를 찾을 수 없습니다: {place_url}")

            result: Dict[str, Any] = {
                "landmark_name": landmark.name,
                "landmark_index": landmark.index,
            }

            # 내부용 (context 전파, 템플릿 가이드에는 미노출)
            if landmark.place_id:
                result["landmark_id"] = landmark.place_id
            if landmark.distance_m is not None:
                result["landmark_distance_m"] = landmark.distance_m

            return result

        except NaverMapScraperError as e:
            raise ModuleError(f"명소 추출 실패: {str(e)}")
        except ModuleError:
            raise
        except Exception as e:
            raise ModuleError(f"명소 모듈 실행 중 오류: {str(e)}")

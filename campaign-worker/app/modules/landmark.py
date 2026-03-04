"""Landmark extraction module.

Selects a nearby landmark from Naver Place's "주변 > 명소" tab.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.modules.base import BaseModule, ModuleError
from app.services.naver_map import NaverMapScraper, NaverMapScraperError


class LandmarkModule(BaseModule):
    """Select a nearby landmark from place's surrounding area.

    Selection strategies (controlled via context):
        - landmark_strategy = "random": Random pick from top 1-5 landmarks
        - landmark_strategy = "min_distance": First landmark >= 100m away
        - Default: "random"

    Input (context):
        - place_url: Naver Place URL (required)
        - landmark_strategy: Selection strategy (optional)
        - landmark_min_distance: Minimum distance in meters (optional)

    Output:
        - landmark_name: Selected landmark name
        - landmark_index: Position in list (1-based)
    """

    module_id: str = "landmark"
    description: str = "플레이스 주변 명소 선택"
    output_variables: List[str] = ["landmark_name", "landmark_index"]
    dependencies: List[str] = []

    def __init__(self, headless: bool = True, stealth: bool = True):
        self.headless = headless
        self.stealth = stealth

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
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
                    landmark = await scraper.select_landmark_by_min_distance(
                        place_url, min_distance_m=0,
                        random_pick=True, max_candidates=5,
                    )

            if landmark is None:
                raise ModuleError(f"No nearby landmarks found: {place_url}")

            result: Dict[str, Any] = {
                "landmark_name": landmark.name,
                "landmark_index": landmark.index,
            }

            if landmark.place_id:
                result["landmark_id"] = landmark.place_id
            if landmark.distance_m is not None:
                result["landmark_distance_m"] = landmark.distance_m

            return result

        except NaverMapScraperError as e:
            raise ModuleError(f"Landmark extraction failed: {str(e)}")
        except ModuleError:
            raise
        except Exception as e:
            raise ModuleError(f"Landmark module error: {str(e)}")

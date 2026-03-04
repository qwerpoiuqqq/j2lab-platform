"""Walking steps calculation module.

Calculates walking steps from a landmark to the place via Naver Map directions.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.modules.base import BaseModule, ModuleError
from app.services.naver_map import NaverMapScraper, NaverMapScraperError


class StepsModule(BaseModule):
    """Calculate walking steps from start to destination.

    Start location priority:
        1. context["steps_start"] (explicitly specified)
        2. context["landmark_name"] (from landmark module)

    Input (context):
        - place_name: Destination place name (required)
        - landmark_name or steps_start: Start location (at least one required)
        - real_place_name: Actual registered name (used if available)
        - place_area: Area hint for autocomplete validation (optional)

    Output:
        - steps: Walking steps count (integer)
    """

    module_id: str = "steps"
    description: str = "출발지→업체 도보 걸음수 계산"
    output_variables: List[str] = ["steps"]
    dependencies: List[str] = ["landmark", "place_info"]

    def __init__(self, headless: bool = True, stealth: bool = True):
        self.headless = headless
        self.stealth = stealth

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_context(context, ["place_name"])

        start = context.get("steps_start") or context.get("landmark_name")
        if not start:
            raise ModuleError(
                "Cannot determine start location: steps_start or landmark_name required"
            )

        destination = context.get("real_place_name") or context["place_name"]
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
            raise ModuleError(f"Walking steps calculation failed: {str(e)}")
        except ModuleError:
            raise
        except Exception as e:
            raise ModuleError(f"Steps module error: {str(e)}")

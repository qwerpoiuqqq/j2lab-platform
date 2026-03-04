"""Place info extraction module.

Extracts real place name, address, and area from Naver Place URL.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.modules.base import BaseModule, ModuleError
from app.services.naver_map import NaverMapScraper, NaverMapScraperError


class PlaceInfoModule(BaseModule):
    """Extract real place name and address from place URL.

    Input (context):
        - place_url: Naver Place URL (required)

    Output:
        - real_place_name: Registered place name
        - place_address: Place address
        - place_area: City/district level area (for autocomplete validation)
    """

    module_id: str = "place_info"
    description: str = "플레이스 실제 상호명/주소 추출"
    output_variables: List[str] = []  # Internal variables only
    dependencies: List[str] = []

    def __init__(self, headless: bool = True, stealth: bool = True):
        self.headless = headless
        self.stealth = stealth

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_context(context, ["place_url"])
        place_url = context["place_url"]

        try:
            async with NaverMapScraper(
                headless=self.headless, stealth=self.stealth
            ) as scraper:
                place_info = await scraper.get_place_info(place_url)

            result: Dict[str, Any] = {}
            if place_info.name:
                result["real_place_name"] = place_info.name
            if place_info.address:
                result["place_address"] = place_info.address
            if place_info.area:
                result["place_area"] = place_info.area
            if place_info.image_url:
                result["place_image_url"] = place_info.image_url

            return result

        except NaverMapScraperError as e:
            raise ModuleError(f"Place info extraction failed: {str(e)}")
        except Exception as e:
            raise ModuleError(f"place_info module error: {str(e)}")

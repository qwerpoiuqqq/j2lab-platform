"""플레이스 상호명/주소 추출 모듈."""

from typing import Any, Dict, List

from app.modules.base import BaseModule, ModuleError
from app.services.naver_map import NaverMapScraper, NaverMapScraperError


class PlaceInfoModule(BaseModule):
    """플레이스 URL에서 실제 상호명과 주소를 추출하는 모듈.

    Input (context):
        - place_url: 플레이스 URL (필수)

    Output:
        - real_place_name: 플레이스에 등록된 실제 상호명
        - place_address: 플레이스 주소
        - place_area: 플레이스 지역 (시/구 레벨, 주소 검증용)
    """

    module_id: str = "place_info"
    description: str = "플레이스 실제 상호명/주소 추출"
    output_variables: List[str] = []  # 내부용 변수만 (템플릿 가이드에 노출 안 함)
    dependencies: List[str] = []

    def __init__(self, headless: bool = True, stealth: bool = True):
        self.headless = headless
        self.stealth = stealth

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """상호명/주소 추출 실행."""
        self.validate_context(context, ["place_url"])

        place_url = context["place_url"]

        try:
            async with NaverMapScraper(
                headless=self.headless, stealth=self.stealth
            ) as scraper:
                place_info = await scraper.get_place_info(place_url)

            result = {}
            if place_info.name:
                result["real_place_name"] = place_info.name
            if place_info.address:
                result["place_address"] = place_info.address
            if place_info.area:
                result["place_area"] = place_info.area

            return result

        except NaverMapScraperError as e:
            raise ModuleError(f"상호명/주소 추출 실패: {str(e)}")
        except Exception as e:
            raise ModuleError(f"place_info 모듈 실행 중 오류: {str(e)}")

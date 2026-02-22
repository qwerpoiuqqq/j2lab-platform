"""캠페인 폼 관련 테스트."""

import pytest
from app.services.superap import (
    CampaignFormData,
    CampaignFormResult,
    SuperapCampaignError,
)


class TestCampaignFormData:
    """CampaignFormData 테스트."""

    def test_template_replacement_place_name(self):
        """상호명 템플릿 치환 테스트 (마스킹 적용됨)."""
        form_data = CampaignFormData(
            campaign_name="테스트 캠페인",
            place_name="맛있는식당",
            landmark_name="서울타워",
            participation_guide="&상호명&에서 사진을 찍어주세요",
            keywords=["키워드1"],
            hint="힌트",
            walking_steps=1000,
        )
        # 상호명 마스킹: "맛있는식당" -> "맛X는X당" (2글자마다 X)
        assert "맛X는X당에서 사진을 찍어주세요" == form_data.processed_guide

    def test_template_replacement_landmark_name(self):
        """명소명 템플릿 치환 테스트."""
        form_data = CampaignFormData(
            campaign_name="테스트 캠페인",
            place_name="맛있는식당",
            landmark_name="서울타워",
            participation_guide="&명소명&에서 출발하세요",
            keywords=["키워드1"],
            hint="힌트",
            walking_steps=1000,
        )
        assert "서울타워에서 출발하세요" == form_data.processed_guide

    def test_template_replacement_both(self):
        """상호명과 명소명 동시 치환 테스트 (마스킹 적용됨)."""
        form_data = CampaignFormData(
            campaign_name="테스트 캠페인",
            place_name="맛있는식당",
            landmark_name="서울타워",
            participation_guide="&명소명&에서 &상호명&까지 걸어오세요",
            keywords=["키워드1"],
            hint="힌트",
            walking_steps=1000,
        )
        # 상호명 마스킹: "맛있는식당" -> "맛X는X당"
        assert "서울타워에서 맛X는X당까지 걸어오세요" == form_data.processed_guide

    def test_keywords_255_limit_under(self):
        """키워드가 255자 미만인 경우."""
        keywords = ["키워드1", "키워드2", "키워드3"]
        form_data = CampaignFormData(
            campaign_name="테스트",
            place_name="식당",
            landmark_name="타워",
            participation_guide="참여",
            keywords=keywords,
            hint="힌트",
            walking_steps=1000,
        )
        assert form_data.processed_keywords == "키워드1,키워드2,키워드3"
        assert len(form_data.processed_keywords) <= 255

    def test_keywords_255_limit_over(self):
        """키워드가 255자를 초과하는 경우."""
        # 긴 키워드 생성
        keywords = [f"매우긴키워드{i}" for i in range(100)]
        form_data = CampaignFormData(
            campaign_name="테스트",
            place_name="식당",
            landmark_name="타워",
            participation_guide="참여",
            keywords=keywords,
            hint="힌트",
            walking_steps=1000,
        )
        assert len(form_data.processed_keywords) <= 255

    def test_keywords_empty(self):
        """빈 키워드 처리."""
        form_data = CampaignFormData(
            campaign_name="테스트",
            place_name="식당",
            landmark_name="타워",
            participation_guide="참여",
            keywords=[],
            hint="힌트",
            walking_steps=1000,
        )
        assert form_data.processed_keywords == ""
        assert form_data.get_keywords_count() == 0

    def test_keywords_count(self):
        """키워드 개수 카운트."""
        keywords = ["키워드1", "키워드2", "키워드3"]
        form_data = CampaignFormData(
            campaign_name="테스트",
            place_name="식당",
            landmark_name="타워",
            participation_guide="참여",
            keywords=keywords,
            hint="힌트",
            walking_steps=1000,
        )
        assert form_data.get_keywords_count() == 3

    def test_keywords_strip_whitespace(self):
        """키워드 공백 제거."""
        keywords = ["  키워드1  ", "키워드2", "  "]
        form_data = CampaignFormData(
            campaign_name="테스트",
            place_name="식당",
            landmark_name="타워",
            participation_guide="참여",
            keywords=keywords,
            hint="힌트",
            walking_steps=1000,
        )
        assert form_data.processed_keywords == "키워드1,키워드2"

    def test_place_name_masking(self):
        """상호명 마스킹 테스트."""
        form_data = CampaignFormData(
            campaign_name="테스트",
            place_name="일류곱창 마포공덕본점",
            landmark_name="타워",
            participation_guide="&상호명&",
            keywords=["키워드"],
            hint="힌트",
            walking_steps=1000,
        )
        # "일류곱창 마포공덕본점" -> "일X곱X 마X공X본X" (공백은 유지, 2글자마다 X)
        assert form_data.processed_guide == "일X곱X 마X공X본X"


class TestCampaignFormResult:
    """CampaignFormResult 테스트."""

    def test_default_values(self):
        """기본값 확인."""
        result = CampaignFormResult(success=False)
        assert result.success is False
        assert result.screenshot_path is None
        assert result.filled_fields == []
        assert result.errors == []

    def test_with_values(self):
        """값 설정 확인."""
        result = CampaignFormResult(
            success=True,
            screenshot_path="/path/to/screenshot.png",
            filled_fields=["campaign_name", "keywords"],
            errors=[],
        )
        assert result.success is True
        assert result.screenshot_path == "/path/to/screenshot.png"
        assert len(result.filled_fields) == 2


class TestCampaignSelectors:
    """캠페인 셀렉터 테스트."""

    def test_campaign_selectors_defined(self):
        """캠페인 셀렉터가 정의되어 있는지 확인."""
        from app.services.superap import SuperapController

        assert "campaign_name" in SuperapController.CAMPAIGN_SELECTORS
        assert "participation_guide" in SuperapController.CAMPAIGN_SELECTORS
        assert "keywords" in SuperapController.CAMPAIGN_SELECTORS
        assert "hint" in SuperapController.CAMPAIGN_SELECTORS
        # walking_steps -> conversion_input으로 변경됨
        assert "conversion_input" in SuperapController.CAMPAIGN_SELECTORS
        assert "submit_button" in SuperapController.CAMPAIGN_SELECTORS

    def test_campaign_url_defined(self):
        """캠페인 URL이 정의되어 있는지 확인."""
        from app.services.superap import SuperapController

        assert hasattr(SuperapController, "CAMPAIGN_CREATE_URL")
        # URL에 adver/add가 포함되어 있는지 확인
        assert "adver/add" in SuperapController.CAMPAIGN_CREATE_URL.lower()

"""캠페인 등록 서비스 테스트.

Phase 3 - Task 3.3: 캠페인 등록 전체 플로우 테스트
"""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.campaign_registration import (
    CampaignRegistrationData,
    CampaignRegistrationResult,
    CampaignRegistrationService,
    CampaignRegistrationError,
    register_campaign,
)
from app.services.superap import (
    CampaignFormData,
    CampaignFormResult,
    SubmitResult,
    SuperapController,
    SuperapCampaignError,
)
from app.models.campaign import Campaign
from app.models.keyword import KeywordPool
from app.models.template import CampaignTemplate


# ============================================================================
# CampaignRegistrationData 테스트
# ============================================================================

class TestCampaignRegistrationData:
    """CampaignRegistrationData 데이터 클래스 테스트."""

    def test_basic_creation(self):
        """기본 데이터 생성 테스트."""
        data = CampaignRegistrationData(
            place_name="일류곱창 마포공덕본점",
            place_url="https://m.place.naver.com/restaurant/1724563569",
            campaign_type="트래픽",
            keywords=["일류곱창", "마포공덕맛집", "곱창맛집"],
            start_date=date(2026, 2, 5),
            end_date=date(2026, 2, 11),
        )

        assert data.place_name == "일류곱창 마포공덕본점"
        assert data.campaign_type == "트래픽"
        assert len(data.keywords) == 3
        assert data.daily_limit == 300  # 기본값

    def test_total_limit_auto_calculation(self):
        """전체 한도 자동 계산 테스트."""
        data = CampaignRegistrationData(
            place_name="테스트",
            place_url="https://test.com",
            campaign_type="트래픽",
            keywords=["키워드1"],
            start_date=date(2026, 2, 5),
            end_date=date(2026, 2, 11),  # 7일
            daily_limit=300,
        )

        # 7일 * 300 = 2100
        assert data.total_limit == 2100

    def test_total_limit_explicit(self):
        """명시적 전체 한도 설정 테스트."""
        data = CampaignRegistrationData(
            place_name="테스트",
            place_url="https://test.com",
            campaign_type="트래픽",
            keywords=["키워드1"],
            start_date=date(2026, 2, 5),
            end_date=date(2026, 2, 11),
            daily_limit=300,
            total_limit=5000,  # 명시적 설정
        )

        # 명시적 값 유지
        assert data.total_limit == 5000


class TestCampaignRegistrationResult:
    """CampaignRegistrationResult 데이터 클래스 테스트."""

    def test_success_result(self):
        """성공 결과 테스트."""
        result = CampaignRegistrationResult(
            success=True,
            campaign_code="1234567",
            campaign_id=1,
        )

        assert result.success is True
        assert result.campaign_code == "1234567"
        assert result.campaign_id == 1
        assert result.error_message is None

    def test_failure_result(self):
        """실패 결과 테스트."""
        result = CampaignRegistrationResult(
            success=False,
            error_message="템플릿을 찾을 수 없습니다",
        )

        assert result.success is False
        assert result.error_message == "템플릿을 찾을 수 없습니다"
        assert result.campaign_code is None


# ============================================================================
# CampaignRegistrationService 테스트
# ============================================================================

class TestCampaignRegistrationService:
    """CampaignRegistrationService 테스트."""

    @pytest.fixture
    def mock_superap(self):
        """Mock SuperapController."""
        controller = MagicMock(spec=SuperapController)
        controller.fill_campaign_form = AsyncMock(return_value=CampaignFormResult(
            success=True,
            filled_fields=["campaign_name", "keywords", "hint", "dates", "budget", "links"],
            screenshot_path="screenshots/test.png",
        ))
        controller.submit_campaign = AsyncMock(return_value=SubmitResult(
            success=True,
            redirect_url="https://superap.io/service/reward/adver/report",
        ))
        controller.extract_campaign_code = AsyncMock(return_value="1234567")
        return controller

    @pytest.fixture
    def mock_db(self):
        """Mock DB Session."""
        db = MagicMock()

        # 템플릿 mock
        template = MagicMock(spec=CampaignTemplate)
        template.type_name = "트래픽"
        template.modules = ["landmark", "steps"]
        template.description_template = "&명소명&에서 &상호명&까지 걸음수"
        template.hint_text = "출발지에서 목적지까지 걸음 수"
        template.links = ["https://link1.com", "https://link2.com"]
        template.conversion_text_template = None
        template.is_active = True

        db.query.return_value.filter.return_value.first.return_value = template

        # add, flush, commit, refresh mock
        db.add = MagicMock()
        db.flush = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()

        return db

    @pytest.fixture
    def sample_data(self):
        """샘플 등록 데이터."""
        return CampaignRegistrationData(
            place_name="일류곱창 마포공덕본점",
            place_url="https://m.place.naver.com/restaurant/1724563569",
            campaign_type="트래픽",
            keywords=["일류곱창", "마포공덕맛집", "곱창맛집"],
            start_date=date(2026, 2, 5),
            end_date=date(2026, 2, 11),
            agency_name="테스트대행사",
        )

    @pytest.mark.asyncio
    async def test_register_campaign_dry_run(self, mock_superap, mock_db, sample_data):
        """dry_run 모드 테스트 (폼 입력까지만)."""
        # 모듈 실행 mock
        with patch('app.services.campaign_registration.ModuleRegistry') as mock_registry:
            mock_registry.execute_modules = AsyncMock(return_value={
                "place_url": sample_data.place_url,
                "place_name": sample_data.place_name,
                "landmark_name": "마포역 2번출구",
                "landmark_id": "12345",
                "steps": 863,
            })

            service = CampaignRegistrationService(mock_superap, mock_db)
            result = await service.register_campaign(
                account_id="test_account",
                data=sample_data,
                db_account_id=1,
                dry_run=True,
            )

        assert result.success is True
        assert "dry_run" in result.error_message
        assert result.module_context["landmark_name"] == "마포역 2번출구"
        assert result.module_context["steps"] == 863

        # 폼 입력은 호출됨
        mock_superap.fill_campaign_form.assert_called_once()
        # 제출은 호출되지 않음
        mock_superap.submit_campaign.assert_not_called()

    @pytest.mark.asyncio
    async def test_register_campaign_full_flow(self, mock_superap, mock_db, sample_data):
        """전체 플로우 테스트."""
        with patch('app.services.campaign_registration.ModuleRegistry') as mock_registry:
            mock_registry.execute_modules = AsyncMock(return_value={
                "place_url": sample_data.place_url,
                "place_name": sample_data.place_name,
                "landmark_name": "마포역 2번출구",
                "steps": 863,
            })

            service = CampaignRegistrationService(mock_superap, mock_db)
            result = await service.register_campaign(
                account_id="test_account",
                data=sample_data,
                db_account_id=1,
                dry_run=False,
            )

        assert result.success is True
        assert result.campaign_code == "1234567"

        # 모든 단계 호출 확인
        mock_superap.fill_campaign_form.assert_called_once()
        mock_superap.submit_campaign.assert_called_once()
        mock_superap.extract_campaign_code.assert_called_once()

        # DB 저장 확인
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_template_not_found(self, mock_superap, mock_db, sample_data):
        """템플릿을 찾을 수 없는 경우 테스트."""
        # 템플릿 없음
        mock_db.query.return_value.filter.return_value.first.return_value = None

        service = CampaignRegistrationService(mock_superap, mock_db)
        result = await service.register_campaign(
            account_id="test_account",
            data=sample_data,
            db_account_id=1,
        )

        assert result.success is False
        assert "템플릿을 찾을 수 없습니다" in result.error_message

    @pytest.mark.asyncio
    async def test_form_fill_failure(self, mock_superap, mock_db, sample_data):
        """폼 입력 실패 테스트."""
        mock_superap.fill_campaign_form = AsyncMock(return_value=CampaignFormResult(
            success=False,
            errors=["캠페인 이름 입력 실패", "키워드 입력 실패"],
        ))

        with patch('app.services.campaign_registration.ModuleRegistry') as mock_registry:
            mock_registry.execute_modules = AsyncMock(return_value={
                "place_name": sample_data.place_name,
                "landmark_name": "마포역",
                "steps": 863,
            })

            service = CampaignRegistrationService(mock_superap, mock_db)
            result = await service.register_campaign(
                account_id="test_account",
                data=sample_data,
                db_account_id=1,
            )

        assert result.success is False
        assert "폼 입력 실패" in result.error_message

    @pytest.mark.asyncio
    async def test_submit_failure(self, mock_superap, mock_db, sample_data):
        """제출 실패 테스트."""
        mock_superap.submit_campaign = AsyncMock(return_value=SubmitResult(
            success=False,
            error_message="등록 버튼을 찾을 수 없습니다",
        ))

        with patch('app.services.campaign_registration.ModuleRegistry') as mock_registry:
            mock_registry.execute_modules = AsyncMock(return_value={
                "place_name": sample_data.place_name,
                "landmark_name": "마포역",
                "steps": 863,
            })

            service = CampaignRegistrationService(mock_superap, mock_db)
            result = await service.register_campaign(
                account_id="test_account",
                data=sample_data,
                db_account_id=1,
            )

        assert result.success is False
        assert "제출 실패" in result.error_message


class TestCampaignNameGeneration:
    """캠페인 이름 생성 테스트."""

    @pytest.fixture
    def mock_superap(self):
        return MagicMock(spec=SuperapController)

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    def test_traffic_campaign_name(self, mock_superap, mock_db):
        """트래픽 타입 캠페인 이름 생성."""
        service = CampaignRegistrationService(mock_superap, mock_db)

        name = service._generate_campaign_name("일류곱창 마포공덕본점", "traffic")
        assert name == "일류 마포 퀴즈 맞추기"

    def test_save_campaign_name(self, mock_superap, mock_db):
        """저장하기 타입 캠페인 이름 생성."""
        service = CampaignRegistrationService(mock_superap, mock_db)

        name = service._generate_campaign_name("일류곱창 마포공덕본점", "save")
        assert name == "일류 마포 저장 퀴즈 맞추기"

    def test_short_place_name(self, mock_superap, mock_db):
        """짧은 상호명 처리."""
        service = CampaignRegistrationService(mock_superap, mock_db)

        name = service._generate_campaign_name("AB", "traffic")
        assert name == "A 퀴즈 맞추기"

    def test_single_char_place_name(self, mock_superap, mock_db):
        """한 글자 상호명 처리."""
        service = CampaignRegistrationService(mock_superap, mock_db)

        name = service._generate_campaign_name("A", "traffic")
        assert name == "A 퀴즈 맞추기"


# ============================================================================
# SubmitResult 테스트
# ============================================================================

class TestSubmitResult:
    """SubmitResult 데이터 클래스 테스트."""

    def test_success_result(self):
        """성공 결과."""
        result = SubmitResult(
            success=True,
            redirect_url="https://superap.io/service/reward/adver/report",
        )

        assert result.success is True
        assert result.error_message is None

    def test_failure_result(self):
        """실패 결과."""
        result = SubmitResult(
            success=False,
            error_message="등록 버튼을 찾을 수 없습니다",
        )

        assert result.success is False
        assert result.error_message == "등록 버튼을 찾을 수 없습니다"


# ============================================================================
# 편의 함수 테스트
# ============================================================================

class TestRegisterCampaignFunction:
    """register_campaign 편의 함수 테스트."""

    @pytest.mark.asyncio
    async def test_convenience_function(self):
        """편의 함수 테스트."""
        mock_superap = MagicMock(spec=SuperapController)
        mock_superap.fill_campaign_form = AsyncMock(return_value=CampaignFormResult(
            success=True,
            filled_fields=["field1", "field2", "field3", "field4", "field5"],
        ))
        mock_superap.submit_campaign = AsyncMock(return_value=SubmitResult(success=True))
        mock_superap.extract_campaign_code = AsyncMock(return_value="9999999")

        mock_db = MagicMock()
        template = MagicMock()
        template.modules = []
        template.description_template = "테스트"
        template.hint_text = "힌트"
        template.links = []
        template.is_active = True
        template.conversion_text_template = None
        mock_db.query.return_value.filter.return_value.first.return_value = template

        data = CampaignRegistrationData(
            place_name="테스트",
            place_url="https://test.com",
            campaign_type="트래픽",
            keywords=["키워드"],
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
        )

        with patch('app.services.campaign_registration.ModuleRegistry') as mock_registry:
            mock_registry.execute_modules = AsyncMock(return_value={
                "place_name": "테스트",
            })

            result = await register_campaign(
                superap_controller=mock_superap,
                db=mock_db,
                account_id="test",
                data=data,
                db_account_id=1,
            )

        assert result.success is True
        assert result.campaign_code == "9999999"


# ============================================================================
# 통합 테스트 (모듈 + 템플릿 + 등록)
# ============================================================================

class TestIntegration:
    """통합 테스트."""

    @pytest.mark.asyncio
    async def test_full_registration_flow_with_modules(self):
        """모듈 실행 포함 전체 플로우."""
        # Mock 설정
        mock_superap = MagicMock(spec=SuperapController)
        mock_superap.fill_campaign_form = AsyncMock(return_value=CampaignFormResult(
            success=True,
            filled_fields=["campaign_type", "campaign_name", "guide", "keywords", "hint", "budget"],
        ))
        mock_superap.submit_campaign = AsyncMock(return_value=SubmitResult(success=True))
        mock_superap.extract_campaign_code = AsyncMock(return_value="1336101")

        mock_db = MagicMock()
        template = MagicMock()
        template.type_name = "트래픽"
        template.modules = ["landmark", "steps"]
        template.description_template = "&명소명&에서 &상호명&까지 &걸음수& 걸음"
        template.hint_text = "걸음 수 맞추기"
        template.links = ["https://link1.com"]
        template.is_active = True
        template.conversion_text_template = None
        mock_db.query.return_value.filter.return_value.first.return_value = template

        data = CampaignRegistrationData(
            place_name="일류곱창",
            place_url="https://m.place.naver.com/restaurant/1724563569",
            campaign_type="트래픽",
            keywords=["일류곱창", "마포맛집"],
            start_date=date(2026, 2, 5),
            end_date=date(2026, 2, 11),
            agency_name="테스트대행사",
        )

        with patch('app.services.campaign_registration.ModuleRegistry') as mock_registry:
            mock_registry.execute_modules = AsyncMock(return_value={
                "place_url": data.place_url,
                "place_name": data.place_name,
                "landmark_name": "마포역 2번출구",
                "landmark_id": "12345",
                "steps": 863,
            })

            result = await register_campaign(
                superap_controller=mock_superap,
                db=mock_db,
                account_id="test",
                data=data,
                db_account_id=1,
            )

        # 결과 검증
        assert result.success is True
        assert result.campaign_code == "1336101"
        assert result.module_context["landmark_name"] == "마포역 2번출구"
        assert result.module_context["steps"] == 863

        # 폼 데이터 검증
        call_args = mock_superap.fill_campaign_form.call_args
        form_data = call_args[1]["form_data"]
        assert form_data.walking_steps == 863
        assert form_data.landmark_name == "마포역 2번출구"

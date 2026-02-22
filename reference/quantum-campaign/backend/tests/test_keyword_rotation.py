"""키워드 자동 변경 로직 테스트.

Phase 3 - Task 3.7: rotate_keywords, sync_campaign_status, scheduler 테스트.
"""

import pytest
from datetime import datetime, date, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from app.models.campaign import Campaign
from app.models.keyword import KeywordPool
from app.models.account import Account
from app.services.keyword_rotation import (
    rotate_keywords,
    sync_campaign_status,
    sync_all_campaign_statuses,
    should_rotate_at_2350,
)

KST = ZoneInfo("Asia/Seoul")


# ──────────────────────────────────────
# Fixtures
# ──────────────────────────────────────

@pytest.fixture
def mock_superap():
    """Mock SuperapController."""
    controller = AsyncMock()
    controller.edit_campaign_keywords = AsyncMock(return_value=True)
    controller.get_campaign_status = AsyncMock(return_value="진행중")
    controller.get_all_campaign_statuses = AsyncMock(return_value={})
    return controller


@pytest.fixture
def sample_account(db_session):
    """테스트 계정 생성."""
    account = Account(
        user_id="test_user",
        password_encrypted="test_password",
        agency_name="테스트 대행사",
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


@pytest.fixture
def sample_campaign(db_session, sample_account):
    """테스트 캠페인 생성."""
    campaign = Campaign(
        campaign_code="1234567",
        account_id=sample_account.id,
        place_name="테스트 플레이스",
        place_url="https://m.place.naver.com/restaurant/12345",
        place_id="12345",
        campaign_type="트래픽",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
        daily_limit=300,
        total_limit=9300,
        status="active",
    )
    db_session.add(campaign)
    db_session.commit()
    db_session.refresh(campaign)
    return campaign


@pytest.fixture
def sample_keywords(db_session, sample_campaign):
    """테스트 키워드 풀 생성 (미사용 10개)."""
    keywords = []
    kw_list = [
        "마포 곱창", "공덕역 맛집", "곱창 맛집", "서울 곱창",
        "마포구 맛집", "공덕 곱창", "홍대 곱창", "여의도 맛집",
        "마포역 맛집", "신촌 곱창",
    ]
    for kw in kw_list:
        kp = KeywordPool(
            campaign_id=sample_campaign.id,
            keyword=kw,
            is_used=False,
        )
        db_session.add(kp)
        keywords.append(kp)
    db_session.commit()
    return keywords


# ──────────────────────────────────────
# rotate_keywords 테스트
# ──────────────────────────────────────

class TestRotateKeywords:
    """rotate_keywords 함수 테스트."""

    @pytest.mark.asyncio
    async def test_rotate_keywords_success(
        self, db_session, sample_campaign, sample_keywords, mock_superap
    ):
        """키워드 변경 성공."""
        result = await rotate_keywords(
            campaign_id=sample_campaign.id,
            db=db_session,
            superap_controller=mock_superap,
            trigger_type="daily_exhausted",
        )

        assert result["success"] is True
        assert result["keywords_used"] > 0
        assert result["keywords_str"]
        assert len(result["keywords_str"]) <= 255

        # superap 호출 확인
        mock_superap.edit_campaign_keywords.assert_called_once()
        call_args = mock_superap.edit_campaign_keywords.call_args
        assert call_args.kwargs["campaign_code"] == "1234567"
        assert len(call_args.kwargs["new_keywords"]) <= 255

    @pytest.mark.asyncio
    async def test_rotate_keywords_updates_keyword_pool(
        self, db_session, sample_campaign, sample_keywords, mock_superap
    ):
        """키워드 변경 후 KeywordPool is_used 업데이트."""
        result = await rotate_keywords(
            campaign_id=sample_campaign.id,
            db=db_session,
            superap_controller=mock_superap,
        )

        assert result["success"] is True

        used_count = db_session.query(KeywordPool).filter(
            KeywordPool.campaign_id == sample_campaign.id,
            KeywordPool.is_used == True,
        ).count()

        assert used_count == result["keywords_used"]
        assert used_count > 0

        # used_at 확인
        used_keyword = db_session.query(KeywordPool).filter(
            KeywordPool.campaign_id == sample_campaign.id,
            KeywordPool.is_used == True,
        ).first()
        assert used_keyword.used_at is not None

    @pytest.mark.asyncio
    async def test_rotate_keywords_updates_last_keyword_change(
        self, db_session, sample_campaign, sample_keywords, mock_superap
    ):
        """키워드 변경 후 campaign.last_keyword_change 업데이트."""
        assert sample_campaign.last_keyword_change is None

        result = await rotate_keywords(
            campaign_id=sample_campaign.id,
            db=db_session,
            superap_controller=mock_superap,
            trigger_type="daily_exhausted",
        )

        assert result["success"] is True
        db_session.refresh(sample_campaign)
        assert sample_campaign.last_keyword_change is not None

    @pytest.mark.asyncio
    async def test_rotate_keywords_time_2350_fixed_time(
        self, db_session, sample_campaign, sample_keywords, mock_superap
    ):
        """23:50 트리거 시 last_keyword_change가 KST 23:50:00의 UTC 변환값으로 저장."""
        result = await rotate_keywords(
            campaign_id=sample_campaign.id,
            db=db_session,
            superap_controller=mock_superap,
            trigger_type="time_2350",
        )

        assert result["success"] is True
        db_session.refresh(sample_campaign)

        last_change = sample_campaign.last_keyword_change
        assert last_change is not None
        # KST 23:50 = UTC 14:50
        if last_change.tzinfo is not None:
            last_change_kst = last_change.astimezone(KST)
        else:
            last_change_kst = last_change.replace(tzinfo=timezone.utc).astimezone(KST)
        assert last_change_kst.hour == 23
        assert last_change_kst.minute == 50
        assert last_change_kst.second == 0

    @pytest.mark.asyncio
    async def test_rotate_keywords_255_char_limit(
        self, db_session, sample_campaign, mock_superap
    ):
        """키워드 문자열이 255자를 초과하지 않음."""
        # 긴 키워드 많이 추가
        for i in range(50):
            kp = KeywordPool(
                campaign_id=sample_campaign.id,
                keyword=f"매우긴키워드테스트용입니다번호{i:03d}",
                is_used=False,
            )
            db_session.add(kp)
        db_session.commit()

        result = await rotate_keywords(
            campaign_id=sample_campaign.id,
            db=db_session,
            superap_controller=mock_superap,
        )

        assert result["success"] is True
        assert len(result["keywords_str"]) <= 255

    @pytest.mark.asyncio
    async def test_rotate_keywords_no_keywords_at_all(
        self, db_session, sample_campaign, mock_superap
    ):
        """키워드 풀 자체가 비어있는 경우."""
        result = await rotate_keywords(
            campaign_id=sample_campaign.id,
            db=db_session,
            superap_controller=mock_superap,
        )

        assert result["success"] is False
        assert "비어있습니다" in result["message"]
        assert result["remaining"] == 0

    @pytest.mark.asyncio
    async def test_rotate_keywords_all_keywords_already_used_recycles(
        self, db_session, sample_campaign, mock_superap
    ):
        """모든 키워드가 이미 사용된 경우 → 재활용 성공."""
        for kw in ["키워드A", "키워드B"]:
            kp = KeywordPool(
                campaign_id=sample_campaign.id,
                keyword=kw,
                is_used=True,
                used_at=datetime.now(timezone.utc),
            )
            db_session.add(kp)
        db_session.commit()

        result = await rotate_keywords(
            campaign_id=sample_campaign.id,
            db=db_session,
            superap_controller=mock_superap,
        )

        assert result["success"] is True
        assert result["recycled"] is True
        assert result["keywords_used"] > 0

    @pytest.mark.asyncio
    async def test_rotate_keywords_campaign_not_found(
        self, db_session, mock_superap
    ):
        """존재하지 않는 캠페인."""
        result = await rotate_keywords(
            campaign_id=99999,
            db=db_session,
            superap_controller=mock_superap,
        )

        assert result["success"] is False
        assert "찾을 수 없습니다" in result["message"]

    @pytest.mark.asyncio
    async def test_rotate_keywords_no_campaign_code(
        self, db_session, sample_account, mock_superap
    ):
        """캠페인 코드가 없는 경우."""
        campaign = Campaign(
            campaign_code=None,
            account_id=sample_account.id,
            place_name="코드없는 캠페인",
            place_url="https://m.place.naver.com/restaurant/99999",
            campaign_type="트래픽",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            daily_limit=300,
            status="active",
        )
        db_session.add(campaign)
        db_session.commit()

        result = await rotate_keywords(
            campaign_id=campaign.id,
            db=db_session,
            superap_controller=mock_superap,
        )

        assert result["success"] is False
        assert "캠페인 코드" in result["message"]

    @pytest.mark.asyncio
    async def test_rotate_keywords_superap_failure(
        self, db_session, sample_campaign, sample_keywords, mock_superap
    ):
        """superap 키워드 수정 실패 시."""
        mock_superap.edit_campaign_keywords = AsyncMock(return_value=False)

        result = await rotate_keywords(
            campaign_id=sample_campaign.id,
            db=db_session,
            superap_controller=mock_superap,
        )

        assert result["success"] is False
        assert "수정 실패" in result["message"]

        # KeywordPool은 변경되지 않아야 함
        used_count = db_session.query(KeywordPool).filter(
            KeywordPool.campaign_id == sample_campaign.id,
            KeywordPool.is_used == True,
        ).count()
        assert used_count == 0

    @pytest.mark.asyncio
    async def test_rotate_keywords_superap_exception(
        self, db_session, sample_campaign, sample_keywords, mock_superap
    ):
        """superap 호출 중 예외 발생 시."""
        mock_superap.edit_campaign_keywords = AsyncMock(
            side_effect=Exception("네트워크 오류")
        )

        result = await rotate_keywords(
            campaign_id=sample_campaign.id,
            db=db_session,
            superap_controller=mock_superap,
        )

        assert result["success"] is False
        assert "superap 수정 실패" in result["message"]

    @pytest.mark.asyncio
    async def test_rotate_keywords_remaining_count(
        self, db_session, sample_campaign, sample_keywords, mock_superap
    ):
        """변경 후 남은 키워드 수 정확한지 확인."""
        total = len(sample_keywords)

        result = await rotate_keywords(
            campaign_id=sample_campaign.id,
            db=db_session,
            superap_controller=mock_superap,
        )

        assert result["success"] is True
        assert result["remaining"] == total - result["keywords_used"]

    @pytest.mark.asyncio
    async def test_rotate_keywords_no_account(
        self, db_session, mock_superap
    ):
        """계정이 없는 캠페인."""
        campaign = Campaign(
            campaign_code="9999999",
            account_id=9999,
            place_name="계정없음",
            place_url="https://m.place.naver.com/restaurant/11111",
            campaign_type="트래픽",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            daily_limit=300,
            status="active",
        )
        db_session.add(campaign)
        kp = KeywordPool(
            campaign_id=None,  # 임시
            keyword="테스트",
            is_used=False,
        )
        db_session.add(campaign)
        db_session.commit()
        db_session.refresh(campaign)

        # 키워드 추가
        kp = KeywordPool(
            campaign_id=campaign.id,
            keyword="테스트키워드",
            is_used=False,
        )
        db_session.add(kp)
        db_session.commit()

        result = await rotate_keywords(
            campaign_id=campaign.id,
            db=db_session,
            superap_controller=mock_superap,
        )

        assert result["success"] is False
        assert "계정" in result["message"]

    @pytest.mark.asyncio
    async def test_rotate_keywords_comma_separated_no_spaces(
        self, db_session, sample_campaign, mock_superap
    ):
        """키워드 문자열이 쉼표 구분, 공백 없이 생성되는지 확인."""
        for kw in ["키워드A", "키워드B", "키워드C"]:
            kp = KeywordPool(
                campaign_id=sample_campaign.id,
                keyword=kw,
                is_used=False,
            )
            db_session.add(kp)
        db_session.commit()

        result = await rotate_keywords(
            campaign_id=sample_campaign.id,
            db=db_session,
            superap_controller=mock_superap,
        )

        assert result["success"] is True
        # 쉼표 구분 확인, 공백 없음
        keywords_str = result["keywords_str"]
        assert ", " not in keywords_str  # 쉼표 뒤에 공백 없어야 함
        parts = keywords_str.split(",")
        for part in parts:
            assert part == part.strip()  # 각 키워드에 앞뒤 공백 없음


# ──────────────────────────────────────
# sync_campaign_status 테스트
# ──────────────────────────────────────

class TestSyncCampaignStatus:
    """sync_campaign_status 함수 테스트."""

    @pytest.mark.asyncio
    async def test_sync_status_to_active(
        self, db_session, sample_campaign, mock_superap
    ):
        """상태를 '진행중'으로 동기화 → DB에 'active'로 정규화."""
        mock_superap.get_campaign_status = AsyncMock(return_value="진행중")

        result = await sync_campaign_status(
            campaign_id=sample_campaign.id,
            db=db_session,
            superap_controller=mock_superap,
        )

        assert result["success"] is True
        assert result["status"] == "active"
        assert result["previous_status"] == "active"

        db_session.refresh(sample_campaign)
        assert sample_campaign.status == "active"

    @pytest.mark.asyncio
    async def test_sync_status_to_daily_exhausted(
        self, db_session, sample_campaign, mock_superap
    ):
        """상태를 '일일소진'으로 동기화 → DB에 'daily_exhausted'로 정규화."""
        mock_superap.get_campaign_status = AsyncMock(return_value="일일소진")

        result = await sync_campaign_status(
            campaign_id=sample_campaign.id,
            db=db_session,
            superap_controller=mock_superap,
        )

        assert result["success"] is True
        assert result["status"] == "daily_exhausted"

        db_session.refresh(sample_campaign)
        assert sample_campaign.status == "daily_exhausted"

    @pytest.mark.asyncio
    async def test_sync_status_to_campaign_exhausted(
        self, db_session, sample_campaign, mock_superap
    ):
        """상태를 '캠페인소진'으로 동기화 → DB에 'campaign_exhausted'로 정규화."""
        mock_superap.get_campaign_status = AsyncMock(return_value="캠페인소진")

        result = await sync_campaign_status(
            campaign_id=sample_campaign.id,
            db=db_session,
            superap_controller=mock_superap,
        )

        assert result["success"] is True
        assert result["status"] == "campaign_exhausted"

    @pytest.mark.asyncio
    async def test_sync_status_campaign_not_found(
        self, db_session, mock_superap
    ):
        """존재하지 않는 캠페인."""
        result = await sync_campaign_status(
            campaign_id=99999,
            db=db_session,
            superap_controller=mock_superap,
        )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_sync_status_null_response(
        self, db_session, sample_campaign, mock_superap
    ):
        """superap에서 상태를 가져오지 못한 경우."""
        mock_superap.get_campaign_status = AsyncMock(return_value=None)

        result = await sync_campaign_status(
            campaign_id=sample_campaign.id,
            db=db_session,
            superap_controller=mock_superap,
        )

        assert result["success"] is False
        assert "확인할 수 없습니다" in result["message"]

    @pytest.mark.asyncio
    async def test_sync_status_exception(
        self, db_session, sample_campaign, mock_superap
    ):
        """superap 조회 중 예외 발생."""
        mock_superap.get_campaign_status = AsyncMock(
            side_effect=Exception("타임아웃")
        )

        result = await sync_campaign_status(
            campaign_id=sample_campaign.id,
            db=db_session,
            superap_controller=mock_superap,
        )

        assert result["success"] is False
        assert "상태 조회 실패" in result["message"]


# ──────────────────────────────────────
# sync_all_campaign_statuses 테스트
# ──────────────────────────────────────

class TestSyncAllCampaignStatuses:
    """sync_all_campaign_statuses 함수 테스트."""

    @pytest.mark.asyncio
    async def test_sync_all_statuses_with_conversions(
        self, db_session, sample_account, mock_superap
    ):
        """여러 캠페인 상태+전환수 동기화 (정규화 포함)."""
        c1 = Campaign(
            campaign_code="1000001",
            account_id=sample_account.id,
            place_name="업체1",
            place_url="https://m.place.naver.com/restaurant/1",
            campaign_type="트래픽",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            daily_limit=300,
            status="active",
            current_conversions=0,
        )
        c2 = Campaign(
            campaign_code="1000002",
            account_id=sample_account.id,
            place_name="업체2",
            place_url="https://m.place.naver.com/restaurant/2",
            campaign_type="트래픽",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            daily_limit=300,
            status="active",
            current_conversions=0,
        )
        db_session.add_all([c1, c2])
        db_session.commit()

        # get_campaign_status_with_conversions 모킹
        async def mock_get_status_with_conv(account_id, campaign_code):
            if campaign_code == "1000001":
                return {"status": "진행중", "current_count": 150, "total_count": 300}
            elif campaign_code == "1000002":
                return {"status": "일일소진", "current_count": 50, "total_count": 100}
            return None

        mock_superap.get_campaign_status_with_conversions = AsyncMock(
            side_effect=mock_get_status_with_conv
        )

        result = await sync_all_campaign_statuses(
            db=db_session,
            superap_controller=mock_superap,
            account_id=sample_account.id,
        )

        assert result["success"] is True

        db_session.refresh(c1)
        db_session.refresh(c2)
        # 상태가 영문으로 정규화됨
        assert c1.status == "active"  # 진행중 → active (변경 없음)
        assert c2.status == "daily_exhausted"  # 일일소진 → daily_exhausted
        # 전환수 업데이트
        assert c1.current_conversions == 150
        assert c2.current_conversions == 50

    @pytest.mark.asyncio
    async def test_sync_all_no_changes(
        self, db_session, sample_account, mock_superap
    ):
        """상태 변경이 없는 경우."""
        c1 = Campaign(
            campaign_code="2000001",
            account_id=sample_account.id,
            place_name="업체X",
            place_url="https://m.place.naver.com/restaurant/3",
            campaign_type="트래픽",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            daily_limit=300,
            status="active",
            current_conversions=100,
        )
        db_session.add(c1)
        db_session.commit()

        mock_superap.get_campaign_status_with_conversions = AsyncMock(
            return_value={"status": "진행중", "current_count": 100, "total_count": 300}
        )

        result = await sync_all_campaign_statuses(
            db=db_session,
            superap_controller=mock_superap,
            account_id=sample_account.id,
        )

        assert result["success"] is True
        assert result["synced_count"] == 0

    @pytest.mark.asyncio
    async def test_sync_all_empty_response(
        self, db_session, sample_account, mock_superap
    ):
        """superap에서 빈 결과 반환."""
        mock_superap.get_campaign_status_with_conversions = AsyncMock(return_value=None)

        result = await sync_all_campaign_statuses(
            db=db_session,
            superap_controller=mock_superap,
            account_id=sample_account.id,
        )

        assert result["success"] is True
        assert result["synced_count"] == 0


# ──────────────────────────────────────
# should_rotate_at_2350 테스트
# ──────────────────────────────────────

class TestShouldRotateAt2350:
    """should_rotate_at_2350 함수 테스트."""

    def test_no_last_change(self, db_session, sample_campaign):
        """last_keyword_change가 None이면 변경 필요."""
        sample_campaign.last_keyword_change = None
        assert should_rotate_at_2350(sample_campaign) is True

    def test_changed_yesterday(self, db_session, sample_campaign):
        """어제 변경됐으면 오늘 변경 필요."""
        # UTC로 저장 (KST 어제 23:50 = UTC 어제 14:50)
        yesterday_utc = datetime.now(timezone.utc) - timedelta(days=1)
        sample_campaign.last_keyword_change = yesterday_utc.replace(
            hour=14, minute=50, second=0, microsecond=0, tzinfo=None
        )
        assert should_rotate_at_2350(sample_campaign) is True

    def test_changed_today_before_2350(self, db_session, sample_campaign):
        """오늘 23:50 이전에 변경됐으면 변경 필요."""
        # KST 14:00 = UTC 05:00
        today_kst = datetime.now(KST)
        today_utc_equiv = today_kst.replace(
            hour=14, minute=0, second=0, microsecond=0
        ).astimezone(timezone.utc)
        sample_campaign.last_keyword_change = today_utc_equiv.replace(tzinfo=None)
        assert should_rotate_at_2350(sample_campaign) is True

    def test_changed_today_at_2350(self, db_session, sample_campaign):
        """오늘 KST 23:50에 이미 변경됐으면 변경 불필요."""
        # KST 23:50 = UTC 14:50
        today_kst = datetime.now(KST)
        kst_2350 = today_kst.replace(hour=23, minute=50, second=0, microsecond=0)
        utc_equiv = kst_2350.astimezone(timezone.utc)
        sample_campaign.last_keyword_change = utc_equiv.replace(tzinfo=None)
        assert should_rotate_at_2350(sample_campaign) is False

    def test_changed_today_after_2350(self, db_session, sample_campaign):
        """오늘 KST 23:55에 변경됐으면 변경 불필요."""
        today_kst = datetime.now(KST)
        kst_2355 = today_kst.replace(hour=23, minute=55, second=0, microsecond=0)
        utc_equiv = kst_2355.astimezone(timezone.utc)
        sample_campaign.last_keyword_change = utc_equiv.replace(tzinfo=None)
        assert should_rotate_at_2350(sample_campaign) is False


# ──────────────────────────────────────
# check_and_rotate_keywords 스케줄러 통합 테스트
# ──────────────────────────────────────

class TestCheckAndRotateKeywords:
    """check_and_rotate_keywords 통합 테스트."""

    @pytest.mark.asyncio
    async def test_scheduler_skips_when_no_active_accounts(self, db_session):
        """활성 계정이 없으면 건너뜀."""
        with patch("app.services.scheduler.SessionLocal", return_value=db_session), \
             patch("app.services.scheduler.SuperapController") as MockController:

            from app.services.scheduler import check_and_rotate_keywords
            await check_and_rotate_keywords()

            # SuperapController가 생성되지 않아야 함
            MockController.assert_not_called()

    @pytest.mark.asyncio
    async def test_scheduler_processes_exhausted_campaigns(
        self, db_session, sample_account, sample_keywords
    ):
        """오늘 변경하지 않은 모든 캠페인을 처리."""
        # 추가 캠페인 생성
        campaign = Campaign(
            campaign_code="3000001",
            account_id=sample_account.id,
            place_name="소진업체",
            place_url="https://m.place.naver.com/restaurant/30001",
            campaign_type="트래픽",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            daily_limit=300,
            status="일일소진",
        )
        db_session.add(campaign)
        db_session.commit()
        db_session.refresh(campaign)

        # 키워드 추가
        for kw in ["소진키워드1", "소진키워드2", "소진키워드3"]:
            kp = KeywordPool(
                campaign_id=campaign.id,
                keyword=kw,
                is_used=False,
            )
            db_session.add(kp)
        db_session.commit()

        mock_controller = AsyncMock()
        mock_controller.initialize = AsyncMock()
        mock_controller.close = AsyncMock()
        mock_controller.close_context = AsyncMock()
        mock_controller.login = AsyncMock(return_value=True)
        mock_controller.edit_campaign_keywords = AsyncMock(return_value=True)
        mock_controller.get_campaign_status_with_conversions = AsyncMock(
            return_value={"status": "진행중", "current_count": 0, "total_count": 300}
        )

        original_close = db_session.close
        db_session.close = lambda: None

        try:
            with patch("app.services.scheduler.SessionLocal", return_value=db_session), \
                 patch("app.services.scheduler.SuperapController", return_value=mock_controller), \
                 patch("app.services.scheduler.decrypt_password", return_value="test_pass"):

                from app.services.scheduler import check_and_rotate_keywords
                await check_and_rotate_keywords()
        finally:
            db_session.close = original_close

        # sample_keywords의 캠페인(1234567) + 소진업체(3000001) 모두 변경됨
        assert mock_controller.edit_campaign_keywords.call_count == 2

    @pytest.mark.asyncio
    async def test_scheduler_processes_active_after_2350(
        self, db_session, sample_account
    ):
        """23:50 이후 진행중 캠페인을 처리."""
        campaign = Campaign(
            campaign_code="4000001",
            account_id=sample_account.id,
            place_name="진행중업체",
            place_url="https://m.place.naver.com/restaurant/40001",
            campaign_type="트래픽",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            daily_limit=300,
            status="진행중",
        )
        db_session.add(campaign)
        db_session.commit()
        db_session.refresh(campaign)

        for kw in ["진행키워드1", "진행키워드2"]:
            kp = KeywordPool(
                campaign_id=campaign.id,
                keyword=kw,
                is_used=False,
            )
            db_session.add(kp)
        db_session.commit()

        mock_controller = AsyncMock()
        mock_controller.initialize = AsyncMock()
        mock_controller.close = AsyncMock()
        mock_controller.close_context = AsyncMock()
        mock_controller.login = AsyncMock(return_value=True)
        mock_controller.edit_campaign_keywords = AsyncMock(return_value=True)
        mock_controller.get_campaign_status_with_conversions = AsyncMock(return_value={
            "status": "진행중", "current_count": 0, "total_count": 300,
        })

        # 23:55 KST로 시간 고정
        fake_now = datetime.now(KST).replace(hour=23, minute=55, second=0)

        with patch("app.services.scheduler.SessionLocal", return_value=db_session), \
             patch("app.services.scheduler.SuperapController", return_value=mock_controller), \
             patch("app.services.scheduler.datetime") as mock_dt:

            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            from app.services.scheduler import check_and_rotate_keywords
            await check_and_rotate_keywords()

        mock_controller.edit_campaign_keywords.assert_called_once()


# ──────────────────────────────────────
# 스케줄러 시작/정지 테스트
# ──────────────────────────────────────

class TestSchedulerLifecycle:
    """스케줄러 시작/정지 테스트."""

    def test_start_scheduler(self):
        """스케줄러 시작."""
        with patch("app.services.scheduler.scheduler") as mock_scheduler:
            mock_scheduler.running = False

            from app.services.scheduler import start_scheduler
            start_scheduler()

            assert mock_scheduler.add_job.call_count == 2
            mock_scheduler.start.assert_called_once()

    def test_stop_scheduler(self):
        """스케줄러 정지."""
        with patch("app.services.scheduler.scheduler") as mock_scheduler:
            mock_scheduler.running = True

            from app.services.scheduler import stop_scheduler
            stop_scheduler()

            mock_scheduler.shutdown.assert_called_once_with(wait=False)

    def test_stop_scheduler_not_running(self):
        """스케줄러가 실행 중이 아닐 때 정지."""
        with patch("app.services.scheduler.scheduler") as mock_scheduler:
            mock_scheduler.running = False

            from app.services.scheduler import stop_scheduler
            stop_scheduler()

            mock_scheduler.shutdown.assert_not_called()


# ──────────────────────────────────────
# 엣지 케이스
# ──────────────────────────────────────

class TestEdgeCases:
    """엣지 케이스 테스트."""

    @pytest.mark.asyncio
    async def test_single_keyword_within_255(
        self, db_session, sample_campaign, mock_superap
    ):
        """키워드 1개만 있는 경우."""
        kp = KeywordPool(
            campaign_id=sample_campaign.id,
            keyword="단일키워드",
            is_used=False,
        )
        db_session.add(kp)
        db_session.commit()

        result = await rotate_keywords(
            campaign_id=sample_campaign.id,
            db=db_session,
            superap_controller=mock_superap,
        )

        assert result["success"] is True
        assert result["keywords_used"] == 1
        assert result["keywords_str"] == "단일키워드"

    @pytest.mark.asyncio
    async def test_keyword_exactly_255_chars(
        self, db_session, sample_campaign, mock_superap
    ):
        """키워드 문자열이 정확히 255자인 경우."""
        # 255자에 맞는 키워드 생성
        kw = "a" * 255
        kp = KeywordPool(
            campaign_id=sample_campaign.id,
            keyword=kw,
            is_used=False,
        )
        db_session.add(kp)
        db_session.commit()

        result = await rotate_keywords(
            campaign_id=sample_campaign.id,
            db=db_session,
            superap_controller=mock_superap,
        )

        assert result["success"] is True
        assert len(result["keywords_str"]) == 255

    @pytest.mark.asyncio
    async def test_keyword_over_255_chars_single(
        self, db_session, sample_campaign, mock_superap
    ):
        """단일 키워드가 255자 초과인 경우 선택 불가."""
        kw = "a" * 256
        kp = KeywordPool(
            campaign_id=sample_campaign.id,
            keyword=kw,
            is_used=False,
        )
        db_session.add(kp)
        db_session.commit()

        result = await rotate_keywords(
            campaign_id=sample_campaign.id,
            db=db_session,
            superap_controller=mock_superap,
        )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_whitespace_only_keywords_skipped(
        self, db_session, sample_campaign, mock_superap
    ):
        """공백만 있는 키워드는 건너뜀."""
        kp1 = KeywordPool(
            campaign_id=sample_campaign.id,
            keyword="   ",
            is_used=False,
        )
        kp2 = KeywordPool(
            campaign_id=sample_campaign.id,
            keyword="유효한키워드",
            is_used=False,
        )
        db_session.add_all([kp1, kp2])
        db_session.commit()

        result = await rotate_keywords(
            campaign_id=sample_campaign.id,
            db=db_session,
            superap_controller=mock_superap,
        )

        assert result["success"] is True
        assert "유효한키워드" in result["keywords_str"]

    @pytest.mark.asyncio
    async def test_rotate_twice_uses_different_keywords(
        self, db_session, sample_campaign, mock_superap
    ):
        """2번 연속 변경 시 다른 키워드 사용."""
        # 긴 키워드 40개 생성 → 255자 제한으로 한번에 전부 사용 불가
        for i in range(40):
            kp = KeywordPool(
                campaign_id=sample_campaign.id,
                keyword=f"테스트긴키워드이름번호{i:03d}",
                is_used=False,
            )
            db_session.add(kp)
        db_session.commit()

        result1 = await rotate_keywords(
            campaign_id=sample_campaign.id,
            db=db_session,
            superap_controller=mock_superap,
        )
        assert result1["success"] is True
        first_keywords = set(result1["keywords_str"].split(","))

        result2 = await rotate_keywords(
            campaign_id=sample_campaign.id,
            db=db_session,
            superap_controller=mock_superap,
        )
        assert result2["success"] is True
        second_keywords = set(result2["keywords_str"].split(","))

        # 두 번째 변경은 다른 키워드를 사용해야 함
        assert first_keywords.isdisjoint(second_keywords)

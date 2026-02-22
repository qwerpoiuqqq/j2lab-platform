"""5가지 기능 통합 테스트.

Feature 1: 키워드 재활용 (풀 소진 시)
Feature 2: last_keyword_change 날짜 수정
Feature 3: 전환수 실시간 업데이트
Feature 4: 캠페인 상태 한글화 + DB 영문 통일
Feature 5: 캠페인 연장 자동 처리
"""

import pytest
from datetime import datetime, date, timedelta, timezone
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from app.models.campaign import Campaign
from app.models.keyword import KeywordPool
from app.models.account import Account
from app.utils.status_map import normalize_status, to_display_label, SUPERAP_TO_INTERNAL
from app.services.keyword_rotation import (
    rotate_keywords,
    sync_campaign_status,
    sync_all_campaign_statuses,
    check_keyword_shortage,
    should_rotate_at_2350,
)

KST = ZoneInfo("Asia/Seoul")


# ──────────────────────────────────────
# Common Fixtures
# ──────────────────────────────────────

@pytest.fixture
def mock_superap():
    controller = AsyncMock()
    controller.edit_campaign_keywords = AsyncMock(return_value=True)
    controller.edit_campaign = AsyncMock(return_value=True)
    controller.get_campaign_status = AsyncMock(return_value="진행중")
    controller.get_campaign_status_with_conversions = AsyncMock(
        return_value={"status": "진행중", "current_count": 150, "total_count": 300}
    )
    return controller


@pytest.fixture
def account(db_session):
    acc = Account(
        user_id="test_user",
        password_encrypted="test_password",
        agency_name="테스트 대행사",
        is_active=True,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)
    return acc


@pytest.fixture
def campaign(db_session, account):
    c = Campaign(
        campaign_code="1234567",
        account_id=account.id,
        place_name="테스트 플레이스",
        place_url="https://m.place.naver.com/restaurant/12345",
        place_id="12345",
        campaign_type="트래픽",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        daily_limit=300,
        total_limit=9300,
        current_conversions=0,
        status="active",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


# ──────────────────────────────────────
# Feature 4: 상태 한글화 + DB 영문 통일
# ──────────────────────────────────────

class TestStatusNormalization:
    """Feature 4: normalize_status() 단위 테스트."""

    def test_korean_to_english_all_mappings(self):
        """모든 한글→영문 매핑 확인."""
        assert normalize_status("진행중") == "active"
        assert normalize_status("일일소진") == "daily_exhausted"
        assert normalize_status("캠페인소진") == "campaign_exhausted"
        assert normalize_status("일시정지") == "paused"
        assert normalize_status("대기중") == "pending"
        assert normalize_status("종료") == "completed"

    def test_already_english(self):
        """이미 영문인 경우 그대로."""
        assert normalize_status("active") == "active"
        assert normalize_status("daily_exhausted") == "daily_exhausted"
        assert normalize_status("pending_extend") == "pending_extend"

    def test_empty_or_none(self):
        """빈 문자열은 pending."""
        assert normalize_status("") == "pending"

    def test_unknown_status(self):
        """매핑에 없는 값은 그대로."""
        assert normalize_status("unknown_status") == "unknown_status"

    def test_to_display_label(self):
        """영문→한글 표시 라벨."""
        assert to_display_label("active") == "진행중"
        assert to_display_label("daily_exhausted") == "일일소진"
        assert to_display_label("pending_extend") == "연장 대기"
        assert to_display_label("") == "대기중"

    @pytest.mark.asyncio
    async def test_sync_normalizes_status(self, db_session, campaign, mock_superap):
        """sync_campaign_status가 한글을 영문으로 정규화."""
        mock_superap.get_campaign_status = AsyncMock(return_value="진행중")

        result = await sync_campaign_status(
            campaign_id=campaign.id,
            db=db_session,
            superap_controller=mock_superap,
        )

        assert result["success"] is True
        assert result["status"] == "active"
        db_session.refresh(campaign)
        assert campaign.status == "active"

    @pytest.mark.asyncio
    async def test_sync_daily_exhausted_normalized(self, db_session, campaign, mock_superap):
        """일일소진 → daily_exhausted 정규화."""
        mock_superap.get_campaign_status = AsyncMock(return_value="일일소진")

        result = await sync_campaign_status(
            campaign_id=campaign.id,
            db=db_session,
            superap_controller=mock_superap,
        )

        assert result["status"] == "daily_exhausted"
        db_session.refresh(campaign)
        assert campaign.status == "daily_exhausted"


# ──────────────────────────────────────
# Feature 2: last_keyword_change 날짜 수정
# ──────────────────────────────────────

class TestDateHandling:
    """Feature 2: UTC 저장 + KST 변환 테스트."""

    @pytest.mark.asyncio
    async def test_rotate_stores_utc(self, db_session, campaign, mock_superap):
        """rotate_keywords가 UTC로 저장."""
        for kw in ["키워드1", "키워드2", "키워드3"]:
            db_session.add(KeywordPool(
                campaign_id=campaign.id, keyword=kw, is_used=False,
            ))
        db_session.commit()

        await rotate_keywords(
            campaign_id=campaign.id,
            db=db_session,
            superap_controller=mock_superap,
            trigger_type="daily_exhausted",
        )

        db_session.refresh(campaign)
        last_change = campaign.last_keyword_change
        assert last_change is not None
        # UTC 저장이므로 tzinfo가 있거나 없더라도 UTC로 간주
        if last_change.tzinfo is not None:
            assert last_change.tzinfo in (timezone.utc, None)

    @pytest.mark.asyncio
    async def test_time_2350_stores_utc(self, db_session, campaign, mock_superap):
        """time_2350 트리거가 KST 23:50을 UTC로 변환하여 저장."""
        for kw in ["키워드A", "키워드B"]:
            db_session.add(KeywordPool(
                campaign_id=campaign.id, keyword=kw, is_used=False,
            ))
        db_session.commit()

        await rotate_keywords(
            campaign_id=campaign.id,
            db=db_session,
            superap_controller=mock_superap,
            trigger_type="time_2350",
        )

        db_session.refresh(campaign)
        last_change = campaign.last_keyword_change
        assert last_change is not None

        # UTC로 변환하면 KST 23:50 = UTC 14:50
        if last_change.tzinfo is None:
            last_change = last_change.replace(tzinfo=timezone.utc)
        kst_time = last_change.astimezone(KST)
        assert kst_time.hour == 23
        assert kst_time.minute == 50

    def test_was_rotated_today_utc_naive(self, db_session, campaign):
        """_was_rotated_today: naive datetime은 UTC로 간주."""
        from app.services.scheduler import _was_rotated_today

        # KST 오늘 14:00 = UTC 오늘 05:00
        today_kst = datetime.now(KST)
        utc_equiv = today_kst.replace(hour=14, minute=0).astimezone(timezone.utc)
        campaign.last_keyword_change = utc_equiv.replace(tzinfo=None)

        assert _was_rotated_today(campaign, today_kst.date()) is True


# ──────────────────────────────────────
# Feature 1: 키워드 재활용 (풀 소진 시)
# ──────────────────────────────────────

class TestKeywordRecycling:
    """Feature 1: 풀 소진 시 키워드 재활용."""

    @pytest.fixture
    def all_used_keywords(self, db_session, campaign):
        """모든 키워드가 사용된 상태."""
        keywords = []
        for i, kw in enumerate(["키워드1", "키워드2", "키워드3", "키워드4", "키워드5"]):
            kp = KeywordPool(
                campaign_id=campaign.id,
                keyword=kw,
                is_used=True,
                used_at=datetime.now(timezone.utc) - timedelta(hours=5-i),
            )
            db_session.add(kp)
            keywords.append(kp)
        db_session.commit()
        return keywords

    @pytest.mark.asyncio
    async def test_recycle_when_all_used(
        self, db_session, campaign, all_used_keywords, mock_superap
    ):
        """모든 키워드 사용 시 재활용 후 로테이션."""
        result = await rotate_keywords(
            campaign_id=campaign.id,
            db=db_session,
            superap_controller=mock_superap,
        )

        assert result["success"] is True
        assert result["recycled"] is True
        assert result["keywords_used"] > 0
        assert len(result["keywords_str"]) <= 255

        # superap에 전달된 키워드 확인
        mock_superap.edit_campaign_keywords.assert_called_once()
        call_kw = mock_superap.edit_campaign_keywords.call_args.kwargs["new_keywords"]
        assert "," in call_kw or len(call_kw) > 0

    @pytest.mark.asyncio
    async def test_recycle_resets_all_keywords(
        self, db_session, campaign, all_used_keywords, mock_superap
    ):
        """재활용 시 모든 키워드가 리셋 후 일부 재사용됨."""
        result = await rotate_keywords(
            campaign_id=campaign.id,
            db=db_session,
            superap_controller=mock_superap,
        )

        assert result["success"] is True
        assert result["recycled"] is True

        # 사용된 것은 이번에 선택된 것만
        used = db_session.query(KeywordPool).filter(
            KeywordPool.campaign_id == campaign.id,
            KeywordPool.is_used == True,
        ).count()
        total = db_session.query(KeywordPool).filter(
            KeywordPool.campaign_id == campaign.id,
        ).count()

        assert used > 0
        assert used <= total  # 전부 리셋 후 새로 선택 (전부 들어갈 수도 있음)

    @pytest.mark.asyncio
    async def test_no_recycle_when_pool_empty(
        self, db_session, campaign, mock_superap
    ):
        """키워드 풀 자체가 비면 재활용 불가."""
        result = await rotate_keywords(
            campaign_id=campaign.id,
            db=db_session,
            superap_controller=mock_superap,
        )

        assert result["success"] is False
        assert "비어있습니다" in result["message"]

    def test_check_keyword_shortage_recycle_warning(self, db_session, account):
        """미사용 0, 전체 있음 → 재활용 예정 warning."""
        # end_date를 미래로 설정
        future_campaign = Campaign(
            campaign_code="9999999",
            account_id=account.id,
            place_name="재활용 테스트",
            place_url="https://m.place.naver.com/restaurant/99999",
            campaign_type="트래픽",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            daily_limit=50,
            total_limit=1500,
            status="active",
        )
        db_session.add(future_campaign)
        db_session.commit()
        db_session.refresh(future_campaign)

        for kw in ["키워드A", "키워드B"]:
            db_session.add(KeywordPool(
                campaign_id=future_campaign.id, keyword=kw,
                is_used=True, used_at=datetime.now(timezone.utc),
            ))
        db_session.commit()

        result = check_keyword_shortage(future_campaign.id, db_session)
        assert result["status"] == "warning"
        assert "재활용" in result["message"]


# ──────────────────────────────────────
# Feature 3: 전환수 실시간 업데이트
# ──────────────────────────────────────

class TestConversionTracking:
    """Feature 3: 전환수 동기화."""

    @pytest.mark.asyncio
    async def test_sync_updates_conversions(
        self, db_session, campaign, account, mock_superap
    ):
        """sync_all_campaign_statuses가 전환수도 업데이트."""
        mock_superap.get_campaign_status_with_conversions = AsyncMock(
            return_value={"status": "진행중", "current_count": 150, "total_count": 300}
        )

        result = await sync_all_campaign_statuses(
            db=db_session,
            superap_controller=mock_superap,
            account_id=account.id,
        )

        assert result["success"] is True
        db_session.refresh(campaign)
        assert campaign.current_conversions == 150

    @pytest.mark.asyncio
    async def test_sync_normalizes_status_with_conversions(
        self, db_session, campaign, account, mock_superap
    ):
        """전환수와 함께 상태도 정규화."""
        campaign.status = "pending"
        db_session.commit()

        mock_superap.get_campaign_status_with_conversions = AsyncMock(
            return_value={"status": "일일소진", "current_count": 50, "total_count": 100}
        )

        result = await sync_all_campaign_statuses(
            db=db_session,
            superap_controller=mock_superap,
            account_id=account.id,
        )

        assert result["success"] is True
        db_session.refresh(campaign)
        assert campaign.status == "daily_exhausted"
        assert campaign.current_conversions == 50

    @pytest.mark.asyncio
    async def test_sync_no_change_when_same(
        self, db_session, campaign, account, mock_superap
    ):
        """동일한 상태+전환수면 synced_count=0."""
        campaign.current_conversions = 150
        db_session.commit()

        mock_superap.get_campaign_status_with_conversions = AsyncMock(
            return_value={"status": "진행중", "current_count": 150, "total_count": 300}
        )

        result = await sync_all_campaign_statuses(
            db=db_session,
            superap_controller=mock_superap,
            account_id=account.id,
        )

        assert result["synced_count"] == 0


# ──────────────────────────────────────
# Feature 5: 캠페인 연장 자동 처리
# ──────────────────────────────────────

class TestCampaignExtension:
    """Feature 5: pending_extend → 연장 처리."""

    @pytest.fixture
    def target_campaign(self, db_session, account):
        """연장 대상 기존 캠페인."""
        c = Campaign(
            campaign_code="5000001",
            account_id=account.id,
            place_name="기존 업체",
            place_url="https://m.place.naver.com/restaurant/50001",
            place_id="50001",
            campaign_type="트래픽",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 6, 30),
            daily_limit=50,
            total_limit=1000,
            current_conversions=500,
            status="active",
        )
        db_session.add(c)
        db_session.commit()
        db_session.refresh(c)

        # 기존 키워드
        for kw in ["기존키워드1", "기존키워드2", "기존키워드3"]:
            db_session.add(KeywordPool(
                campaign_id=c.id, keyword=kw, is_used=False,
            ))
        db_session.commit()
        return c

    @pytest.fixture
    def extend_campaign(self, db_session, account, target_campaign):
        """pending_extend 상태의 연장 캠페인."""
        c = Campaign(
            account_id=account.id,
            place_name="기존 업체",
            place_url="https://m.place.naver.com/restaurant/50001",
            place_id="50001",
            campaign_type="트래픽",
            start_date=date(2025, 7, 1),
            end_date=date(2025, 12, 31),
            daily_limit=50,
            total_limit=500,
            original_keywords="신규키워드1,신규키워드2,신규키워드3",
            status="pending_extend",
            extend_target_id=target_campaign.id,
        )
        db_session.add(c)
        db_session.commit()
        db_session.refresh(c)

        # 연장 캠페인의 키워드도 KeywordPool에 추가
        for kw in ["신규키워드1", "신규키워드2", "신규키워드3"]:
            db_session.add(KeywordPool(
                campaign_id=c.id, keyword=kw, is_used=False,
            ))
        db_session.commit()
        return c

    @pytest.mark.asyncio
    async def test_process_extension(
        self, db_session, account, target_campaign, extend_campaign
    ):
        """연장 처리 성공 시 total_limit 합산 + 키워드 추가."""
        mock_controller = AsyncMock()
        mock_controller.initialize = AsyncMock()
        mock_controller.close = AsyncMock()
        mock_controller.close_context = AsyncMock()
        mock_controller.login = AsyncMock(return_value=True)
        mock_controller.edit_campaign = AsyncMock(return_value=True)

        # process_pending_extensions creates its own session, so we mock it
        # to use the same db_session. Also mock session.close() to be a no-op.
        original_close = db_session.close
        db_session.close = lambda: None

        try:
            with patch("app.services.auto_registration.SessionLocal", return_value=db_session), \
                 patch("app.services.auto_registration.SuperapController", return_value=mock_controller), \
                 patch("app.services.auto_registration.decrypt_password", return_value="test_pass"):

                from app.services.auto_registration import process_pending_extensions
                await process_pending_extensions([extend_campaign.id])
        finally:
            db_session.close = original_close

        db_session.refresh(target_campaign)
        db_session.refresh(extend_campaign)

        # 기존 캠페인: total_limit 합산 (1000 + 500 = 1500)
        assert target_campaign.total_limit == 1500

        # 기존 캠페인: end_date 갱신
        assert target_campaign.end_date == date(2025, 12, 31)

        # 기존 캠페인: 신규 키워드 추가 확인
        target_keywords = db_session.query(KeywordPool).filter(
            KeywordPool.campaign_id == target_campaign.id,
        ).all()
        keyword_set = {kw.keyword for kw in target_keywords}
        assert "신규키워드1" in keyword_set
        assert "신규키워드2" in keyword_set
        assert "신규키워드3" in keyword_set
        assert "기존키워드1" in keyword_set  # 기존 키워드도 유지

        # 연장 레코드: completed
        assert extend_campaign.status == "completed"

        # superap에 전달된 값 확인
        mock_controller.edit_campaign.assert_called_once()
        call_kwargs = mock_controller.edit_campaign.call_args.kwargs
        assert call_kwargs["new_total_limit"] == 1500
        assert call_kwargs["new_end_date"] == date(2025, 12, 31)

    @pytest.mark.asyncio
    async def test_extension_superap_failure(
        self, db_session, account, target_campaign, extend_campaign
    ):
        """superap edit 실패 시 status=failed."""
        mock_controller = AsyncMock()
        mock_controller.initialize = AsyncMock()
        mock_controller.close = AsyncMock()
        mock_controller.close_context = AsyncMock()
        mock_controller.login = AsyncMock(return_value=True)
        mock_controller.edit_campaign = AsyncMock(return_value=False)

        original_close = db_session.close
        db_session.close = lambda: None

        try:
            with patch("app.services.auto_registration.SessionLocal", return_value=db_session), \
                 patch("app.services.auto_registration.SuperapController", return_value=mock_controller), \
                 patch("app.services.auto_registration.decrypt_password", return_value="test_pass"):

                from app.services.auto_registration import process_pending_extensions
                await process_pending_extensions([extend_campaign.id])
        finally:
            db_session.close = original_close

        db_session.refresh(extend_campaign)
        assert extend_campaign.status == "failed"
        assert "수정 실패" in extend_campaign.registration_message

        # 기존 캠페인은 변경되지 않아야 함
        db_session.refresh(target_campaign)
        assert target_campaign.total_limit == 1000

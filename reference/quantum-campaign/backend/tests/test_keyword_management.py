"""키워드 관리 테스트.

Phase 3 - Task 3.8: 키워드 추가 API, 잔량 확인 로직, 잔량 상태 조회 API 테스트.
"""

import pytest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.models.campaign import Campaign
from app.models.keyword import KeywordPool
from app.models.account import Account
from app.services.keyword_rotation import check_keyword_shortage


# ──────────────────────────────────────
# Fixtures
# ──────────────────────────────────────

@pytest.fixture
def sample_account(db_session):
    """테스트 계정 생성."""
    account = Account(
        user_id="test_kw_mgmt",
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
    """테스트 캠페인 생성 (종료일 10일 후)."""
    end = date.today() + timedelta(days=10)
    campaign = Campaign(
        campaign_code="9999999",
        account_id=sample_account.id,
        place_name="테스트 플레이스",
        place_url="https://m.place.naver.com/restaurant/12345",
        place_id="12345",
        campaign_type="트래픽",
        start_date=date.today(),
        end_date=end,
        daily_limit=300,
        total_limit=3300,
        status="active",
    )
    db_session.add(campaign)
    db_session.commit()
    db_session.refresh(campaign)
    return campaign


@pytest.fixture
def campaign_with_keywords(db_session, sample_campaign):
    """키워드 20개가 있는 캠페인 (미사용 15개, 사용 5개)."""
    kw_list = [
        "마포 곱창", "공덕역 맛집", "곱창 맛집", "서울 곱창", "마포역 곱창",
        "공덕 곱창", "홍대 곱창", "여의도 곱창", "신촌 곱창", "이대 곱창",
        "강남 곱창", "잠실 곱창", "송파 곱창", "성수 곱창", "건대 곱창",
        "왕십리 곱창", "동대문 곱창", "종로 곱창", "을지로 곱창", "명동 곱창",
    ]
    keywords = []
    for i, kw_text in enumerate(kw_list):
        kw = KeywordPool(
            campaign_id=sample_campaign.id,
            keyword=kw_text,
            is_used=(i < 5),  # 처음 5개는 사용됨
            used_at=datetime.now(timezone.utc) if i < 5 else None,
        )
        db_session.add(kw)
        keywords.append(kw)
    db_session.commit()
    return keywords


@pytest.fixture
def expired_campaign(db_session, sample_account):
    """종료된 캠페인."""
    campaign = Campaign(
        campaign_code="8888888",
        account_id=sample_account.id,
        place_name="종료 플레이스",
        place_url="https://m.place.naver.com/restaurant/88888",
        place_id="88888",
        campaign_type="트래픽",
        start_date=date.today() - timedelta(days=20),
        end_date=date.today() - timedelta(days=1),
        daily_limit=300,
        total_limit=6000,
        status="completed",
    )
    db_session.add(campaign)
    db_session.commit()
    db_session.refresh(campaign)
    return campaign


@pytest.fixture
def test_client(db_session):
    """테스트용 FastAPI TestClient."""
    from app.main import app
    from app.database import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# ============================================================================
# check_keyword_shortage 테스트
# ============================================================================

class TestCheckKeywordShortage:
    """check_keyword_shortage() 함수 테스트."""

    def test_normal_status(self, db_session, sample_campaign, campaign_with_keywords):
        """키워드 충분 → normal 상태."""
        # 15개 미사용, 11일 남음 → 15 >= 11 * 1.5 (16.5)? No → warning?
        # 15 >= 11? Yes → not critical
        # 15 >= 11 * 1.5 = 16.5? No → warning
        result = check_keyword_shortage(sample_campaign.id, db_session)
        assert result["remaining_keywords"] == 15
        assert result["remaining_days"] == 11  # today + 10일 = 11일 남음
        # 15 < 16.5 → warning
        assert result["status"] == "warning"

    def test_normal_status_enough_keywords(self, db_session, sample_account):
        """키워드가 충분히 많을 때 normal."""
        end = date.today() + timedelta(days=5)
        campaign = Campaign(
            campaign_code="7777777",
            account_id=sample_account.id,
            place_name="충분한 키워드 플레이스",
            place_url="https://m.place.naver.com/restaurant/77777",
            place_id="77777",
            campaign_type="트래픽",
            start_date=date.today(),
            end_date=end,
            daily_limit=300,
            total_limit=1800,
            status="active",
        )
        db_session.add(campaign)
        db_session.commit()
        db_session.refresh(campaign)

        # 30개 키워드 추가 (6일 남음, 30 >= 6*1.5=9 → normal)
        for i in range(30):
            kw = KeywordPool(
                campaign_id=campaign.id,
                keyword=f"키워드{i}",
                is_used=False,
            )
            db_session.add(kw)
        db_session.commit()

        result = check_keyword_shortage(campaign.id, db_session)
        assert result["remaining_keywords"] == 30
        assert result["remaining_days"] == 6
        assert result["status"] == "normal"

    def test_warning_status(self, db_session, sample_account):
        """키워드 주의 → warning 상태."""
        end = date.today() + timedelta(days=9)
        campaign = Campaign(
            campaign_code="6666666",
            account_id=sample_account.id,
            place_name="경고 플레이스",
            place_url="https://m.place.naver.com/restaurant/66666",
            place_id="66666",
            campaign_type="트래픽",
            start_date=date.today(),
            end_date=end,
            daily_limit=300,
            total_limit=3000,
            status="active",
        )
        db_session.add(campaign)
        db_session.commit()
        db_session.refresh(campaign)

        # 12개 키워드 추가 (10일 남음, 10 <= 12 < 15 → warning)
        for i in range(12):
            kw = KeywordPool(
                campaign_id=campaign.id,
                keyword=f"경고키워드{i}",
                is_used=False,
            )
            db_session.add(kw)
        db_session.commit()

        result = check_keyword_shortage(campaign.id, db_session)
        assert result["remaining_keywords"] == 12
        assert result["remaining_days"] == 10
        assert result["status"] == "warning"
        assert "주의" in result["message"]

    def test_critical_status(self, db_session, sample_account):
        """키워드 부족 → critical 상태."""
        end = date.today() + timedelta(days=9)
        campaign = Campaign(
            campaign_code="5555555",
            account_id=sample_account.id,
            place_name="부족 플레이스",
            place_url="https://m.place.naver.com/restaurant/55555",
            place_id="55555",
            campaign_type="트래픽",
            start_date=date.today(),
            end_date=end,
            daily_limit=300,
            total_limit=3000,
            status="active",
        )
        db_session.add(campaign)
        db_session.commit()
        db_session.refresh(campaign)

        # 5개 키워드 추가 (10일 남음, 5 < 10 → critical)
        for i in range(5):
            kw = KeywordPool(
                campaign_id=campaign.id,
                keyword=f"부족키워드{i}",
                is_used=False,
            )
            db_session.add(kw)
        db_session.commit()

        result = check_keyword_shortage(campaign.id, db_session)
        assert result["remaining_keywords"] == 5
        assert result["remaining_days"] == 10
        assert result["status"] == "critical"
        assert "부족" in result["message"]

    def test_expired_campaign(self, db_session, expired_campaign):
        """종료된 캠페인 → remaining_days=0, normal."""
        result = check_keyword_shortage(expired_campaign.id, db_session)
        assert result["remaining_days"] == 0
        assert result["status"] == "normal"
        assert "종료" in result["message"]

    def test_no_keywords(self, db_session, sample_campaign):
        """키워드 없음 → critical."""
        result = check_keyword_shortage(sample_campaign.id, db_session)
        assert result["remaining_keywords"] == 0
        assert result["status"] == "critical"

    def test_campaign_not_found(self, db_session):
        """존재하지 않는 캠페인 → critical."""
        result = check_keyword_shortage(99999, db_session)
        assert result["remaining_keywords"] == 0
        assert result["status"] == "critical"
        assert "찾을 수 없습니다" in result["message"]

    def test_all_keywords_used(self, db_session, sample_campaign):
        """모든 키워드가 사용됨 → warning (재활용 예정)."""
        for i in range(10):
            kw = KeywordPool(
                campaign_id=sample_campaign.id,
                keyword=f"사용키워드{i}",
                is_used=True,
                used_at=datetime.now(timezone.utc),
            )
            db_session.add(kw)
        db_session.commit()

        result = check_keyword_shortage(sample_campaign.id, db_session)
        assert result["remaining_keywords"] == 0
        assert result["status"] == "warning"
        assert "재활용" in result["message"]

    def test_exact_boundary_critical(self, db_session, sample_account):
        """경계값: remaining_keywords == remaining_days - 1 → critical."""
        end = date.today() + timedelta(days=9)
        campaign = Campaign(
            campaign_code="4444444",
            account_id=sample_account.id,
            place_name="경계 플레이스1",
            place_url="https://m.place.naver.com/restaurant/44444",
            place_id="44444",
            campaign_type="트래픽",
            start_date=date.today(),
            end_date=end,
            daily_limit=300,
            total_limit=3000,
            status="active",
        )
        db_session.add(campaign)
        db_session.commit()
        db_session.refresh(campaign)

        # 9개 키워드 (10일 남음, 9 < 10 → critical)
        for i in range(9):
            kw = KeywordPool(
                campaign_id=campaign.id,
                keyword=f"경계키워드{i}",
                is_used=False,
            )
            db_session.add(kw)
        db_session.commit()

        result = check_keyword_shortage(campaign.id, db_session)
        assert result["status"] == "critical"

    def test_exact_boundary_warning(self, db_session, sample_account):
        """경계값: remaining_keywords == remaining_days → warning (not critical)."""
        end = date.today() + timedelta(days=9)
        campaign = Campaign(
            campaign_code="3333333",
            account_id=sample_account.id,
            place_name="경계 플레이스2",
            place_url="https://m.place.naver.com/restaurant/33333",
            place_id="33333",
            campaign_type="트래픽",
            start_date=date.today(),
            end_date=end,
            daily_limit=300,
            total_limit=3000,
            status="active",
        )
        db_session.add(campaign)
        db_session.commit()
        db_session.refresh(campaign)

        # 10개 키워드 (10일 남음, 10 >= 10 → not critical, 10 < 15 → warning)
        for i in range(10):
            kw = KeywordPool(
                campaign_id=campaign.id,
                keyword=f"경계2키워드{i}",
                is_used=False,
            )
            db_session.add(kw)
        db_session.commit()

        result = check_keyword_shortage(campaign.id, db_session)
        assert result["status"] == "warning"

    def test_exact_boundary_normal(self, db_session, sample_account):
        """경계값: remaining_keywords == remaining_days * 1.5 → normal."""
        end = date.today() + timedelta(days=9)
        campaign = Campaign(
            campaign_code="2222222",
            account_id=sample_account.id,
            place_name="경계 플레이스3",
            place_url="https://m.place.naver.com/restaurant/22222",
            place_id="22222",
            campaign_type="트래픽",
            start_date=date.today(),
            end_date=end,
            daily_limit=300,
            total_limit=3000,
            status="active",
        )
        db_session.add(campaign)
        db_session.commit()
        db_session.refresh(campaign)

        # 15개 키워드 (10일 남음, 15 >= 15 → normal)
        for i in range(15):
            kw = KeywordPool(
                campaign_id=campaign.id,
                keyword=f"경계3키워드{i}",
                is_used=False,
            )
            db_session.add(kw)
        db_session.commit()

        result = check_keyword_shortage(campaign.id, db_session)
        assert result["status"] == "normal"

    def test_ends_today(self, db_session, sample_account):
        """오늘 종료 캠페인 → remaining_days=1."""
        campaign = Campaign(
            campaign_code="1111111",
            account_id=sample_account.id,
            place_name="오늘종료 플레이스",
            place_url="https://m.place.naver.com/restaurant/11111",
            place_id="11111",
            campaign_type="트래픽",
            start_date=date.today() - timedelta(days=5),
            end_date=date.today(),
            daily_limit=300,
            total_limit=1800,
            status="active",
        )
        db_session.add(campaign)
        db_session.commit()
        db_session.refresh(campaign)

        # 5개 키워드 (1일 남음, 5 >= 1.5 → normal)
        for i in range(5):
            kw = KeywordPool(
                campaign_id=campaign.id,
                keyword=f"오늘키워드{i}",
                is_used=False,
            )
            db_session.add(kw)
        db_session.commit()

        result = check_keyword_shortage(campaign.id, db_session)
        assert result["remaining_days"] == 1
        assert result["status"] == "normal"


# ============================================================================
# POST /campaigns/{campaign_id}/keywords 테스트
# ============================================================================

class TestAddKeywordsAPI:
    """키워드 추가 API 테스트."""

    def test_add_keywords_success(self, test_client, sample_campaign):
        """키워드 추가 성공."""
        resp = test_client.post(
            f"/campaigns/{sample_campaign.id}/keywords",
            json={"keywords": "새키워드1,새키워드2,새키워드3"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["added_count"] == 3
        assert data["duplicates"] == []
        assert data["total_keywords"] == 3
        assert data["unused_keywords"] == 3

    def test_add_keywords_with_duplicates(
        self, test_client, sample_campaign, campaign_with_keywords, db_session
    ):
        """중복 키워드 포함 시 중복 제외하고 추가."""
        resp = test_client.post(
            f"/campaigns/{sample_campaign.id}/keywords",
            json={"keywords": "마포 곱창,새로운키워드,공덕역 맛집"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["added_count"] == 1  # 새로운키워드만 추가
        assert len(data["duplicates"]) == 2
        assert "마포 곱창" in data["duplicates"]
        assert "공덕역 맛집" in data["duplicates"]

    def test_add_keywords_all_duplicates(
        self, test_client, sample_campaign, campaign_with_keywords
    ):
        """모두 중복인 경우."""
        resp = test_client.post(
            f"/campaigns/{sample_campaign.id}/keywords",
            json={"keywords": "마포 곱창,공덕역 맛집"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["added_count"] == 0
        assert len(data["duplicates"]) == 2

    def test_add_keywords_campaign_not_found(self, test_client):
        """존재하지 않는 캠페인."""
        resp = test_client.post(
            "/campaigns/99999/keywords",
            json={"keywords": "키워드1,키워드2"},
        )
        assert resp.status_code == 404

    def test_add_keywords_empty_input(self, test_client, sample_campaign):
        """빈 키워드 입력."""
        resp = test_client.post(
            f"/campaigns/{sample_campaign.id}/keywords",
            json={"keywords": ""},
        )
        assert resp.status_code == 422  # validation error

    def test_add_keywords_whitespace_only(self, test_client, sample_campaign):
        """공백만 있는 키워드."""
        resp = test_client.post(
            f"/campaigns/{sample_campaign.id}/keywords",
            json={"keywords": " , , "},
        )
        assert resp.status_code == 400

    def test_add_keywords_with_spaces(self, test_client, sample_campaign):
        """키워드 앞뒤 공백 처리."""
        resp = test_client.post(
            f"/campaigns/{sample_campaign.id}/keywords",
            json={"keywords": " 키워드A , 키워드B , 키워드C "},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["added_count"] == 3

    def test_add_keywords_single(self, test_client, sample_campaign):
        """단일 키워드 추가."""
        resp = test_client.post(
            f"/campaigns/{sample_campaign.id}/keywords",
            json={"keywords": "단일키워드"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["added_count"] == 1
        assert data["total_keywords"] == 1

    def test_add_keywords_updates_counts(
        self, test_client, sample_campaign, campaign_with_keywords, db_session
    ):
        """추가 후 total/unused 카운트 정확성."""
        resp = test_client.post(
            f"/campaigns/{sample_campaign.id}/keywords",
            json={"keywords": "추가키워드1,추가키워드2"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # 기존 20개 + 새 2개 = 22개
        assert data["total_keywords"] == 22
        # 기존 미사용 15개 + 새 2개 = 17개
        assert data["unused_keywords"] == 17

    def test_add_keywords_duplicate_in_input(self, test_client, sample_campaign):
        """입력 내 중복 키워드 (같은 키워드 2번)."""
        resp = test_client.post(
            f"/campaigns/{sample_campaign.id}/keywords",
            json={"keywords": "중복테스트,중복테스트,유니크"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # 첫번째 "중복테스트"는 추가, 두번째는 DB UniqueConstraint 또는 set으로 걸림
        # 우리 구현은 existing_set으로 추적하므로 2개 추가
        assert data["added_count"] == 2
        assert data["total_keywords"] == 2


# ============================================================================
# GET /campaigns/{campaign_id}/keywords/status 테스트
# ============================================================================

class TestKeywordStatusAPI:
    """키워드 잔량 상태 조회 API 테스트."""

    def test_status_normal(self, test_client, db_session, sample_account):
        """정상 상태 조회."""
        end = date.today() + timedelta(days=4)
        campaign = Campaign(
            campaign_code="ST00001",
            account_id=sample_account.id,
            place_name="정상 플레이스",
            place_url="https://m.place.naver.com/restaurant/10001",
            place_id="10001",
            campaign_type="트래픽",
            start_date=date.today(),
            end_date=end,
            daily_limit=300,
            total_limit=1500,
            status="active",
        )
        db_session.add(campaign)
        db_session.commit()
        db_session.refresh(campaign)

        # 20개 키워드 (5일 남음, 20 >= 7.5 → normal)
        for i in range(20):
            kw = KeywordPool(
                campaign_id=campaign.id,
                keyword=f"상태키워드{i}",
                is_used=False,
            )
            db_session.add(kw)
        db_session.commit()

        resp = test_client.get(f"/campaigns/{campaign.id}/keywords/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["campaign_id"] == campaign.id
        assert data["remaining_keywords"] == 20
        assert data["remaining_days"] == 5
        assert data["status"] == "normal"

    def test_status_warning(self, test_client, db_session, sample_account):
        """경고 상태 조회."""
        end = date.today() + timedelta(days=9)
        campaign = Campaign(
            campaign_code="ST00002",
            account_id=sample_account.id,
            place_name="경고 플레이스",
            place_url="https://m.place.naver.com/restaurant/10002",
            place_id="10002",
            campaign_type="트래픽",
            start_date=date.today(),
            end_date=end,
            daily_limit=300,
            total_limit=3000,
            status="active",
        )
        db_session.add(campaign)
        db_session.commit()
        db_session.refresh(campaign)

        # 12개 키워드 (10일 남음, 10 <= 12 < 15 → warning)
        for i in range(12):
            kw = KeywordPool(
                campaign_id=campaign.id,
                keyword=f"경고상태키워드{i}",
                is_used=False,
            )
            db_session.add(kw)
        db_session.commit()

        resp = test_client.get(f"/campaigns/{campaign.id}/keywords/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "warning"

    def test_status_critical(self, test_client, db_session, sample_account):
        """위험 상태 조회."""
        end = date.today() + timedelta(days=9)
        campaign = Campaign(
            campaign_code="ST00003",
            account_id=sample_account.id,
            place_name="위험 플레이스",
            place_url="https://m.place.naver.com/restaurant/10003",
            place_id="10003",
            campaign_type="트래픽",
            start_date=date.today(),
            end_date=end,
            daily_limit=300,
            total_limit=3000,
            status="active",
        )
        db_session.add(campaign)
        db_session.commit()
        db_session.refresh(campaign)

        # 3개 키워드 (10일 남음, 3 < 10 → critical)
        for i in range(3):
            kw = KeywordPool(
                campaign_id=campaign.id,
                keyword=f"위험상태키워드{i}",
                is_used=False,
            )
            db_session.add(kw)
        db_session.commit()

        resp = test_client.get(f"/campaigns/{campaign.id}/keywords/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "critical"

    def test_status_campaign_not_found(self, test_client):
        """존재하지 않는 캠페인."""
        resp = test_client.get("/campaigns/99999/keywords/status")
        assert resp.status_code == 404

    def test_status_expired_campaign(self, test_client, expired_campaign):
        """종료된 캠페인."""
        resp = test_client.get(
            f"/campaigns/{expired_campaign.id}/keywords/status"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["remaining_days"] == 0
        assert data["status"] == "normal"
        assert "종료" in data["message"]

    def test_status_no_keywords(self, test_client, sample_campaign):
        """키워드가 없는 캠페인."""
        resp = test_client.get(
            f"/campaigns/{sample_campaign.id}/keywords/status"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["remaining_keywords"] == 0
        assert data["status"] == "critical"


# ============================================================================
# 통합 시나리오 테스트
# ============================================================================

class TestKeywordManagementIntegration:
    """키워드 추가 후 잔량 확인 통합 테스트."""

    def test_add_then_check_status(self, test_client, sample_campaign):
        """키워드 추가 후 잔량 확인."""
        # 초기: 키워드 없음 → critical
        resp = test_client.get(
            f"/campaigns/{sample_campaign.id}/keywords/status"
        )
        assert resp.json()["status"] == "critical"

        # 키워드 30개 추가
        keywords = ",".join([f"통합키워드{i}" for i in range(30)])
        resp = test_client.post(
            f"/campaigns/{sample_campaign.id}/keywords",
            json={"keywords": keywords},
        )
        assert resp.json()["added_count"] == 30

        # 잔량 확인: 30개/11일 → 30 >= 16.5 → normal
        resp = test_client.get(
            f"/campaigns/{sample_campaign.id}/keywords/status"
        )
        data = resp.json()
        assert data["remaining_keywords"] == 30
        assert data["status"] == "normal"

    def test_add_keywords_incremental(self, test_client, sample_campaign):
        """키워드 점진적 추가."""
        # 1차: 5개 추가
        resp = test_client.post(
            f"/campaigns/{sample_campaign.id}/keywords",
            json={"keywords": "가,나,다,라,마"},
        )
        assert resp.json()["added_count"] == 5
        assert resp.json()["total_keywords"] == 5

        # 2차: 3개 추가 (2개 중복)
        resp = test_client.post(
            f"/campaigns/{sample_campaign.id}/keywords",
            json={"keywords": "가,나,바,사"},
        )
        assert resp.json()["added_count"] == 2  # 바, 사
        assert resp.json()["duplicates"] == ["가", "나"]
        assert resp.json()["total_keywords"] == 7

    def test_add_many_keywords_changes_status(
        self, test_client, db_session, sample_account
    ):
        """키워드 추가로 상태 변경: critical → warning → normal."""
        end = date.today() + timedelta(days=9)
        campaign = Campaign(
            campaign_code="INTEG01",
            account_id=sample_account.id,
            place_name="통합테스트 플레이스",
            place_url="https://m.place.naver.com/restaurant/99001",
            place_id="99001",
            campaign_type="트래픽",
            start_date=date.today(),
            end_date=end,
            daily_limit=300,
            total_limit=3000,
            status="active",
        )
        db_session.add(campaign)
        db_session.commit()
        db_session.refresh(campaign)

        # 초기: 0개 → critical
        resp = test_client.get(f"/campaigns/{campaign.id}/keywords/status")
        assert resp.json()["status"] == "critical"

        # 10개 추가: 10/10 → warning (10 >= 10 not critical, 10 < 15 → warning)
        keywords = ",".join([f"상태변경{i}" for i in range(10)])
        test_client.post(
            f"/campaigns/{campaign.id}/keywords",
            json={"keywords": keywords},
        )
        resp = test_client.get(f"/campaigns/{campaign.id}/keywords/status")
        assert resp.json()["status"] == "warning"

        # 10개 더 추가: 20/10 → normal (20 >= 15 → normal)
        keywords = ",".join([f"추가상태{i}" for i in range(10)])
        test_client.post(
            f"/campaigns/{campaign.id}/keywords",
            json={"keywords": keywords},
        )
        resp = test_client.get(f"/campaigns/{campaign.id}/keywords/status")
        assert resp.json()["status"] == "normal"

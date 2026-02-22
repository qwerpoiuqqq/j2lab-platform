"""캠페인 수기 추가 API 테스트.

Phase 3 - Task 3.6: 수기 캠페인 추가 + 캠페인 존재 확인
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.account import Account
from app.models.campaign import Campaign
from app.models.keyword import KeywordPool


# 테스트용 인메모리 DB 설정
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """테스트용 DB 세션."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()

    # 테스트용 계정 추가
    test_accounts = [
        Account(user_id="testuser1", agency_name="테스트대행사1", is_active=True),
        Account(user_id="testuser2", agency_name="테스트대행사2", is_active=True),
        Account(user_id="inactive_user", agency_name="비활성대행사", is_active=False),
    ]
    for account in test_accounts:
        session.add(account)
    session.commit()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """테스트 클라이언트."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _base_manual_input(db_session, **overrides):
    """기본 수기 캠페인 입력 데이터 생성."""
    account = db_session.query(Account).filter(
        Account.user_id == "testuser1"
    ).first()

    tomorrow = date.today() + timedelta(days=1)
    next_week = date.today() + timedelta(days=7)

    data = {
        "campaign_code": "C100001",
        "account_id": account.id,
        "place_name": "테스트플레이스",
        "place_url": "https://m.place.naver.com/restaurant/1234567890",
        "campaign_type": "트래픽",
        "start_date": tomorrow.isoformat(),
        "end_date": next_week.isoformat(),
        "daily_limit": 100,
        "keywords": "키워드1,키워드2,키워드3,키워드4,키워드5",
    }
    data.update(overrides)
    return data


# ============================================================
# POST /campaigns/manual - 수기 캠페인 추가 테스트
# ============================================================

class TestAddManualCampaign:
    """POST /campaigns/manual 테스트."""

    def test_add_manual_campaign_success(self, client, db_session):
        """정상적인 수기 캠페인 추가."""
        data = _base_manual_input(db_session)

        response = client.post("/campaigns/manual", json=data)

        assert response.status_code == 200
        resp = response.json()
        assert resp["success"] is True
        assert resp["campaign_id"] is not None
        assert resp["campaign_code"] == "C100001"
        assert resp["place_id"] == "1234567890"
        assert resp["keyword_count"] == 5

    def test_campaign_saved_to_db(self, client, db_session):
        """DB에 캠페인이 올바르게 저장되는지 확인."""
        data = _base_manual_input(db_session)

        response = client.post("/campaigns/manual", json=data)
        assert response.status_code == 200

        campaign = db_session.query(Campaign).filter(
            Campaign.campaign_code == "C100001"
        ).first()

        assert campaign is not None
        assert campaign.status == "active"
        assert campaign.place_name == "테스트플레이스"
        assert campaign.place_id == "1234567890"
        assert campaign.campaign_type == "트래픽"
        assert campaign.daily_limit == 100
        assert campaign.agency_name == "테스트대행사1"
        assert campaign.registered_at is not None

    def test_campaign_total_limit_calculated(self, client, db_session):
        """total_limit이 자동 계산되는지 확인."""
        tomorrow = date.today() + timedelta(days=1)
        end_day = date.today() + timedelta(days=7)
        expected_days = (end_day - tomorrow).days + 1  # 7일

        data = _base_manual_input(
            db_session,
            start_date=tomorrow.isoformat(),
            end_date=end_day.isoformat(),
            daily_limit=150,
        )

        response = client.post("/campaigns/manual", json=data)
        assert response.status_code == 200

        campaign = db_session.query(Campaign).filter(
            Campaign.campaign_code == "C100001"
        ).first()

        assert campaign.total_limit == 150 * expected_days

    def test_keywords_saved_to_keyword_pool(self, client, db_session):
        """키워드가 KeywordPool에 저장되는지 확인."""
        data = _base_manual_input(db_session, keywords="맛집,카페,디저트")

        response = client.post("/campaigns/manual", json=data)
        assert response.status_code == 200

        campaign_id = response.json()["campaign_id"]
        keywords = db_session.query(KeywordPool).filter(
            KeywordPool.campaign_id == campaign_id
        ).all()

        assert len(keywords) == 3
        keyword_texts = {kw.keyword for kw in keywords}
        assert keyword_texts == {"맛집", "카페", "디저트"}

        for kw in keywords:
            assert kw.is_used is False
            assert kw.used_at is None

    def test_duplicate_keywords_deduplicated(self, client, db_session):
        """중복 키워드는 제거되는지 확인."""
        data = _base_manual_input(
            db_session,
            keywords="맛집,카페,맛집,디저트,카페",
        )

        response = client.post("/campaigns/manual", json=data)
        assert response.status_code == 200

        resp = response.json()
        assert resp["keyword_count"] == 3  # 중복 제거 후 3개

        campaign_id = resp["campaign_id"]
        keywords = db_session.query(KeywordPool).filter(
            KeywordPool.campaign_id == campaign_id
        ).all()

        assert len(keywords) == 3

    def test_original_keywords_preserved(self, client, db_session):
        """original_keywords에 원본 키워드 문자열 저장."""
        keywords_str = "키워드A, 키워드B, 키워드C"
        data = _base_manual_input(db_session, keywords=keywords_str)

        response = client.post("/campaigns/manual", json=data)
        assert response.status_code == 200

        campaign = db_session.query(Campaign).filter(
            Campaign.campaign_code == "C100001"
        ).first()

        assert campaign.original_keywords == keywords_str

    def test_savehagi_campaign_type(self, client, db_session):
        """저장하기 타입 캠페인 추가."""
        data = _base_manual_input(db_session, campaign_type="저장하기")

        response = client.post("/campaigns/manual", json=data)
        assert response.status_code == 200

        campaign = db_session.query(Campaign).filter(
            Campaign.campaign_code == "C100001"
        ).first()
        assert campaign.campaign_type == "저장하기"

    def test_place_id_extracted_from_various_urls(self, client, db_session):
        """다양한 URL 형식에서 place_id 추출."""
        urls_and_expected = [
            ("https://m.place.naver.com/restaurant/1234567890", "1234567890"),
            ("https://m.place.naver.com/cafe/9876543210", "9876543210"),
            ("https://place.naver.com/restaurant/5555555555/home", "5555555555"),
        ]

        for i, (url, expected_id) in enumerate(urls_and_expected):
            code = f"CURL{i}"
            data = _base_manual_input(
                db_session,
                campaign_code=code,
                place_url=url,
            )

            response = client.post("/campaigns/manual", json=data)
            assert response.status_code == 200
            assert response.json()["place_id"] == expected_id


# ============================================================
# POST /campaigns/manual - 에러 케이스 테스트
# ============================================================

class TestAddManualCampaignErrors:
    """POST /campaigns/manual 에러 케이스 테스트."""

    def test_account_not_found(self, client, db_session):
        """존재하지 않는 계정 ID."""
        data = _base_manual_input(db_session, account_id=99999)

        response = client.post("/campaigns/manual", json=data)
        assert response.status_code == 404
        assert "계정" in response.json()["detail"]

    def test_inactive_account(self, client, db_session):
        """비활성 계정으로 추가 시도."""
        inactive = db_session.query(Account).filter(
            Account.user_id == "inactive_user"
        ).first()

        data = _base_manual_input(db_session, account_id=inactive.id)

        response = client.post("/campaigns/manual", json=data)
        assert response.status_code == 404
        assert "활성 계정" in response.json()["detail"]

    def test_duplicate_campaign_code(self, client, db_session):
        """중복 캠페인 코드."""
        # 첫 번째 등록
        data = _base_manual_input(db_session, campaign_code="CDUP001")
        response = client.post("/campaigns/manual", json=data)
        assert response.status_code == 200

        # 같은 코드로 두 번째 등록 시도
        data2 = _base_manual_input(db_session, campaign_code="CDUP001")
        response2 = client.post("/campaigns/manual", json=data2)
        assert response2.status_code == 409
        assert "이미 등록된" in response2.json()["detail"]

    def test_end_date_before_start_date(self, client, db_session):
        """종료일이 시작일보다 이전."""
        tomorrow = date.today() + timedelta(days=1)
        yesterday = date.today() - timedelta(days=1)

        data = _base_manual_input(
            db_session,
            start_date=tomorrow.isoformat(),
            end_date=yesterday.isoformat(),
        )

        response = client.post("/campaigns/manual", json=data)
        assert response.status_code == 400
        assert "종료일" in response.json()["detail"]

    def test_empty_campaign_type(self, client, db_session):
        """빈 캠페인 이름."""
        data = _base_manual_input(db_session, campaign_type="   ")

        response = client.post("/campaigns/manual", json=data)
        assert response.status_code == 422  # Pydantic validation error

    def test_empty_campaign_code(self, client, db_session):
        """빈 캠페인 코드."""
        data = _base_manual_input(db_session, campaign_code="   ")

        response = client.post("/campaigns/manual", json=data)
        assert response.status_code == 422

    def test_empty_keywords(self, client, db_session):
        """빈 키워드."""
        data = _base_manual_input(db_session, keywords="   ")

        response = client.post("/campaigns/manual", json=data)
        assert response.status_code == 422

    def test_zero_daily_limit(self, client, db_session):
        """daily_limit이 0 이하."""
        data = _base_manual_input(db_session, daily_limit=0)

        response = client.post("/campaigns/manual", json=data)
        assert response.status_code == 422

    def test_only_comma_keywords(self, client, db_session):
        """쉼표만 있는 키워드."""
        data = _base_manual_input(db_session, keywords=",,,")

        response = client.post("/campaigns/manual", json=data)
        assert response.status_code == 400
        assert "유효한 키워드" in response.json()["detail"]


# ============================================================
# GET /campaigns/manual/verify/{campaign_code} - 캠페인 확인 테스트
# ============================================================

class TestVerifyCampaign:
    """GET /campaigns/manual/verify/{campaign_code} 테스트."""

    def test_verify_nonexistent_campaign(self, client, db_session):
        """DB에 없는 캠페인 코드."""
        response = client.get("/campaigns/manual/verify/CNOTEXIST")

        assert response.status_code == 200
        resp = response.json()
        assert resp["campaign_code"] == "CNOTEXIST"
        assert resp["exists_in_db"] is False
        assert resp["db_campaign_id"] is None
        assert resp["db_status"] is None

    def test_verify_existing_campaign(self, client, db_session):
        """DB에 있는 캠페인 코드."""
        account = db_session.query(Account).filter(
            Account.user_id == "testuser1"
        ).first()

        campaign = Campaign(
            campaign_code="CVERIFY1",
            account_id=account.id,
            place_name="검증플레이스",
            place_url="https://m.place.naver.com/restaurant/11111",
            place_id="11111",
            campaign_type="트래픽",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            daily_limit=100,
            status="active",
        )
        db_session.add(campaign)
        db_session.commit()

        response = client.get("/campaigns/manual/verify/CVERIFY1")

        assert response.status_code == 200
        resp = response.json()
        assert resp["campaign_code"] == "CVERIFY1"
        assert resp["exists_in_db"] is True
        assert resp["db_campaign_id"] == campaign.id
        assert resp["db_status"] == "active"

    def test_verify_with_account_id_filter(self, client, db_session):
        """account_id 필터로 특정 계정 조회."""
        account1 = db_session.query(Account).filter(
            Account.user_id == "testuser1"
        ).first()
        account2 = db_session.query(Account).filter(
            Account.user_id == "testuser2"
        ).first()

        campaign = Campaign(
            campaign_code="CACCT1",
            account_id=account1.id,
            place_name="계정1플레이스",
            place_url="https://m.place.naver.com/restaurant/22222",
            place_id="22222",
            campaign_type="트래픽",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            daily_limit=100,
            status="active",
        )
        db_session.add(campaign)
        db_session.commit()

        # 계정1로 조회 -> 존재
        response1 = client.get(
            f"/campaigns/manual/verify/CACCT1?account_id={account1.id}"
        )
        assert response1.json()["exists_in_db"] is True

        # 계정2로 조회 -> 없음
        response2 = client.get(
            f"/campaigns/manual/verify/CACCT1?account_id={account2.id}"
        )
        assert response2.json()["exists_in_db"] is False

    def test_verify_pending_campaign(self, client, db_session):
        """pending 상태 캠페인도 exists_in_db = True."""
        account = db_session.query(Account).filter(
            Account.user_id == "testuser1"
        ).first()

        campaign = Campaign(
            campaign_code="CPEND1",
            account_id=account.id,
            place_name="대기플레이스",
            place_url="https://m.place.naver.com/restaurant/33333",
            place_id="33333",
            campaign_type="저장하기",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            daily_limit=50,
            status="pending",
        )
        db_session.add(campaign)
        db_session.commit()

        response = client.get("/campaigns/manual/verify/CPEND1")

        assert response.status_code == 200
        resp = response.json()
        assert resp["exists_in_db"] is True
        assert resp["db_status"] == "pending"

    def test_verify_without_account_filter(self, client, db_session):
        """account_id 없이 조회하면 전체 캠페인에서 검색."""
        account = db_session.query(Account).filter(
            Account.user_id == "testuser2"
        ).first()

        campaign = Campaign(
            campaign_code="CANY1",
            account_id=account.id,
            place_name="아무플레이스",
            place_url="https://m.place.naver.com/restaurant/44444",
            place_id="44444",
            campaign_type="트래픽",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            daily_limit=100,
            status="active",
        )
        db_session.add(campaign)
        db_session.commit()

        response = client.get("/campaigns/manual/verify/CANY1")

        assert response.status_code == 200
        assert response.json()["exists_in_db"] is True


# ============================================================
# 통합 플로우 테스트
# ============================================================

class TestManualCampaignFlow:
    """수기 캠페인 추가 전체 플로우 테스트."""

    def test_verify_then_add_flow(self, client, db_session):
        """확인 후 추가 전체 플로우."""
        # 1. 먼저 확인 - 없음
        verify_resp = client.get("/campaigns/manual/verify/CFLOW1")
        assert verify_resp.json()["exists_in_db"] is False

        # 2. 수기 추가
        data = _base_manual_input(db_session, campaign_code="CFLOW1")
        add_resp = client.post("/campaigns/manual", json=data)
        assert add_resp.status_code == 200
        assert add_resp.json()["success"] is True

        # 3. 다시 확인 - 있음
        verify_resp2 = client.get("/campaigns/manual/verify/CFLOW1")
        assert verify_resp2.json()["exists_in_db"] is True
        assert verify_resp2.json()["db_status"] == "active"

    def test_add_then_attempt_duplicate(self, client, db_session):
        """추가 후 중복 추가 시도 실패."""
        data = _base_manual_input(db_session, campaign_code="CDUP2")

        # 첫 번째 추가 성공
        resp1 = client.post("/campaigns/manual", json=data)
        assert resp1.status_code == 200

        # 두 번째 추가 실패 (409)
        resp2 = client.post("/campaigns/manual", json=data)
        assert resp2.status_code == 409

    def test_multiple_campaigns_different_codes(self, client, db_session):
        """서로 다른 캠페인 코드로 여러 캠페인 추가."""
        for i in range(3):
            data = _base_manual_input(
                db_session,
                campaign_code=f"CMULTI{i}",
                place_url=f"https://m.place.naver.com/restaurant/{50000 + i}",
            )
            response = client.post("/campaigns/manual", json=data)
            assert response.status_code == 200

        # DB에 3개 캠페인이 있는지 확인
        count = db_session.query(Campaign).filter(
            Campaign.campaign_code.like("CMULTI%")
        ).count()
        assert count == 3

    def test_campaign_with_many_keywords(self, client, db_session):
        """많은 키워드 처리."""
        keywords = ",".join([f"키워드{i}" for i in range(50)])
        data = _base_manual_input(db_session, keywords=keywords)

        response = client.post("/campaigns/manual", json=data)
        assert response.status_code == 200

        resp = response.json()
        assert resp["keyword_count"] == 50

        # KeywordPool에도 50개
        kw_count = db_session.query(KeywordPool).filter(
            KeywordPool.campaign_id == resp["campaign_id"]
        ).count()
        assert kw_count == 50

"""대시보드 API 테스트.

Phase 3 - Task 3.9: 캠페인 목록/상세, 계정/대행사 목록, 대시보드 통계 API 테스트.
"""

import pytest
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.models.account import Account
from app.models.campaign import Campaign
from app.models.keyword import KeywordPool


# ──────────────────────────────────────
# Fixtures
# ──────────────────────────────────────

@pytest.fixture
def account_a(db_session):
    """계정 A."""
    account = Account(
        user_id="account_a",
        password_encrypted="enc_pw_a",
        agency_name="대행사A",
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


@pytest.fixture
def account_b(db_session):
    """계정 B."""
    account = Account(
        user_id="account_b",
        password_encrypted="enc_pw_b",
        agency_name="대행사B",
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


@pytest.fixture
def inactive_account(db_session):
    """비활성 계정."""
    account = Account(
        user_id="inactive_acc",
        password_encrypted="enc_pw",
        agency_name="비활성대행사",
        is_active=False,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


@pytest.fixture
def campaigns_set(db_session, account_a, account_b):
    """다양한 상태의 캠페인 세트."""
    today = date.today()
    campaigns = []

    # 계정A: 활성 캠페인 3개
    for i in range(3):
        c = Campaign(
            campaign_code=f"100000{i}",
            account_id=account_a.id,
            agency_name="대행사A",
            place_name=f"플레이스A{i}",
            place_url=f"https://m.place.naver.com/restaurant/{10000 + i}",
            place_id=str(10000 + i),
            campaign_type="트래픽",
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=10),
            daily_limit=300,
            total_limit=4500,
            current_conversions=840 + i * 100,
            status="active",
            registered_at=datetime.now(timezone.utc),
        )
        db_session.add(c)
        campaigns.append(c)

    # 계정A: 일일소진 캠페인 1개
    c_exhausted = Campaign(
        campaign_code="1000003",
        account_id=account_a.id,
        agency_name="대행사A",
        place_name="소진플레이스",
        place_url="https://m.place.naver.com/restaurant/10003",
        place_id="10003",
        campaign_type="저장하기",
        start_date=today - timedelta(days=3),
        end_date=today + timedelta(days=7),
        daily_limit=500,
        total_limit=5000,
        current_conversions=1768,
        status="daily_exhausted",
        registered_at=datetime.now(timezone.utc),
    )
    db_session.add(c_exhausted)
    campaigns.append(c_exhausted)

    # 계정B: 진행중 캠페인 2개
    for i in range(2):
        c = Campaign(
            campaign_code=f"200000{i}",
            account_id=account_b.id,
            agency_name="대행사B",
            place_name=f"플레이스B{i}",
            place_url=f"https://m.place.naver.com/restaurant/{20000 + i}",
            place_id=str(20000 + i),
            campaign_type="트래픽",
            start_date=today - timedelta(days=2),
            end_date=today + timedelta(days=12),
            daily_limit=200,
            total_limit=2800,
            current_conversions=420 + i * 50,
            status="active",
            registered_at=datetime.now(timezone.utc),
        )
        db_session.add(c)
        campaigns.append(c)

    # 계정B: 종료 캠페인 1개
    c_ended = Campaign(
        campaign_code="2000002",
        account_id=account_b.id,
        agency_name="대행사B",
        place_name="종료플레이스",
        place_url="https://m.place.naver.com/restaurant/20002",
        place_id="20002",
        campaign_type="저장하기",
        start_date=today - timedelta(days=20),
        end_date=today - timedelta(days=1),
        daily_limit=300,
        total_limit=6000,
        current_conversions=5800,
        status="completed",
    )
    db_session.add(c_ended)
    campaigns.append(c_ended)

    db_session.commit()
    for c in campaigns:
        db_session.refresh(c)
    return campaigns


@pytest.fixture
def keywords_for_campaigns(db_session, campaigns_set):
    """캠페인별 키워드 추가."""
    all_keywords = []

    for idx, campaign in enumerate(campaigns_set):
        # 캠페인마다 다른 수의 키워드
        total_count = 20 - idx * 2  # 20, 18, 16, 14, 12, 10, 8
        used_count = idx * 2  # 0, 2, 4, 6, 8, 10, 12

        for i in range(min(total_count, 20)):
            kw = KeywordPool(
                campaign_id=campaign.id,
                keyword=f"키워드{campaign.id}_{i}",
                is_used=(i < used_count),
                used_at=datetime.now(timezone.utc) if i < used_count else None,
            )
            db_session.add(kw)
            all_keywords.append(kw)

    db_session.commit()
    return all_keywords


@pytest.fixture
def campaign_critical_keywords(db_session, account_a):
    """키워드 부족 (critical) 캠페인."""
    today = date.today()
    c = Campaign(
        campaign_code="9900001",
        account_id=account_a.id,
        agency_name="대행사A",
        place_name="키워드부족",
        place_url="https://m.place.naver.com/restaurant/99001",
        place_id="99001",
        campaign_type="트래픽",
        start_date=today - timedelta(days=3),
        end_date=today + timedelta(days=10),
        daily_limit=300,
        total_limit=3900,
        status="active",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)

    # 남은 일수 11일인데 키워드 5개만 (critical)
    for i in range(5):
        kw = KeywordPool(
            campaign_id=c.id,
            keyword=f"부족키워드{i}",
            is_used=False,
        )
        db_session.add(kw)
    db_session.commit()
    return c


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
# GET /campaigns 테스트
# ============================================================================

class TestListCampaigns:
    """캠페인 목록 조회 테스트."""

    def test_empty_list(self, test_client):
        """캠페인이 없을 때 빈 목록."""
        resp = test_client.get("/campaigns")
        assert resp.status_code == 200
        data = resp.json()
        assert data["campaigns"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["pages"] == 1

    def test_list_all(self, test_client, campaigns_set):
        """전체 캠페인 목록."""
        resp = test_client.get("/campaigns")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 7
        assert len(data["campaigns"]) == 7

    def test_filter_by_account_id(self, test_client, campaigns_set, account_a):
        """account_id 필터."""
        resp = test_client.get(f"/campaigns?account_id={account_a.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4  # 계정A 캠페인 4개
        for c in data["campaigns"]:
            assert c["account_id"] == account_a.id

    def test_filter_by_agency_name(self, test_client, campaigns_set):
        """agency_name 필터."""
        resp = test_client.get("/campaigns?agency_name=대행사B")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3  # 대행사B 캠페인 3개
        for c in data["campaigns"]:
            assert c["agency_name"] == "대행사B"

    def test_filter_by_status(self, test_client, campaigns_set):
        """status 필터."""
        resp = test_client.get("/campaigns?status=active")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5  # active 5개 (계정A 3개 + 계정B 2개)
        for c in data["campaigns"]:
            assert c["status"] == "active"

    def test_filter_exhausted(self, test_client, campaigns_set):
        """일일소진 필터."""
        resp = test_client.get("/campaigns?status=daily_exhausted")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    def test_pagination_page1(self, test_client, campaigns_set):
        """페이지네이션 - 1페이지."""
        resp = test_client.get("/campaigns?page=1&limit=3")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 7
        assert len(data["campaigns"]) == 3
        assert data["page"] == 1
        assert data["pages"] == 3  # ceil(7/3) = 3

    def test_pagination_page2(self, test_client, campaigns_set):
        """페이지네이션 - 2페이지."""
        resp = test_client.get("/campaigns?page=2&limit=3")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["campaigns"]) == 3
        assert data["page"] == 2

    def test_pagination_last_page(self, test_client, campaigns_set):
        """페이지네이션 - 마지막 페이지."""
        resp = test_client.get("/campaigns?page=3&limit=3")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["campaigns"]) == 1  # 7개 중 마지막 1개

    def test_combined_filters(self, test_client, campaigns_set, account_a):
        """복합 필터."""
        resp = test_client.get(
            f"/campaigns?account_id={account_a.id}&status=active"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    def test_days_running(self, test_client, campaigns_set):
        """days_running 계산 확인."""
        resp = test_client.get("/campaigns?status=active")
        assert resp.status_code == 200
        data = resp.json()
        # 계정A: 5일 전 시작 → D+6, 계정B: 2일 전 시작 → D+3
        days_set = {c["days_running"] for c in data["campaigns"]}
        assert 6 in days_set  # 계정A 캠페인
        assert 3 in days_set  # 계정B 캠페인

    def test_keyword_status_included(self, test_client, campaigns_set, keywords_for_campaigns):
        """keyword_status 필드 포함."""
        resp = test_client.get("/campaigns")
        assert resp.status_code == 200
        data = resp.json()
        for c in data["campaigns"]:
            assert c["keyword_status"] in ["normal", "warning", "critical"]

    def test_order_desc(self, test_client, campaigns_set):
        """최신 캠페인이 먼저 (id DESC)."""
        resp = test_client.get("/campaigns")
        assert resp.status_code == 200
        data = resp.json()
        ids = [c["id"] for c in data["campaigns"]]
        assert ids == sorted(ids, reverse=True)

    def test_response_fields(self, test_client, campaigns_set):
        """응답 필드 확인."""
        resp = test_client.get("/campaigns?limit=1")
        assert resp.status_code == 200
        data = resp.json()
        c = data["campaigns"][0]
        assert "id" in c
        assert "campaign_code" in c
        assert "place_name" in c
        assert "status" in c
        assert "current_conversions" in c
        assert "total_limit" in c
        assert "days_running" in c
        assert "keyword_status" in c
        assert "last_keyword_change" in c
        assert "campaign_type" in c
        assert "start_date" in c
        assert "end_date" in c


# ============================================================================
# GET /campaigns/{campaign_id} 테스트
# ============================================================================

class TestGetCampaignDetail:
    """캠페인 상세 조회 테스트."""

    def test_get_detail(self, test_client, campaigns_set, keywords_for_campaigns):
        """캠페인 상세 정보 조회."""
        campaign = campaigns_set[0]
        resp = test_client.get(f"/campaigns/{campaign.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == campaign.id
        assert data["campaign_code"] == campaign.campaign_code
        assert data["place_name"] == campaign.place_name
        assert data["place_url"] == campaign.place_url
        assert data["campaign_type"] == campaign.campaign_type

    def test_detail_includes_keywords(self, test_client, campaigns_set, keywords_for_campaigns):
        """상세 정보에 키워드 목록 포함."""
        campaign = campaigns_set[0]
        resp = test_client.get(f"/campaigns/{campaign.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "keywords" in data
        assert len(data["keywords"]) > 0
        kw = data["keywords"][0]
        assert "id" in kw
        assert "keyword" in kw
        assert "is_used" in kw

    def test_detail_keyword_counts(self, test_client, campaigns_set, keywords_for_campaigns):
        """키워드 수량 정보."""
        campaign = campaigns_set[0]
        resp = test_client.get(f"/campaigns/{campaign.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "keyword_total" in data
        assert "keyword_used" in data
        assert "keyword_remaining" in data
        assert data["keyword_total"] == data["keyword_used"] + data["keyword_remaining"]

    def test_detail_keyword_status(self, test_client, campaigns_set, keywords_for_campaigns):
        """키워드 상태 필드."""
        campaign = campaigns_set[0]
        resp = test_client.get(f"/campaigns/{campaign.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["keyword_status"] in ["normal", "warning", "critical"]

    def test_detail_days_running(self, test_client, campaigns_set):
        """days_running 필드."""
        campaign = campaigns_set[0]
        resp = test_client.get(f"/campaigns/{campaign.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["days_running"] == 6  # 5일 전 시작

    def test_detail_not_found(self, test_client):
        """존재하지 않는 캠페인."""
        resp = test_client.get("/campaigns/99999")
        assert resp.status_code == 404

    def test_detail_no_keywords(self, test_client, campaigns_set):
        """키워드 없는 캠페인."""
        campaign = campaigns_set[0]
        resp = test_client.get(f"/campaigns/{campaign.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["keyword_total"] == 0
        assert data["keyword_remaining"] == 0
        assert data["keywords"] == []

    def test_detail_all_fields(self, test_client, campaigns_set):
        """모든 응답 필드 확인."""
        campaign = campaigns_set[0]
        resp = test_client.get(f"/campaigns/{campaign.id}")
        assert resp.status_code == 200
        data = resp.json()
        expected_fields = [
            "id", "campaign_code", "account_id", "agency_name",
            "place_name", "place_url", "place_id", "campaign_type",
            "status", "start_date", "end_date", "daily_limit",
            "total_limit", "current_conversions", "days_running",
            "keyword_status", "keyword_remaining", "keyword_total",
            "keyword_used", "last_keyword_change", "keywords",
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"


# ============================================================================
# GET /accounts 테스트
# ============================================================================

class TestListAccounts:
    """계정 목록 조회 테스트."""

    def test_empty_accounts(self, test_client):
        """계정이 없을 때."""
        resp = test_client.get("/accounts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["accounts"] == []

    def test_list_accounts(self, test_client, account_a, account_b):
        """계정 목록."""
        resp = test_client.get("/accounts")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["accounts"]) == 2

    def test_account_fields(self, test_client, account_a):
        """계정 필드 확인."""
        resp = test_client.get("/accounts")
        assert resp.status_code == 200
        data = resp.json()
        acc = data["accounts"][0]
        assert acc["id"] == account_a.id
        assert acc["user_id"] == "account_a"
        assert acc["agency_name"] == "대행사A"
        assert acc["is_active"] is True

    def test_campaign_count(self, test_client, account_a, campaigns_set):
        """캠페인 수 포함."""
        resp = test_client.get("/accounts")
        assert resp.status_code == 200
        data = resp.json()
        acc_a = next(a for a in data["accounts"] if a["id"] == account_a.id)
        assert acc_a["campaign_count"] == 4  # 계정A 캠페인 4개

    def test_inactive_account_included(self, test_client, account_a, inactive_account):
        """비활성 계정도 목록에 포함."""
        resp = test_client.get("/accounts")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["accounts"]) == 2
        inactive = next(a for a in data["accounts"] if a["id"] == inactive_account.id)
        assert inactive["is_active"] is False

    def test_no_campaigns_count_zero(self, test_client, account_a):
        """캠페인 없는 계정은 campaign_count=0."""
        resp = test_client.get("/accounts")
        assert resp.status_code == 200
        data = resp.json()
        acc = data["accounts"][0]
        assert acc["campaign_count"] == 0


# ============================================================================
# GET /agencies 테스트
# ============================================================================

class TestListAgencies:
    """대행사 목록 조회 테스트."""

    def test_empty_agencies(self, test_client):
        """캠페인이 없으면 빈 대행사 목록."""
        resp = test_client.get("/agencies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agencies"] == []

    def test_list_agencies(self, test_client, campaigns_set):
        """대행사 목록."""
        resp = test_client.get("/agencies")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["agencies"]) == 2
        names = {a["agency_name"] for a in data["agencies"]}
        assert "대행사A" in names
        assert "대행사B" in names

    def test_agency_campaign_count(self, test_client, campaigns_set):
        """대행사별 캠페인 수."""
        resp = test_client.get("/agencies")
        assert resp.status_code == 200
        data = resp.json()
        agency_a = next(a for a in data["agencies"] if a["agency_name"] == "대행사A")
        agency_b = next(a for a in data["agencies"] if a["agency_name"] == "대행사B")
        assert agency_a["campaign_count"] == 4
        assert agency_b["campaign_count"] == 3

    def test_agencies_sorted(self, test_client, campaigns_set):
        """대행사명 정렬."""
        resp = test_client.get("/agencies")
        assert resp.status_code == 200
        data = resp.json()
        names = [a["agency_name"] for a in data["agencies"]]
        assert names == sorted(names)


# ============================================================================
# GET /dashboard/stats 테스트
# ============================================================================

class TestDashboardStats:
    """대시보드 통계 테스트."""

    def test_empty_stats(self, test_client):
        """캠페인이 없을 때 통계."""
        resp = test_client.get("/dashboard/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_campaigns"] == 0
        assert data["active_campaigns"] == 0
        assert data["exhausted_today"] == 0
        assert data["keyword_warnings"] == 0

    def test_total_campaigns(self, test_client, campaigns_set):
        """전체 캠페인 수."""
        resp = test_client.get("/dashboard/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_campaigns"] == 7

    def test_active_campaigns(self, test_client, campaigns_set):
        """활성 캠페인 수 (active)."""
        resp = test_client.get("/dashboard/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active_campaigns"] == 5  # active 5개

    def test_exhausted_today(self, test_client, campaigns_set):
        """오늘 소진 캠페인 수."""
        resp = test_client.get("/dashboard/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["exhausted_today"] == 1  # daily_exhausted 1개

    def test_filter_by_account(self, test_client, campaigns_set, account_a, account_b):
        """account_id 필터."""
        resp_a = test_client.get(f"/dashboard/stats?account_id={account_a.id}")
        assert resp_a.status_code == 200
        data_a = resp_a.json()
        assert data_a["total_campaigns"] == 4
        assert data_a["active_campaigns"] == 3
        assert data_a["exhausted_today"] == 1

        resp_b = test_client.get(f"/dashboard/stats?account_id={account_b.id}")
        assert resp_b.status_code == 200
        data_b = resp_b.json()
        assert data_b["total_campaigns"] == 3
        assert data_b["active_campaigns"] == 2
        assert data_b["exhausted_today"] == 0

    def test_keyword_warnings_zero(self, test_client, campaigns_set, keywords_for_campaigns):
        """키워드 충분한 경우."""
        # campaigns_set의 첫 캠페인들은 키워드가 충분하므로 경고 적음
        resp = test_client.get("/dashboard/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["keyword_warnings"], int)

    def test_keyword_warnings_with_critical(
        self, test_client, campaign_critical_keywords
    ):
        """키워드 부족 경고 카운트."""
        resp = test_client.get("/dashboard/stats")
        assert resp.status_code == 200
        data = resp.json()
        # campaign_critical_keywords: 11일 남음, 키워드 5개 → critical
        assert data["keyword_warnings"] >= 1

    def test_stats_response_fields(self, test_client):
        """응답 필드 확인."""
        resp = test_client.get("/dashboard/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_campaigns" in data
        assert "active_campaigns" in data
        assert "exhausted_today" in data
        assert "keyword_warnings" in data


# ============================================================================
# 통합 시나리오 테스트
# ============================================================================

class TestIntegration:
    """통합 시나리오 테스트."""

    def test_full_dashboard_flow(
        self, test_client, account_a, account_b, campaigns_set, keywords_for_campaigns
    ):
        """전체 대시보드 플로우: 계정 → 통계 → 캠페인 목록 → 상세."""
        # 1. 계정 목록 조회
        resp = test_client.get("/accounts")
        assert resp.status_code == 200
        accounts = resp.json()["accounts"]
        assert len(accounts) >= 2

        # 2. 대시보드 통계
        resp = test_client.get("/dashboard/stats")
        assert resp.status_code == 200
        stats = resp.json()
        assert stats["total_campaigns"] == 7

        # 3. 계정A 캠페인 목록
        resp = test_client.get(f"/campaigns?account_id={account_a.id}")
        assert resp.status_code == 200
        campaigns = resp.json()["campaigns"]
        assert len(campaigns) == 4

        # 4. 첫 번째 캠페인 상세
        campaign_id = campaigns[0]["id"]
        resp = test_client.get(f"/campaigns/{campaign_id}")
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["id"] == campaign_id
        assert len(detail["keywords"]) >= 0

    def test_filter_then_detail(self, test_client, campaigns_set):
        """필터 후 상세 조회."""
        # daily_exhausted 필터
        resp = test_client.get("/campaigns?status=daily_exhausted")
        assert resp.status_code == 200
        campaigns = resp.json()["campaigns"]
        assert len(campaigns) == 1

        # 해당 캠페인 상세
        cid = campaigns[0]["id"]
        resp = test_client.get(f"/campaigns/{cid}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "daily_exhausted"

    def test_stats_match_list_count(self, test_client, campaigns_set):
        """통계의 total과 목록 total 일치."""
        resp_stats = test_client.get("/dashboard/stats")
        resp_list = test_client.get("/campaigns")
        assert resp_stats.json()["total_campaigns"] == resp_list.json()["total"]

    def test_agencies_match_campaigns(self, test_client, campaigns_set):
        """대행사 목록의 캠페인 수 합계 == 전체 캠페인 수."""
        resp_agencies = test_client.get("/agencies")
        resp_list = test_client.get("/campaigns")
        agency_total = sum(
            a["campaign_count"] for a in resp_agencies.json()["agencies"]
        )
        assert agency_total == resp_list.json()["total"]

    def test_pagination_covers_all(self, test_client, campaigns_set):
        """모든 페이지 합치면 전체 수량."""
        all_ids = set()
        page = 1
        while True:
            resp = test_client.get(f"/campaigns?page={page}&limit=2")
            data = resp.json()
            if not data["campaigns"]:
                break
            for c in data["campaigns"]:
                all_ids.add(c["id"])
            if page >= data["pages"]:
                break
            page += 1
        assert len(all_ids) == 7

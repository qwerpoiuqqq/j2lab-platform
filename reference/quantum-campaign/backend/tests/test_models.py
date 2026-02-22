"""모델 CRUD 테스트."""

import pytest
from datetime import date, datetime, timezone

from app.models import Account, CampaignTemplate, Campaign, KeywordPool


class TestAccountModel:
    """Account 모델 테스트."""

    def test_create_account(self, db_session):
        """Account 생성 테스트."""
        account = Account(
            user_id="test_user",
            password_encrypted="encrypted_password",
            agency_name="테스트 대행사",
            is_active=True,
        )
        db_session.add(account)
        db_session.commit()
        db_session.refresh(account)

        assert account.id is not None
        assert account.user_id == "test_user"
        assert account.agency_name == "테스트 대행사"
        assert account.is_active is True
        assert account.created_at is not None

    def test_account_user_id_unique(self, db_session):
        """Account user_id 유니크 제약 테스트."""
        account1 = Account(user_id="unique_user", agency_name="대행사1")
        db_session.add(account1)
        db_session.commit()

        account2 = Account(user_id="unique_user", agency_name="대행사2")
        db_session.add(account2)

        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()

    def test_account_repr(self, db_session):
        """Account __repr__ 테스트."""
        account = Account(user_id="repr_test")
        db_session.add(account)
        db_session.commit()

        assert "Account" in repr(account)
        assert "repr_test" in repr(account)


class TestCampaignTemplateModel:
    """CampaignTemplate 모델 테스트."""

    def test_create_template(self, db_session):
        """CampaignTemplate 생성 테스트."""
        template = CampaignTemplate(
            type_name="트래픽",
            description_template="테스트 설명 템플릿",
            hint_text="테스트 힌트",
            campaign_type_selection="플레이스 퀴즈",
            links=["https://example.com/1", "https://example.com/2"],
            hashtag="#test",
        )
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)

        assert template.id is not None
        assert template.type_name == "트래픽"
        assert len(template.links) == 2
        assert template.hashtag == "#test"

    def test_template_type_name_unique(self, db_session):
        """CampaignTemplate type_name 유니크 제약 테스트."""
        template1 = CampaignTemplate(
            type_name="저장하기",
            description_template="설명1",
            hint_text="힌트1",
            links=[],
        )
        db_session.add(template1)
        db_session.commit()

        template2 = CampaignTemplate(
            type_name="저장하기",
            description_template="설명2",
            hint_text="힌트2",
            links=[],
        )
        db_session.add(template2)

        with pytest.raises(Exception):
            db_session.commit()


class TestCampaignModel:
    """Campaign 모델 테스트."""

    def test_create_campaign(self, db_session):
        """Campaign 생성 테스트."""
        campaign = Campaign(
            place_name="테스트 플레이스",
            place_url="https://place.naver.com/test",
            campaign_type="트래픽",
            start_date=date(2026, 2, 4),
            end_date=date(2026, 2, 10),
            daily_limit=300,
            status="pending",
        )
        db_session.add(campaign)
        db_session.commit()
        db_session.refresh(campaign)

        assert campaign.id is not None
        assert campaign.place_name == "테스트 플레이스"
        assert campaign.status == "pending"
        assert campaign.current_conversions == 0

    def test_campaign_with_optional_fields(self, db_session):
        """Campaign 선택적 필드 테스트."""
        campaign = Campaign(
            place_name="옵션 테스트",
            place_url="https://place.naver.com/opt",
            campaign_type="저장하기",
            start_date=date(2026, 2, 4),
            end_date=date(2026, 2, 10),
            daily_limit=100,
            total_limit=700,
            landmark_name="남산타워",
            step_count=1500,
            original_keywords="키워드1,키워드2,키워드3",
        )
        db_session.add(campaign)
        db_session.commit()
        db_session.refresh(campaign)

        assert campaign.total_limit == 700
        assert campaign.landmark_name == "남산타워"
        assert campaign.step_count == 1500


class TestKeywordPoolModel:
    """KeywordPool 모델 테스트."""

    def test_create_keyword(self, db_session):
        """KeywordPool 생성 테스트."""
        # 먼저 캠페인 생성
        campaign = Campaign(
            place_name="키워드 테스트",
            place_url="https://place.naver.com/kw",
            campaign_type="트래픽",
            start_date=date(2026, 2, 4),
            end_date=date(2026, 2, 10),
            daily_limit=300,
        )
        db_session.add(campaign)
        db_session.commit()

        keyword = KeywordPool(
            campaign_id=campaign.id,
            keyword="테스트 키워드",
            is_used=False,
        )
        db_session.add(keyword)
        db_session.commit()
        db_session.refresh(keyword)

        assert keyword.id is not None
        assert keyword.keyword == "테스트 키워드"
        assert keyword.is_used is False
        assert keyword.used_at is None

    def test_keyword_used_at(self, db_session):
        """KeywordPool 사용일시 업데이트 테스트."""
        campaign = Campaign(
            place_name="사용일시 테스트",
            place_url="https://place.naver.com/used",
            campaign_type="트래픽",
            start_date=date(2026, 2, 4),
            end_date=date(2026, 2, 10),
            daily_limit=300,
        )
        db_session.add(campaign)
        db_session.commit()

        keyword = KeywordPool(
            campaign_id=campaign.id,
            keyword="사용된 키워드",
            is_used=True,
            used_at=datetime.now(timezone.utc),
        )
        db_session.add(keyword)
        db_session.commit()
        db_session.refresh(keyword)

        assert keyword.is_used is True
        assert keyword.used_at is not None

    def test_keyword_unique_constraint(self, db_session):
        """KeywordPool 캠페인+키워드 유니크 제약 테스트."""
        campaign = Campaign(
            place_name="유니크 테스트",
            place_url="https://place.naver.com/uniq",
            campaign_type="트래픽",
            start_date=date(2026, 2, 4),
            end_date=date(2026, 2, 10),
            daily_limit=300,
        )
        db_session.add(campaign)
        db_session.commit()

        kw1 = KeywordPool(campaign_id=campaign.id, keyword="중복키워드")
        db_session.add(kw1)
        db_session.commit()

        kw2 = KeywordPool(campaign_id=campaign.id, keyword="중복키워드")
        db_session.add(kw2)

        with pytest.raises(Exception):
            db_session.commit()

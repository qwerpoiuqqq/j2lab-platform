"""모델 관계(relationship) 테스트."""

import pytest
from datetime import date

from app.models import Account, Campaign, KeywordPool


class TestAccountCampaignRelationship:
    """Account-Campaign 관계 테스트."""

    def test_account_has_campaigns(self, db_session):
        """Account에서 campaigns 접근 테스트."""
        # Account 생성
        account = Account(user_id="rel_test_user", agency_name="관계 테스트 대행사")
        db_session.add(account)
        db_session.commit()

        # Campaign 2개 생성
        campaign1 = Campaign(
            account_id=account.id,
            place_name="플레이스1",
            place_url="https://place.naver.com/1",
            campaign_type="트래픽",
            start_date=date(2026, 2, 4),
            end_date=date(2026, 2, 10),
            daily_limit=300,
        )
        campaign2 = Campaign(
            account_id=account.id,
            place_name="플레이스2",
            place_url="https://place.naver.com/2",
            campaign_type="저장하기",
            start_date=date(2026, 2, 5),
            end_date=date(2026, 2, 15),
            daily_limit=200,
        )
        db_session.add_all([campaign1, campaign2])
        db_session.commit()

        # 관계 확인
        db_session.refresh(account)
        assert len(account.campaigns) == 2
        assert campaign1 in account.campaigns
        assert campaign2 in account.campaigns

    def test_campaign_has_account(self, db_session):
        """Campaign에서 account 접근 테스트."""
        account = Account(user_id="back_rel_user", agency_name="역관계 테스트")
        db_session.add(account)
        db_session.commit()

        campaign = Campaign(
            account_id=account.id,
            place_name="역관계 플레이스",
            place_url="https://place.naver.com/back",
            campaign_type="트래픽",
            start_date=date(2026, 2, 4),
            end_date=date(2026, 2, 10),
            daily_limit=300,
        )
        db_session.add(campaign)
        db_session.commit()

        db_session.refresh(campaign)
        assert campaign.account is not None
        assert campaign.account.user_id == "back_rel_user"

    def test_campaign_without_account(self, db_session):
        """Account 없는 Campaign 테스트 (허용됨)."""
        campaign = Campaign(
            place_name="계정없는 플레이스",
            place_url="https://place.naver.com/no_account",
            campaign_type="트래픽",
            start_date=date(2026, 2, 4),
            end_date=date(2026, 2, 10),
            daily_limit=300,
        )
        db_session.add(campaign)
        db_session.commit()
        db_session.refresh(campaign)

        assert campaign.account_id is None
        assert campaign.account is None


class TestCampaignKeywordRelationship:
    """Campaign-KeywordPool 관계 테스트."""

    def test_campaign_has_keywords(self, db_session):
        """Campaign에서 keywords 접근 테스트."""
        campaign = Campaign(
            place_name="키워드 관계 테스트",
            place_url="https://place.naver.com/kw_rel",
            campaign_type="트래픽",
            start_date=date(2026, 2, 4),
            end_date=date(2026, 2, 10),
            daily_limit=300,
        )
        db_session.add(campaign)
        db_session.commit()

        # 키워드 3개 추가
        keywords = [
            KeywordPool(campaign_id=campaign.id, keyword="마포 맛집"),
            KeywordPool(campaign_id=campaign.id, keyword="마포 곱창"),
            KeywordPool(campaign_id=campaign.id, keyword="공덕 맛집"),
        ]
        db_session.add_all(keywords)
        db_session.commit()

        db_session.refresh(campaign)
        assert len(campaign.keywords) == 3

    def test_keyword_has_campaign(self, db_session):
        """KeywordPool에서 campaign 접근 테스트."""
        campaign = Campaign(
            place_name="역관계 키워드 테스트",
            place_url="https://place.naver.com/kw_back",
            campaign_type="저장하기",
            start_date=date(2026, 2, 4),
            end_date=date(2026, 2, 10),
            daily_limit=200,
        )
        db_session.add(campaign)
        db_session.commit()

        keyword = KeywordPool(campaign_id=campaign.id, keyword="테스트키워드")
        db_session.add(keyword)
        db_session.commit()

        db_session.refresh(keyword)
        assert keyword.campaign is not None
        assert keyword.campaign.place_name == "역관계 키워드 테스트"

    def test_cascade_delete_keywords(self, db_session):
        """Campaign 삭제 시 KeywordPool cascade 삭제 테스트."""
        campaign = Campaign(
            place_name="캐스케이드 테스트",
            place_url="https://place.naver.com/cascade",
            campaign_type="트래픽",
            start_date=date(2026, 2, 4),
            end_date=date(2026, 2, 10),
            daily_limit=300,
        )
        db_session.add(campaign)
        db_session.commit()

        # 키워드 추가
        kw1 = KeywordPool(campaign_id=campaign.id, keyword="삭제될키워드1")
        kw2 = KeywordPool(campaign_id=campaign.id, keyword="삭제될키워드2")
        db_session.add_all([kw1, kw2])
        db_session.commit()

        campaign_id = campaign.id

        # 캠페인 삭제
        db_session.delete(campaign)
        db_session.commit()

        # 키워드도 삭제되었는지 확인
        remaining = db_session.query(KeywordPool).filter(
            KeywordPool.campaign_id == campaign_id
        ).count()
        assert remaining == 0


class TestComplexRelationship:
    """복합 관계 테스트."""

    def test_full_hierarchy(self, db_session):
        """Account -> Campaign -> Keywords 전체 계층 테스트."""
        # Account 생성
        account = Account(user_id="hierarchy_user", agency_name="계층 테스트 대행사")
        db_session.add(account)
        db_session.commit()

        # Campaign 생성
        campaign = Campaign(
            account_id=account.id,
            agency_name=account.agency_name,
            place_name="계층 테스트 플레이스",
            place_url="https://place.naver.com/hierarchy",
            campaign_type="트래픽",
            start_date=date(2026, 2, 4),
            end_date=date(2026, 2, 10),
            daily_limit=300,
            original_keywords="키워드1,키워드2,키워드3",
        )
        db_session.add(campaign)
        db_session.commit()

        # Keywords 생성
        for kw in campaign.original_keywords.split(","):
            keyword = KeywordPool(campaign_id=campaign.id, keyword=kw.strip())
            db_session.add(keyword)
        db_session.commit()

        # 전체 계층 확인
        db_session.refresh(account)
        db_session.refresh(campaign)

        # Account -> Campaign
        assert len(account.campaigns) == 1
        assert account.campaigns[0].place_name == "계층 테스트 플레이스"

        # Campaign -> Keywords
        assert len(campaign.keywords) == 3

        # Keywords -> Campaign -> Account
        keyword = campaign.keywords[0]
        assert keyword.campaign.account.user_id == "hierarchy_user"

    def test_multiple_accounts_campaigns_keywords(self, db_session):
        """다중 Account/Campaign/Keywords 테스트."""
        # 2개 Account 생성
        account1 = Account(user_id="multi_user1", agency_name="대행사A")
        account2 = Account(user_id="multi_user2", agency_name="대행사B")
        db_session.add_all([account1, account2])
        db_session.commit()

        # 각 Account에 2개씩 Campaign 생성
        campaigns = []
        for acc in [account1, account2]:
            for i in range(2):
                campaign = Campaign(
                    account_id=acc.id,
                    place_name=f"{acc.agency_name} 플레이스{i+1}",
                    place_url=f"https://place.naver.com/{acc.user_id}/{i}",
                    campaign_type="트래픽",
                    start_date=date(2026, 2, 4),
                    end_date=date(2026, 2, 10),
                    daily_limit=300,
                )
                campaigns.append(campaign)
        db_session.add_all(campaigns)
        db_session.commit()

        # 각 Campaign에 2개씩 Keyword 생성
        for campaign in campaigns:
            for j in range(2):
                kw = KeywordPool(
                    campaign_id=campaign.id,
                    keyword=f"키워드{campaign.id}_{j}"
                )
                db_session.add(kw)
        db_session.commit()

        # 검증
        db_session.refresh(account1)
        db_session.refresh(account2)

        assert len(account1.campaigns) == 2
        assert len(account2.campaigns) == 2

        total_keywords = db_session.query(KeywordPool).count()
        assert total_keywords == 8  # 4 campaigns * 2 keywords

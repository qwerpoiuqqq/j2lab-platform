"""Tests for campaigns endpoints."""

from __future__ import annotations

from datetime import date

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign, CampaignStatus
from app.models.campaign_keyword_pool import CampaignKeywordPool
from app.models.company import Company
from app.models.place import Place
from app.models.user import User, UserRole
from tests.conftest import (
    create_test_company,
    create_test_user,
    get_auth_header,
)


async def create_test_place(
    db: AsyncSession,
    place_id: int = 1234567890,
    name: str = "Test Place",
) -> Place:
    place = Place(id=place_id, name=name, place_type="restaurant")
    db.add(place)
    await db.flush()
    await db.refresh(place)
    return place


async def create_test_campaign(
    db: AsyncSession,
    place_id: int | None = None,
    campaign_type: str = "traffic",
    status: str = CampaignStatus.PENDING.value,
    company_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    daily_limit: int = 300,
    total_limit: int | None = None,
    superap_account_id: int | None = None,
    network_preset_id: int | None = None,
) -> Campaign:
    campaign = Campaign(
        place_id=place_id,
        place_url="https://map.naver.com/p/entry/place/123",
        place_name="Test Place",
        campaign_type=campaign_type,
        status=status,
        company_id=company_id,
        start_date=start_date or date(2026, 3, 1),
        end_date=end_date or date(2026, 3, 31),
        daily_limit=daily_limit,
        total_limit=total_limit,
        superap_account_id=superap_account_id,
        network_preset_id=network_preset_id,
    )
    db.add(campaign)
    await db.flush()
    await db.refresh(campaign)
    return campaign


@pytest.mark.asyncio
class TestListCampaigns:
    """Tests for GET /api/v1/campaigns."""

    async def test_list_campaigns(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        admin = await create_test_user(
            db_session, email="admin@test.com", role=UserRole.COMPANY_ADMIN,
            company_id=test_company.id,
        )
        await create_test_campaign(db_session, company_id=test_company.id)
        await create_test_campaign(db_session, company_id=test_company.id, campaign_type="save")
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.get("/api/v1/campaigns/", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    async def test_list_campaigns_filter_status(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        system_admin: User,
    ):
        await create_test_campaign(db_session, status="pending")
        await create_test_campaign(db_session, status="active")
        await db_session.commit()

        headers = get_auth_header(system_admin)
        resp = await client.get("/api/v1/campaigns/?status=active", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    async def test_list_campaigns_company_scoped(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """Company admin sees only own company campaigns."""
        company2 = await create_test_company(db_session, name="Other", code="other")
        admin = await create_test_user(
            db_session, email="admin@test.com", role=UserRole.COMPANY_ADMIN,
            company_id=test_company.id,
        )
        await create_test_campaign(db_session, company_id=test_company.id)
        await create_test_campaign(db_session, company_id=company2.id)
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.get("/api/v1/campaigns/", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 1


@pytest.mark.asyncio
class TestCreateCampaign:
    """Tests for POST /api/v1/campaigns."""

    async def test_create_campaign(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        system_admin: User,
    ):
        await db_session.commit()
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/campaigns/",
            json={
                "place_url": "https://map.naver.com/p/entry/place/123",
                "place_name": "Test Place",
                "campaign_type": "traffic",
                "start_date": "2026-03-01",
                "end_date": "2026-03-31",
                "daily_limit": 300,
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["campaign_type"] == "traffic"
        assert data["status"] == "pending"

    async def test_create_campaign_unauthorized(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        sub = await create_test_user(
            db_session, email="sub@test.com", role=UserRole.SUB_ACCOUNT,
            company_id=test_company.id,
        )
        await db_session.commit()

        headers = get_auth_header(sub)
        resp = await client.post(
            "/api/v1/campaigns/",
            json={
                "place_url": "https://map.naver.com/p/entry/place/123",
                "campaign_type": "traffic",
                "start_date": "2026-03-01",
                "end_date": "2026-03-31",
                "daily_limit": 300,
            },
            headers=headers,
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestCampaignKeywordPool:
    """Tests for campaign keyword pool."""

    async def test_add_keywords(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        system_admin: User,
    ):
        campaign = await create_test_campaign(db_session)
        await db_session.commit()

        headers = get_auth_header(system_admin)
        resp = await client.post(
            f"/api/v1/campaigns/{campaign.id}/keywords",
            json={"keywords": ["kw1", "kw2", "kw3"], "round_number": 1},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["detail"]["added"] == 3

    async def test_add_duplicate_keywords(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        system_admin: User,
    ):
        campaign = await create_test_campaign(db_session)
        # Add initial keywords
        pool = CampaignKeywordPool(
            campaign_id=campaign.id, keyword="existing", round_number=1,
        )
        db_session.add(pool)
        await db_session.commit()

        headers = get_auth_header(system_admin)
        resp = await client.post(
            f"/api/v1/campaigns/{campaign.id}/keywords",
            json={"keywords": ["existing", "new_one"], "round_number": 2},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["detail"]["added"] == 1  # Only "new_one"

    async def test_list_keyword_pool(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        system_admin: User,
    ):
        campaign = await create_test_campaign(db_session)
        for i in range(3):
            db_session.add(
                CampaignKeywordPool(
                    campaign_id=campaign.id, keyword=f"kw{i}", round_number=1,
                )
            )
        await db_session.commit()

        headers = get_auth_header(system_admin)
        resp = await client.get(
            f"/api/v1/campaigns/{campaign.id}/keywords",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 3

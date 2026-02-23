"""Tests for network presets endpoints."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.network_preset import NetworkPreset
from app.models.user import User, UserRole
from tests.conftest import (
    create_test_company,
    create_test_user,
    get_auth_header,
)


async def create_test_preset(
    db: AsyncSession,
    company_id: int,
    campaign_type: str = "traffic",
    tier_order: int = 1,
    name: str = "Network 1",
    is_active: bool = True,
) -> NetworkPreset:
    preset = NetworkPreset(
        company_id=company_id,
        campaign_type=campaign_type,
        tier_order=tier_order,
        name=name,
        media_config={"머니워크": True},
        is_active=is_active,
    )
    db.add(preset)
    await db.flush()
    await db.refresh(preset)
    return preset


@pytest.mark.asyncio
class TestListNetworkPresets:
    """Tests for GET /api/v1/network-presets."""

    async def test_list_presets_as_system_admin(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        system_admin: User,
        test_company: Company,
    ):
        await create_test_preset(db_session, test_company.id, tier_order=1)
        await create_test_preset(db_session, test_company.id, tier_order=2, name="Net 2")
        await db_session.commit()

        headers = get_auth_header(system_admin)
        resp = await client.get("/api/v1/network-presets/", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    async def test_list_presets_company_scoped(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """Company admin sees only own company presets."""
        company2 = await create_test_company(db_session, name="Other", code="other")
        admin = await create_test_user(
            db_session, email="cadmin@test.com", role=UserRole.COMPANY_ADMIN,
            company_id=test_company.id,
        )
        await create_test_preset(db_session, test_company.id, tier_order=1)
        await create_test_preset(db_session, company2.id, tier_order=1, name="Other Net")
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.get("/api/v1/network-presets/", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    async def test_list_presets_filter_campaign_type(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        system_admin: User,
        test_company: Company,
    ):
        await create_test_preset(db_session, test_company.id, campaign_type="traffic", tier_order=1)
        await create_test_preset(db_session, test_company.id, campaign_type="save", tier_order=1, name="Save Net")
        await db_session.commit()

        headers = get_auth_header(system_admin)
        resp = await client.get(
            "/api/v1/network-presets/?campaign_type=traffic",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    async def test_list_presets_unauthorized(
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
        resp = await client.get("/api/v1/network-presets/", headers=headers)
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestCreateNetworkPreset:
    """Tests for POST /api/v1/network-presets."""

    async def test_create_preset(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        system_admin: User,
        test_company: Company,
    ):
        await db_session.commit()
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/network-presets/",
            json={
                "company_id": test_company.id,
                "campaign_type": "traffic",
                "tier_order": 1,
                "name": "Network 1 (21won)",
                "media_config": {"머니워크": True},
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["tier_order"] == 1
        assert data["campaign_type"] == "traffic"

    async def test_create_preset_company_admin_own_company(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        admin = await create_test_user(
            db_session, email="cadmin@test.com", role=UserRole.COMPANY_ADMIN,
            company_id=test_company.id,
        )
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.post(
            "/api/v1/network-presets/",
            json={
                "company_id": test_company.id,
                "campaign_type": "traffic",
                "tier_order": 1,
                "name": "Net 1",
            },
            headers=headers,
        )
        assert resp.status_code == 201

    async def test_create_preset_company_admin_other_company(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """Company admin cannot create for another company."""
        company2 = await create_test_company(db_session, name="Other", code="other")
        admin = await create_test_user(
            db_session, email="cadmin@test.com", role=UserRole.COMPANY_ADMIN,
            company_id=test_company.id,
        )
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.post(
            "/api/v1/network-presets/",
            json={
                "company_id": company2.id,
                "campaign_type": "traffic",
                "tier_order": 1,
                "name": "Net 1",
            },
            headers=headers,
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestUpdateDeleteNetworkPreset:
    """Tests for PATCH/DELETE /api/v1/network-presets/{id}."""

    async def test_update_preset(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        system_admin: User,
        test_company: Company,
    ):
        preset = await create_test_preset(db_session, test_company.id)
        await db_session.commit()

        headers = get_auth_header(system_admin)
        resp = await client.patch(
            f"/api/v1/network-presets/{preset.id}",
            json={"name": "Updated Name", "media_config": {"머니워크": False}},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"

    async def test_delete_preset_system_admin_only(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        admin = await create_test_user(
            db_session, email="cadmin@test.com", role=UserRole.COMPANY_ADMIN,
            company_id=test_company.id,
        )
        preset = await create_test_preset(db_session, test_company.id)
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.delete(
            f"/api/v1/network-presets/{preset.id}",
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_delete_preset_as_system_admin(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        system_admin: User,
        test_company: Company,
    ):
        preset = await create_test_preset(db_session, test_company.id)
        await db_session.commit()

        headers = get_auth_header(system_admin)
        resp = await client.delete(
            f"/api/v1/network-presets/{preset.id}",
            headers=headers,
        )
        assert resp.status_code == 204

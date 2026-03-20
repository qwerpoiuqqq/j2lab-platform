from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign_template import CampaignTemplate
from app.models.user import User
from tests.conftest import get_auth_header


@pytest.mark.asyncio
class TestCampaignTemplateReadScope:
    async def test_company_admin_can_list_shared_templates(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        company_admin: User,
    ):
        template = CampaignTemplate(
            code="traffic",
            type_name="트래픽 기본",
            description_template="설명",
            hint_text="힌트",
            modules=["place_info"],
            links=[],
            is_active=True,
        )
        db_session.add(template)
        await db_session.commit()

        headers = get_auth_header(company_admin)
        resp = await client.get("/api/v1/templates/", headers=headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["code"] == "traffic"


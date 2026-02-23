"""Tests for internal callback endpoints (worker -> api-server)."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.campaign import Campaign, CampaignStatus
from app.models.extraction_job import ExtractionJob, ExtractionJobStatus
from app.models.order import Order, OrderItem, OrderStatus
from app.models.pipeline_state import PipelineState, PipelineStage
from app.models.place import Place
from app.models.product import Product
from app.models.user import User, UserRole
from app.services import pipeline_service
from tests.conftest import (
    create_test_company,
    create_test_user,
    get_auth_header,
)


async def _create_extraction_setup(db, company, user):
    """Create order_item, extraction_job, pipeline_state for testing."""
    from datetime import time
    import secrets

    product = Product(name="Traffic", code=f"t_{secrets.token_hex(2)}", base_price=10000, daily_deadline=time(18, 0))
    db.add(product)
    await db.flush()

    order = Order(
        order_number=f"ORD-TEST-{secrets.token_hex(2).upper()}",
        user_id=user.id,
        company_id=company.id,
        status=OrderStatus.PROCESSING.value,
    )
    db.add(order)
    await db.flush()

    oi = OrderItem(
        order_id=order.id,
        product_id=product.id,
        quantity=1,
        unit_price=10000,
        subtotal=10000,
    )
    db.add(oi)
    await db.flush()

    job = ExtractionJob(
        order_item_id=oi.id,
        naver_url="https://map.naver.com/p/entry/place/123",
        status=ExtractionJobStatus.RUNNING.value,
    )
    db.add(job)
    await db.flush()

    # Create pipeline state at extraction_running
    state = PipelineState(
        order_item_id=oi.id,
        current_stage=PipelineStage.EXTRACTION_RUNNING.value,
    )
    db.add(state)
    await db.flush()
    await db.refresh(job)
    await db.refresh(oi)

    return oi, job, state


async def _create_campaign_setup(db, company, user):
    """Create order_item, campaign, pipeline_state for testing."""
    from datetime import date, time
    import secrets

    product = Product(name="Traffic", code=f"t_{secrets.token_hex(2)}", base_price=10000, daily_deadline=time(18, 0))
    db.add(product)
    await db.flush()

    order = Order(
        order_number=f"ORD-TEST-{secrets.token_hex(2).upper()}",
        user_id=user.id,
        company_id=company.id,
        status=OrderStatus.PROCESSING.value,
    )
    db.add(order)
    await db.flush()

    oi = OrderItem(
        order_id=order.id,
        product_id=product.id,
        quantity=1,
        unit_price=10000,
        subtotal=10000,
    )
    db.add(oi)
    await db.flush()

    campaign = Campaign(
        order_item_id=oi.id,
        place_url="https://map.naver.com/p/entry/place/123",
        place_name="Test",
        campaign_type="traffic",
        status=CampaignStatus.REGISTERING.value,
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
        daily_limit=300,
    )
    db.add(campaign)
    await db.flush()

    state = PipelineState(
        order_item_id=oi.id,
        current_stage=PipelineStage.CAMPAIGN_REGISTERING.value,
    )
    db.add(state)
    await db.flush()
    await db.refresh(campaign)

    return oi, campaign, state


@pytest.mark.asyncio
class TestExtractionCallback:
    """Tests for POST /internal/callback/extraction/{job_id}."""

    async def test_extraction_completed(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        oi, job, state = await _create_extraction_setup(
            db_session, test_company, distributor,
        )
        await db_session.commit()

        resp = await client.post(
            f"/internal/callback/extraction/{job.id}",
            json={
                "status": "completed",
                "result_count": 200,
                "place_id": 1234567890,
                "place_name": "Test Place",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"].startswith("Extraction callback processed")

    async def test_extraction_failed(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        oi, job, state = await _create_extraction_setup(
            db_session, test_company, distributor,
        )
        await db_session.commit()

        resp = await client.post(
            f"/internal/callback/extraction/{job.id}",
            json={
                "status": "failed",
                "error_message": "Worker timeout",
            },
        )
        assert resp.status_code == 200

    async def test_extraction_not_found(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        resp = await client.post(
            "/internal/callback/extraction/99999",
            json={"status": "completed"},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestCampaignCallback:
    """Tests for POST /internal/callback/campaign/{campaign_id}."""

    async def test_campaign_active(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        oi, campaign, state = await _create_campaign_setup(
            db_session, test_company, distributor,
        )
        await db_session.commit()

        resp = await client.post(
            f"/internal/callback/campaign/{campaign.id}",
            json={
                "status": "active",
                "campaign_code": "CAM-001",
            },
        )
        assert resp.status_code == 200

    async def test_campaign_failed(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        oi, campaign, state = await _create_campaign_setup(
            db_session, test_company, distributor,
        )
        await db_session.commit()

        resp = await client.post(
            f"/internal/callback/campaign/{campaign.id}",
            json={
                "status": "failed",
                "error_message": "Login failed",
                "registration_step": "logging_in",
            },
        )
        assert resp.status_code == 200

    async def test_campaign_extended(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        oi, campaign, state = await _create_campaign_setup(
            db_session, test_company, distributor,
        )
        # Set campaign to active first (extension requires active campaign)
        campaign.status = CampaignStatus.ACTIVE.value
        campaign.campaign_code = "CAM-EXT"
        # Move pipeline to campaign_active for the extension callback
        state.current_stage = PipelineStage.CAMPAIGN_ACTIVE.value
        await db_session.flush()
        await db_session.commit()

        resp = await client.post(
            f"/internal/callback/campaign/{campaign.id}",
            json={
                "status": "extended",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "extended" in data["message"]

    async def test_campaign_not_found(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        resp = await client.post(
            "/internal/callback/campaign/99999",
            json={"status": "active"},
        )
        assert resp.status_code == 404

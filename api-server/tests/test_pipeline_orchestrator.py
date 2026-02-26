"""Tests for pipeline orchestrator E2E flow."""

from __future__ import annotations

import secrets
from datetime import date, time
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign, CampaignStatus
from app.models.company import Company
from app.models.extraction_job import ExtractionJob, ExtractionJobStatus
from app.models.network_preset import NetworkPreset
from app.models.order import (
    AssignmentStatus,
    Order,
    OrderItem,
    OrderStatus,
)
from app.models.pipeline_state import PipelineStage, PipelineState
from app.models.place import Place
from app.models.product import Product
from app.models.superap_account import SuperapAccount
from app.models.user import User
from app.services import pipeline_orchestrator
from tests.conftest import create_test_company, create_test_user


async def _create_product(db: AsyncSession) -> Product:
    product = Product(
        name="Traffic",
        code=f"t_{secrets.token_hex(3)}",
        base_price=10000,
        daily_deadline=time(18, 0),
    )
    db.add(product)
    await db.flush()
    return product


async def _create_order_with_items(
    db: AsyncSession,
    company: Company,
    user: User,
    product: Product,
    item_data: dict | None = None,
) -> Order:
    """Create a payment_confirmed order with one item."""
    order = Order(
        order_number=f"ORD-TEST-{secrets.token_hex(2).upper()}",
        user_id=user.id,
        company_id=company.id,
        status=OrderStatus.PAYMENT_CONFIRMED.value,
    )
    db.add(order)
    await db.flush()

    oi = OrderItem(
        order_id=order.id,
        product_id=product.id,
        quantity=1,
        unit_price=10000,
        subtotal=10000,
        item_data=item_data or {
            "place_url": "https://map.naver.com/p/entry/place/123",
            "campaign_type": "traffic",
            "daily_limit": 300,
            "total_limit": 5000,
            "duration_days": 30,
        },
    )
    db.add(oi)
    await db.flush()
    await db.refresh(order)
    return order


# ---------------------------------------------------------------------------
# start_pipeline_for_order
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestStartPipelineForOrder:

    @patch("app.services.pipeline_orchestrator.dispatch_extraction_job", new_callable=AsyncMock)
    async def test_creates_pipeline_state_and_extraction_job(
        self,
        mock_dispatch,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        mock_dispatch.return_value = {"job_id": 1, "status": "queued"}

        product = await _create_product(db_session)
        order = await _create_order_with_items(
            db_session, test_company, distributor, product,
        )
        await db_session.commit()

        await pipeline_orchestrator.start_pipeline_for_order(db_session, order)
        await db_session.commit()

        # Verify pipeline state created
        item = order.items[0]
        result = await db_session.execute(
            select(PipelineState).where(
                PipelineState.order_item_id == item.id
            )
        )
        state = result.scalar_one()
        assert state.current_stage == PipelineStage.EXTRACTION_QUEUED.value
        assert state.extraction_job_id is not None

        # Verify extraction job created
        job_result = await db_session.execute(
            select(ExtractionJob).where(
                ExtractionJob.order_item_id == item.id
            )
        )
        job = job_result.scalar_one()
        assert job.status == ExtractionJobStatus.QUEUED.value
        assert job.naver_url == "https://map.naver.com/p/entry/place/123"

        # Verify order status transitioned to processing
        await db_session.refresh(order)
        assert order.status == OrderStatus.PROCESSING.value

        # Verify dispatch was called
        mock_dispatch.assert_called_once()

    @patch("app.services.pipeline_orchestrator.dispatch_extraction_job", new_callable=AsyncMock)
    async def test_no_place_url_still_creates_state(
        self,
        mock_dispatch,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Items without place_url should still get a pipeline state."""
        product = await _create_product(db_session)
        order = await _create_order_with_items(
            db_session, test_company, distributor, product,
            item_data={"campaign_type": "traffic"},  # no place_url
        )
        await db_session.commit()

        await pipeline_orchestrator.start_pipeline_for_order(db_session, order)
        await db_session.commit()

        item = order.items[0]
        result = await db_session.execute(
            select(PipelineState).where(
                PipelineState.order_item_id == item.id
            )
        )
        state = result.scalar_one()
        assert state.current_stage == PipelineStage.EXTRACTION_QUEUED.value
        assert state.error_message == "No place_url in item_data"

        # Dispatch should NOT be called without place_url
        mock_dispatch.assert_not_called()

    @patch("app.services.pipeline_orchestrator.dispatch_extraction_job", new_callable=AsyncMock)
    async def test_dispatch_failure_preserves_db_state(
        self,
        mock_dispatch,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Worker dispatch failure should not prevent DB state creation."""
        from app.services.worker_clients import WorkerDispatchError
        mock_dispatch.side_effect = WorkerDispatchError("keyword", "Connection refused")

        product = await _create_product(db_session)
        order = await _create_order_with_items(
            db_session, test_company, distributor, product,
        )
        await db_session.commit()

        # Should not raise
        await pipeline_orchestrator.start_pipeline_for_order(db_session, order)
        await db_session.commit()

        # DB state should still be created
        item = order.items[0]
        result = await db_session.execute(
            select(PipelineState).where(
                PipelineState.order_item_id == item.id
            )
        )
        state = result.scalar_one()
        assert state.current_stage == PipelineStage.EXTRACTION_QUEUED.value

    @patch("app.services.pipeline_orchestrator.dispatch_extraction_job", new_callable=AsyncMock)
    async def test_empty_order_items(
        self,
        mock_dispatch,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Order with no items should be skipped gracefully."""
        order = Order(
            order_number=f"ORD-EMPTY-{secrets.token_hex(2).upper()}",
            user_id=distributor.id,
            company_id=test_company.id,
            status=OrderStatus.PAYMENT_CONFIRMED.value,
        )
        db_session.add(order)
        await db_session.flush()
        await db_session.refresh(order)
        await db_session.commit()

        await pipeline_orchestrator.start_pipeline_for_order(db_session, order)
        mock_dispatch.assert_not_called()


# ---------------------------------------------------------------------------
# on_extraction_complete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestOnExtractionComplete:

    async def test_auto_assignment_triggered(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """After extraction completes, auto-assignment should run."""
        product = await _create_product(db_session)

        # Create place (id is Naver-assigned, not autoincrement)
        place = Place(
            id=1234567890,
            name="Test Place",
            naver_url="https://map.naver.com/p/entry/place/123",
        )
        db_session.add(place)
        await db_session.flush()

        # Create network preset + account
        preset = NetworkPreset(
            name="Net1",
            campaign_type="traffic",
            company_id=test_company.id,
            tier_order=1,
            is_active=True,
        )
        db_session.add(preset)
        await db_session.flush()

        account = SuperapAccount(
            user_id_superap="test_user",
            password_encrypted="encrypted_dummy",
            network_preset_id=preset.id,
            is_active=True,
            assignment_order=1,
        )
        db_session.add(account)
        await db_session.flush()

        # Create order + item + job + pipeline
        order = Order(
            order_number=f"ORD-EXT-{secrets.token_hex(2).upper()}",
            user_id=distributor.id,
            company_id=test_company.id,
            status=OrderStatus.PROCESSING.value,
        )
        db_session.add(order)
        await db_session.flush()

        oi = OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=1,
            unit_price=10000,
            subtotal=10000,
            item_data={
                "place_url": "https://map.naver.com/p/entry/place/123",
                "campaign_type": "traffic",
                "total_limit": 5000,
            },
        )
        db_session.add(oi)
        await db_session.flush()

        job = ExtractionJob(
            order_item_id=oi.id,
            naver_url="https://map.naver.com/p/entry/place/123",
            status=ExtractionJobStatus.COMPLETED.value,
            result_count=50,
            place_id=place.id,
            place_name="Test Place",
        )
        db_session.add(job)
        await db_session.flush()

        state = PipelineState(
            order_item_id=oi.id,
            current_stage=PipelineStage.EXTRACTION_DONE.value,
            extraction_job_id=job.id,
        )
        db_session.add(state)
        await db_session.flush()
        await db_session.commit()

        await pipeline_orchestrator.on_extraction_complete(
            db_session, oi.id, job,
        )
        await db_session.commit()

        # Verify assignment happened
        await db_session.refresh(oi)
        assert oi.assignment_status == AssignmentStatus.AUTO_ASSIGNED.value
        assert oi.assigned_account_id == account.id
        assert oi.place_id == place.id

        # Verify pipeline transitioned to account_assigned
        await db_session.refresh(state)
        assert state.current_stage == PipelineStage.ACCOUNT_ASSIGNED.value

    async def test_no_account_available(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """If no account available, pipeline stays at extraction_done."""
        product = await _create_product(db_session)

        place = Place(
            id=456789,
            name="No Account Place",
            naver_url="https://map.naver.com/p/entry/place/456",
        )
        db_session.add(place)
        await db_session.flush()

        order = Order(
            order_number=f"ORD-NA-{secrets.token_hex(2).upper()}",
            user_id=distributor.id,
            company_id=test_company.id,
            status=OrderStatus.PROCESSING.value,
        )
        db_session.add(order)
        await db_session.flush()

        oi = OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=1,
            unit_price=10000,
            subtotal=10000,
            item_data={
                "place_url": "https://map.naver.com/p/entry/place/456",
                "campaign_type": "traffic",
            },
        )
        db_session.add(oi)
        await db_session.flush()

        job = ExtractionJob(
            order_item_id=oi.id,
            naver_url="https://map.naver.com/p/entry/place/456",
            status=ExtractionJobStatus.COMPLETED.value,
            place_id=place.id,
        )
        db_session.add(job)
        await db_session.flush()

        state = PipelineState(
            order_item_id=oi.id,
            current_stage=PipelineStage.EXTRACTION_DONE.value,
        )
        db_session.add(state)
        await db_session.flush()
        await db_session.commit()

        await pipeline_orchestrator.on_extraction_complete(
            db_session, oi.id, job,
        )
        await db_session.commit()

        # Pipeline should stay at extraction_done (no account to assign)
        await db_session.refresh(state)
        assert state.current_stage == PipelineStage.EXTRACTION_DONE.value
        assert state.error_message is not None


# ---------------------------------------------------------------------------
# on_assignment_confirmed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestOnAssignmentConfirmed:

    @patch("app.services.pipeline_orchestrator.dispatch_campaign_registration", new_callable=AsyncMock)
    async def test_creates_campaign_and_dispatches(
        self,
        mock_dispatch,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        mock_dispatch.return_value = {"campaign_id": 1, "status": "queued"}

        product = await _create_product(db_session)

        place = Place(
            id=789012,
            name="Campaign Place",
            naver_url="https://map.naver.com/p/entry/place/789",
        )
        db_session.add(place)
        await db_session.flush()

        order = Order(
            order_number=f"ORD-AC-{secrets.token_hex(2).upper()}",
            user_id=distributor.id,
            company_id=test_company.id,
            status=OrderStatus.PROCESSING.value,
        )
        db_session.add(order)
        await db_session.flush()

        oi = OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=1,
            unit_price=10000,
            subtotal=10000,
            place_id=place.id,
            assigned_account_id=1,
            assignment_status=AssignmentStatus.CONFIRMED.value,
            item_data={
                "place_url": "https://map.naver.com/p/entry/place/789",
                "campaign_type": "traffic",
                "daily_limit": 300,
                "total_limit": 5000,
                "duration_days": 30,
            },
        )
        db_session.add(oi)
        await db_session.flush()

        job = ExtractionJob(
            order_item_id=oi.id,
            naver_url="https://map.naver.com/p/entry/place/789",
            status=ExtractionJobStatus.COMPLETED.value,
            place_name="Campaign Place",
            results=[
                {"keyword": "맛집", "rank": 3},
                {"keyword": "카페", "rank": 5},
                {"keyword": "레스토랑", "rank": 8},
            ],
        )
        db_session.add(job)
        await db_session.flush()

        state = PipelineState(
            order_item_id=oi.id,
            current_stage=PipelineStage.ACCOUNT_ASSIGNED.value,
            extraction_job_id=job.id,
        )
        db_session.add(state)
        await db_session.flush()
        await db_session.commit()

        await pipeline_orchestrator.on_assignment_confirmed(db_session, oi.id)
        await db_session.commit()

        # Verify campaign was created
        camp_result = await db_session.execute(
            select(Campaign).where(Campaign.order_item_id == oi.id)
        )
        campaign = camp_result.scalar_one()
        assert campaign.status == CampaignStatus.PENDING.value
        assert campaign.place_name == "Campaign Place"
        assert campaign.campaign_type == "traffic"
        assert campaign.daily_limit == 300
        assert campaign.extraction_job_id == job.id

        # Verify pipeline transitioned
        await db_session.refresh(state)
        assert state.current_stage == PipelineStage.CAMPAIGN_REGISTERING.value
        assert state.campaign_id == campaign.id

        # Verify dispatch was called
        mock_dispatch.assert_called_once()
        call_args = mock_dispatch.call_args
        assert call_args.kwargs.get("campaign_id") == campaign.id or call_args[1].get("campaign_id") == campaign.id

    @patch("app.services.pipeline_orchestrator.dispatch_campaign_registration", new_callable=AsyncMock)
    async def test_keywords_added_to_pool(
        self,
        mock_dispatch,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Keywords from extraction results should be added to campaign pool."""
        mock_dispatch.return_value = {"campaign_id": 1, "status": "queued"}

        product = await _create_product(db_session)

        place = Place(
            id=111222,
            name="KW Place",
            naver_url="https://map.naver.com/p/entry/place/kw1",
        )
        db_session.add(place)
        await db_session.flush()

        order = Order(
            order_number=f"ORD-KW-{secrets.token_hex(2).upper()}",
            user_id=distributor.id,
            company_id=test_company.id,
            status=OrderStatus.PROCESSING.value,
        )
        db_session.add(order)
        await db_session.flush()

        oi = OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=1,
            unit_price=10000,
            subtotal=10000,
            place_id=place.id,
            assigned_account_id=1,
            assignment_status=AssignmentStatus.CONFIRMED.value,
            item_data={
                "place_url": "https://map.naver.com/p/entry/place/kw1",
                "campaign_type": "traffic",
                "daily_limit": 300,
            },
        )
        db_session.add(oi)
        await db_session.flush()

        job = ExtractionJob(
            order_item_id=oi.id,
            naver_url="https://map.naver.com/p/entry/place/kw1",
            status=ExtractionJobStatus.COMPLETED.value,
            place_name="KW Place",
            results=["키워드1", "키워드2", "키워드3"],
        )
        db_session.add(job)
        await db_session.flush()

        state = PipelineState(
            order_item_id=oi.id,
            current_stage=PipelineStage.ACCOUNT_ASSIGNED.value,
            extraction_job_id=job.id,
        )
        db_session.add(state)
        await db_session.flush()
        await db_session.commit()

        await pipeline_orchestrator.on_assignment_confirmed(db_session, oi.id)
        await db_session.commit()

        # Verify keywords were added
        from app.models.campaign_keyword_pool import CampaignKeywordPool
        camp_result = await db_session.execute(
            select(Campaign).where(Campaign.order_item_id == oi.id)
        )
        campaign = camp_result.scalar_one()

        kw_result = await db_session.execute(
            select(CampaignKeywordPool).where(
                CampaignKeywordPool.campaign_id == campaign.id
            )
        )
        keywords = list(kw_result.scalars().all())
        assert len(keywords) == 3
        kw_texts = {kw.keyword for kw in keywords}
        assert kw_texts == {"키워드1", "키워드2", "키워드3"}


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestHelpers:

    async def test_extract_keywords_from_dict_results(self):
        """Keywords from dict-style results."""
        results = [
            {"keyword": "맛집", "rank": 3},
            {"keyword": "카페", "rank": 5},
        ]
        keywords = pipeline_orchestrator._extract_keywords_from_results(results)
        assert keywords == ["맛집", "카페"]

    async def test_extract_keywords_from_string_results(self):
        """Keywords from string-style results."""
        results = ["맛집", "카페", "레스토랑"]
        keywords = pipeline_orchestrator._extract_keywords_from_results(results)
        assert keywords == ["맛집", "카페", "레스토랑"]

    async def test_extract_keywords_empty(self):
        """Empty/None results return empty list."""
        assert pipeline_orchestrator._extract_keywords_from_results(None) == []
        assert pipeline_orchestrator._extract_keywords_from_results([]) == []

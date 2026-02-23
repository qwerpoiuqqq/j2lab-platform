"""Tests for pipeline endpoints and state machine."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.order import Order, OrderItem, OrderStatus
from app.models.pipeline_state import PipelineStage, PipelineState
from app.models.pipeline_log import PipelineLog
from app.models.place import Place
from app.models.product import Product
from app.models.user import User, UserRole
from app.services import pipeline_service
from tests.conftest import (
    create_test_company,
    create_test_user,
    get_auth_header,
)


async def _setup_order_item(db, company, user):
    """Helper: create a product, order, and order item."""
    import secrets as _sec
    from datetime import time
    product = Product(name="Traffic", code=f"traffic_{_sec.token_hex(3)}", base_price=10000, daily_deadline=time(18, 0))
    db.add(product)
    await db.flush()

    import secrets
    order = Order(
        order_number=f"ORD-TEST-{secrets.token_hex(2).upper()}",
        user_id=user.id,
        company_id=company.id,
        status=OrderStatus.DRAFT.value,
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
    await db.refresh(oi)
    return oi


@pytest.mark.asyncio
class TestPipelineStateMachine:
    """Test pipeline state transitions."""

    async def test_create_pipeline_state(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        oi = await _setup_order_item(db_session, test_company, distributor)
        state = await pipeline_service.create_pipeline_state(
            db_session, order_item_id=oi.id
        )
        assert state.current_stage == PipelineStage.DRAFT.value
        assert state.order_item_id == oi.id

    async def test_valid_transition(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        oi = await _setup_order_item(db_session, test_company, distributor)
        state = await pipeline_service.create_pipeline_state(
            db_session, order_item_id=oi.id
        )
        updated = await pipeline_service.transition_stage(
            db_session, state=state, to_stage="submitted",
            trigger_type="user_action", message="Distributor submitted",
        )
        assert updated.current_stage == "submitted"
        assert updated.previous_stage == "draft"

    async def test_invalid_transition(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        oi = await _setup_order_item(db_session, test_company, distributor)
        state = await pipeline_service.create_pipeline_state(
            db_session, order_item_id=oi.id
        )
        # draft -> campaign_active is not valid
        with pytest.raises(ValueError, match="Invalid pipeline transition"):
            await pipeline_service.transition_stage(
                db_session, state=state, to_stage="campaign_active",
            )

    async def test_full_pipeline_flow(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Test a complete pipeline from draft to campaign_active."""
        oi = await _setup_order_item(db_session, test_company, distributor)
        state = await pipeline_service.create_pipeline_state(
            db_session, order_item_id=oi.id
        )

        stages = [
            ("submitted", "user_action"),
            ("payment_confirmed", "user_action"),
            ("extraction_queued", "user_action"),
            ("extraction_running", "auto_extraction_complete"),
            ("extraction_done", "auto_extraction_complete"),
            ("account_assigned", "user_action"),
            ("assignment_confirmed", "user_action"),
            ("campaign_registering", "user_action"),
            ("campaign_active", "auto_registration_complete"),
        ]

        for to_stage, trigger in stages:
            state = await pipeline_service.transition_stage(
                db_session, state=state, to_stage=to_stage,
                trigger_type=trigger,
            )

        assert state.current_stage == "campaign_active"

    async def test_pipeline_logs_created(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        oi = await _setup_order_item(db_session, test_company, distributor)
        state = await pipeline_service.create_pipeline_state(
            db_session, order_item_id=oi.id
        )
        await pipeline_service.transition_stage(
            db_session, state=state, to_stage="submitted",
            trigger_type="user_action",
        )

        logs, total = await pipeline_service.get_pipeline_logs(
            db_session, state.id
        )
        # Initial creation + 1 transition
        assert total == 2

    async def test_failed_state_can_retry(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        oi = await _setup_order_item(db_session, test_company, distributor)
        state = await pipeline_service.create_pipeline_state(
            db_session, order_item_id=oi.id
        )

        # Go to extraction_running then fail
        await pipeline_service.transition_stage(
            db_session, state=state, to_stage="submitted",
        )
        await pipeline_service.transition_stage(
            db_session, state=state, to_stage="payment_confirmed",
        )
        await pipeline_service.transition_stage(
            db_session, state=state, to_stage="extraction_queued",
        )
        await pipeline_service.transition_stage(
            db_session, state=state, to_stage="extraction_running",
        )
        await pipeline_service.transition_stage(
            db_session, state=state, to_stage="failed",
            error_message="Worker timeout",
        )

        assert state.current_stage == "failed"

        # Retry: failed -> extraction_queued
        await pipeline_service.transition_stage(
            db_session, state=state, to_stage="extraction_queued",
            trigger_type="admin_override", message="Retry extraction",
        )
        assert state.current_stage == "extraction_queued"


@pytest.mark.asyncio
class TestPipelineAPI:
    """Tests for pipeline API endpoints."""

    async def test_get_pipeline_state(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        oi = await _setup_order_item(db_session, test_company, distributor)
        await pipeline_service.create_pipeline_state(
            db_session, order_item_id=oi.id
        )
        await db_session.commit()

        headers = get_auth_header(distributor)
        resp = await client.get(
            f"/api/v1/pipeline/{oi.id}", headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["current_stage"] == "draft"

    async def test_get_pipeline_state_not_found(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        await db_session.commit()
        headers = get_auth_header(distributor)
        resp = await client.get("/api/v1/pipeline/99999", headers=headers)
        assert resp.status_code == 404

    async def test_get_pipeline_logs(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        oi = await _setup_order_item(db_session, test_company, distributor)
        state = await pipeline_service.create_pipeline_state(
            db_session, order_item_id=oi.id
        )
        await pipeline_service.transition_stage(
            db_session, state=state, to_stage="submitted",
        )
        await db_session.commit()

        headers = get_auth_header(distributor)
        resp = await client.get(
            f"/api/v1/pipeline/{oi.id}/logs", headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    async def test_pipeline_overview(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        oi1 = await _setup_order_item(db_session, test_company, distributor)
        oi2 = await _setup_order_item(db_session, test_company, distributor)
        await pipeline_service.create_pipeline_state(
            db_session, order_item_id=oi1.id
        )
        state2 = await pipeline_service.create_pipeline_state(
            db_session, order_item_id=oi2.id
        )
        await pipeline_service.transition_stage(
            db_session, state=state2, to_stage="submitted",
        )
        await db_session.commit()

        headers = get_auth_header(distributor)
        resp = await client.get("/api/v1/pipeline/overview", headers=headers)
        assert resp.status_code == 200
        stages = resp.json()["stages"]
        assert len(stages) == 2  # draft and submitted

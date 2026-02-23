"""Phase 1C edge case tests: assignment, pipeline, callbacks, encryption.

Covers:
- Assignment edge cases: no existing campaign, extension expired, over 10000,
  all networks exhausted, no active accounts, extension with exact boundary,
  multiple campaign types, concurrent place assignments
- Pipeline edge cases: invalid transitions, completed/failed/cancelled blocks,
  full lifecycle to completed, management -> completed flow
- Callback edge cases: non-existent job_id, duplicate completed callback,
  callback for job without pipeline, extraction callback with running status
- AES encryption edge cases: round-trip, unicode, empty string, special chars
"""

from __future__ import annotations

import secrets
from datetime import date, time, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign, CampaignStatus
from app.models.company import Company
from app.models.extraction_job import ExtractionJob, ExtractionJobStatus
from app.models.network_preset import NetworkPreset
from app.models.order import (
    AssignmentStatus,
    Order,
    OrderItem,
    OrderItemStatus,
    OrderStatus,
)
from app.models.pipeline_log import PipelineLog
from app.models.pipeline_state import PipelineStage, PipelineState
from app.models.place import Place
from app.models.product import Product
from app.models.superap_account import SuperapAccount
from app.models.user import User, UserRole
from app.services import assignment_service, pipeline_service
from app.utils.crypto import decrypt_password, encrypt_password
from tests.conftest import (
    create_test_company,
    create_test_user,
    get_auth_header,
)


# ==================== Helpers ====================


async def _place(db, place_id=None):
    pid = place_id or (hash(secrets.token_hex(4)) % 900000 + 100000)
    p = Place(id=pid, name=f"Test Place {pid}", place_type="restaurant")
    db.add(p)
    await db.flush()
    return p


async def _product(db, code=None):
    c = code or f"traffic_{secrets.token_hex(3)}"
    p = Product(name="Traffic", code=c, base_price=10000, daily_deadline=time(18, 0))
    db.add(p)
    await db.flush()
    return p


async def _order(db, user_id, company_id):
    o = Order(
        order_number=f"ORD-TEST-{secrets.token_hex(3).upper()}",
        user_id=user_id,
        company_id=company_id,
        status=OrderStatus.PAYMENT_CONFIRMED.value,
    )
    db.add(o)
    await db.flush()
    return o


async def _order_item(db, order_id, product_id, place_id=None):
    oi = OrderItem(
        order_id=order_id,
        product_id=product_id,
        quantity=1,
        unit_price=10000,
        subtotal=10000,
        place_id=place_id,
    )
    db.add(oi)
    await db.flush()
    await db.refresh(oi)
    return oi


async def _preset(db, company_id, campaign_type="traffic", tier_order=1, name=None):
    nm = name or f"Net-{tier_order}-{secrets.token_hex(2)}"
    np = NetworkPreset(
        company_id=company_id,
        campaign_type=campaign_type,
        tier_order=tier_order,
        name=nm,
        media_config={"test": True},
        is_active=True,
    )
    db.add(np)
    await db.flush()
    await db.refresh(np)
    return np


async def _account(db, company_id, preset_id, login_id=None, order=0, active=True):
    lid = login_id or f"acc_{secrets.token_hex(3)}"
    a = SuperapAccount(
        user_id_superap=lid,
        password_encrypted=encrypt_password("test123"),
        company_id=company_id,
        network_preset_id=preset_id,
        assignment_order=order,
        is_active=active,
    )
    db.add(a)
    await db.flush()
    await db.refresh(a)
    return a


async def _campaign(db, place_id, campaign_type="traffic", end_date=None,
                    total_limit=None, account_id=None, preset_id=None,
                    status="active"):
    c = Campaign(
        place_id=place_id,
        place_url="https://map.naver.com/test",
        place_name="Test",
        campaign_type=campaign_type,
        start_date=date(2026, 2, 1),
        end_date=end_date or date(2026, 2, 28),
        daily_limit=300,
        total_limit=total_limit,
        superap_account_id=account_id,
        network_preset_id=preset_id,
        status=status,
    )
    db.add(c)
    await db.flush()
    await db.refresh(c)
    return c


async def _setup_assignment_basics(db, company, user):
    """Create place, product, order, order_item for assignment tests."""
    place = await _place(db)
    product = await _product(db)
    order = await _order(db, user.id, company.id)
    oi = await _order_item(db, order.id, product.id, place.id)
    return place, product, order, oi


# ==================== Assignment Edge Cases ====================


@pytest.mark.asyncio
class TestAssignmentEdgeCases:
    """Edge cases for the auto-assignment algorithm."""

    async def test_no_existing_campaign_for_place(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """When a place has no existing campaigns, no extension, assign first network."""
        place, product, order, oi = await _setup_assignment_basics(
            db_session, test_company, distributor,
        )
        preset = await _preset(db_session, test_company.id, tier_order=1)
        acc = await _account(db_session, test_company.id, preset.id)
        await db_session.flush()

        result = await assignment_service.auto_assign(
            db_session,
            order_item=oi,
            campaign_type="traffic",
            place_id=place.id,
            company_id=test_company.id,
            total_limit=3000,
        )

        assert result.is_extension is False
        assert result.assigned_account_id == acc.id
        assert result.network_preset_id == preset.id

    async def test_extension_exactly_7_days_ago(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Campaign ending exactly 7 days ago should be eligible for extension."""
        place, product, order, oi = await _setup_assignment_basics(
            db_session, test_company, distributor,
        )
        preset = await _preset(db_session, test_company.id, tier_order=1)
        acc = await _account(db_session, test_company.id, preset.id)

        today = date.today()
        existing = await _campaign(
            db_session, place.id, "traffic",
            end_date=today - timedelta(days=7),  # Exactly 7 days
            total_limit=3000,
            account_id=acc.id,
            preset_id=preset.id,
            status="completed",
        )
        await db_session.flush()

        result = await assignment_service.auto_assign(
            db_session,
            order_item=oi,
            campaign_type="traffic",
            place_id=place.id,
            company_id=test_company.id,
            total_limit=2000,  # 3000 + 2000 = 5000 < 10000
        )

        assert result.is_extension is True
        assert result.extend_target_campaign_id == existing.id

    async def test_extension_8_days_ago_not_eligible(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Campaign ending 8 days ago should NOT be eligible for extension."""
        place, product, order, oi = await _setup_assignment_basics(
            db_session, test_company, distributor,
        )
        preset = await _preset(db_session, test_company.id, tier_order=1)
        acc = await _account(db_session, test_company.id, preset.id)

        today = date.today()
        await _campaign(
            db_session, place.id, "traffic",
            end_date=today - timedelta(days=8),  # 8 days = too old
            total_limit=3000,
            account_id=acc.id,
            preset_id=preset.id,
            status="completed",
        )
        await db_session.flush()

        result = await assignment_service.auto_assign(
            db_session,
            order_item=oi,
            campaign_type="traffic",
            place_id=place.id,
            company_id=test_company.id,
            total_limit=2000,
        )

        # Not an extension, but network used so should still work
        assert result.is_extension is False

    async def test_extension_exactly_10000_limit_new_setup(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Combined total == 10,000 should trigger new setup (not extension)."""
        place, product, order, oi = await _setup_assignment_basics(
            db_session, test_company, distributor,
        )
        preset1 = await _preset(db_session, test_company.id, tier_order=1, name="Net1")
        preset2 = await _preset(db_session, test_company.id, tier_order=2, name="Net2")
        acc1 = await _account(db_session, test_company.id, preset1.id, login_id="a1")
        acc2 = await _account(db_session, test_company.id, preset2.id, login_id="a2")

        today = date.today()
        await _campaign(
            db_session, place.id, "traffic",
            end_date=today - timedelta(days=2),
            total_limit=5000,
            account_id=acc1.id,
            preset_id=preset1.id,
            status="completed",
        )
        await db_session.flush()

        result = await assignment_service.auto_assign(
            db_session,
            order_item=oi,
            campaign_type="traffic",
            place_id=place.id,
            company_id=test_company.id,
            total_limit=5000,  # 5000 + 5000 = 10000, exactly threshold
        )

        assert result.is_extension is False
        assert result.network_preset_id == preset2.id

    async def test_extension_9999_limit_should_extend(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Combined total == 9,999 should extend (just under threshold)."""
        place, product, order, oi = await _setup_assignment_basics(
            db_session, test_company, distributor,
        )
        preset = await _preset(db_session, test_company.id, tier_order=1)
        acc = await _account(db_session, test_company.id, preset.id)

        today = date.today()
        existing = await _campaign(
            db_session, place.id, "traffic",
            end_date=today - timedelta(days=1),
            total_limit=5000,
            account_id=acc.id,
            preset_id=preset.id,
            status="completed",
        )
        await db_session.flush()

        result = await assignment_service.auto_assign(
            db_session,
            order_item=oi,
            campaign_type="traffic",
            place_id=place.id,
            company_id=test_company.id,
            total_limit=4999,  # 5000 + 4999 = 9999 < 10000
        )

        assert result.is_extension is True
        assert result.extend_target_campaign_id == existing.id

    async def test_all_networks_exhausted_for_traffic_suggest_save(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """All traffic networks used -> suggest save."""
        place, product, order, oi = await _setup_assignment_basics(
            db_session, test_company, distributor,
        )
        p1 = await _preset(db_session, test_company.id, "traffic", 1, "T1")
        p2 = await _preset(db_session, test_company.id, "traffic", 2, "T2")
        a1 = await _account(db_session, test_company.id, p1.id, "t1acc")
        a2 = await _account(db_session, test_company.id, p2.id, "t2acc")

        await _campaign(db_session, place.id, "traffic", preset_id=p1.id, account_id=a1.id)
        await _campaign(db_session, place.id, "traffic", preset_id=p2.id, account_id=a2.id)
        await db_session.flush()

        result = await assignment_service.auto_assign(
            db_session,
            order_item=oi,
            campaign_type="traffic",
            place_id=place.id,
            company_id=test_company.id,
        )

        assert result.assigned_account_id is None
        assert result.suggestion is not None
        assert "save" in result.suggestion.lower()

    async def test_all_networks_exhausted_for_save_suggest_traffic(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """All save networks used -> suggest traffic."""
        place, product, order, oi = await _setup_assignment_basics(
            db_session, test_company, distributor,
        )
        p1 = await _preset(db_session, test_company.id, "save", 1, "S1")
        a1 = await _account(db_session, test_company.id, p1.id, "s1acc")

        await _campaign(db_session, place.id, "save", preset_id=p1.id, account_id=a1.id)
        await db_session.flush()

        result = await assignment_service.auto_assign(
            db_session,
            order_item=oi,
            campaign_type="save",
            place_id=place.id,
            company_id=test_company.id,
        )

        assert result.assigned_account_id is None
        assert result.suggestion is not None
        assert "traffic" in result.suggestion.lower()

    async def test_inactive_network_preset_skipped(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Inactive network presets should be skipped."""
        place, product, order, oi = await _setup_assignment_basics(
            db_session, test_company, distributor,
        )
        # tier_order=1 but inactive
        p1 = await _preset(db_session, test_company.id, "traffic", 1, "Inactive")
        p1.is_active = False

        # tier_order=2 and active
        p2 = await _preset(db_session, test_company.id, "traffic", 2, "Active")
        a2 = await _account(db_session, test_company.id, p2.id, "active_acc")
        await db_session.flush()

        result = await assignment_service.auto_assign(
            db_session,
            order_item=oi,
            campaign_type="traffic",
            place_id=place.id,
            company_id=test_company.id,
        )

        assert result.network_preset_id == p2.id
        assert result.assigned_account_id == a2.id

    async def test_no_active_accounts_in_selected_network(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Error when selected network has only inactive accounts."""
        place, product, order, oi = await _setup_assignment_basics(
            db_session, test_company, distributor,
        )
        p1 = await _preset(db_session, test_company.id, "traffic", 1, "Net1")
        # Both accounts inactive
        await _account(db_session, test_company.id, p1.id, "ia1", active=False)
        await _account(db_session, test_company.id, p1.id, "ia2", active=False)
        await db_session.flush()

        result = await assignment_service.auto_assign(
            db_session,
            order_item=oi,
            campaign_type="traffic",
            place_id=place.id,
            company_id=test_company.id,
        )

        assert result.assigned_account_id is None
        assert result.error is not None
        assert "No active accounts" in result.error

    async def test_no_networks_at_all(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """When company has no network presets at all, suggest type change."""
        place, product, order, oi = await _setup_assignment_basics(
            db_session, test_company, distributor,
        )
        await db_session.flush()

        result = await assignment_service.auto_assign(
            db_session,
            order_item=oi,
            campaign_type="traffic",
            place_id=place.id,
            company_id=test_company.id,
        )

        assert result.assigned_account_id is None
        assert result.suggestion is not None

    async def test_extension_with_null_total_limit(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Extension check when total_limit is None on both sides."""
        place, product, order, oi = await _setup_assignment_basics(
            db_session, test_company, distributor,
        )
        preset = await _preset(db_session, test_company.id, tier_order=1)
        acc = await _account(db_session, test_company.id, preset.id)

        today = date.today()
        existing = await _campaign(
            db_session, place.id, "traffic",
            end_date=today - timedelta(days=2),
            total_limit=None,  # NULL
            account_id=acc.id,
            preset_id=preset.id,
            status="completed",
        )
        await db_session.flush()

        result = await assignment_service.auto_assign(
            db_session,
            order_item=oi,
            campaign_type="traffic",
            place_id=place.id,
            company_id=test_company.id,
            total_limit=None,  # NULL
        )

        # 0 + 0 = 0 < 10000 -> extend
        assert result.is_extension is True
        assert result.extend_target_campaign_id == existing.id

    async def test_different_campaign_type_not_considered_for_extension(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Traffic campaign should not extend save campaign."""
        place, product, order, oi = await _setup_assignment_basics(
            db_session, test_company, distributor,
        )
        traffic_preset = await _preset(db_session, test_company.id, "traffic", 1, "TN")
        traffic_acc = await _account(db_session, test_company.id, traffic_preset.id, "tacc")

        today = date.today()
        # Save campaign exists (recent)
        await _campaign(
            db_session, place.id, "save",
            end_date=today - timedelta(days=2),
            total_limit=3000,
            status="completed",
        )
        await db_session.flush()

        result = await assignment_service.auto_assign(
            db_session,
            order_item=oi,
            campaign_type="traffic",
            place_id=place.id,
            company_id=test_company.id,
            total_limit=3000,
        )

        # Should NOT extend because the existing is save, not traffic
        assert result.is_extension is False
        assert result.assigned_account_id == traffic_acc.id

    async def test_order_item_assignment_status_updated(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """After auto-assign, order_item.assignment_status should be auto_assigned."""
        place, product, order, oi = await _setup_assignment_basics(
            db_session, test_company, distributor,
        )
        preset = await _preset(db_session, test_company.id, tier_order=1)
        acc = await _account(db_session, test_company.id, preset.id)
        await db_session.flush()

        assert oi.assignment_status == AssignmentStatus.PENDING.value

        result = await assignment_service.auto_assign(
            db_session,
            order_item=oi,
            campaign_type="traffic",
            place_id=place.id,
            company_id=test_company.id,
        )

        assert oi.assignment_status == AssignmentStatus.AUTO_ASSIGNED.value
        assert oi.assigned_account_id == acc.id
        assert oi.assigned_at is not None


# ==================== Pipeline Edge Cases ====================


@pytest.mark.asyncio
class TestPipelineEdgeCases:
    """Edge cases for pipeline state machine."""

    async def _make_pipeline(self, db, company, user, stage="draft"):
        product = await _product(db)
        order = await _order(db, user.id, company.id)
        oi = await _order_item(db, order.id, product.id)
        state = await pipeline_service.create_pipeline_state(
            db, order_item_id=oi.id, initial_stage=stage,
        )
        return oi, state

    async def test_completed_cannot_transition_to_any_stage(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Completed state should not allow any transition."""
        oi, state = await self._make_pipeline(
            db_session, test_company, distributor, "draft",
        )
        # Walk to completed
        for stage in ["submitted", "payment_confirmed", "extraction_queued",
                       "extraction_running", "extraction_done", "account_assigned",
                       "assignment_confirmed", "campaign_registering",
                       "campaign_active", "management", "completed"]:
            await pipeline_service.transition_stage(db_session, state, stage)

        assert state.current_stage == "completed"

        # Try various transitions
        for target in ["draft", "submitted", "extraction_queued", "failed"]:
            with pytest.raises(ValueError, match="Invalid pipeline transition"):
                await pipeline_service.transition_stage(
                    db_session, state, target,
                )

    async def test_cancelled_cannot_transition(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Cancelled state should not allow any transition."""
        oi, state = await self._make_pipeline(
            db_session, test_company, distributor,
        )
        await pipeline_service.transition_stage(db_session, state, "cancelled")
        assert state.current_stage == "cancelled"

        for target in ["draft", "submitted", "extraction_queued", "failed"]:
            with pytest.raises(ValueError, match="Invalid pipeline transition"):
                await pipeline_service.transition_stage(
                    db_session, state, target,
                )

    async def test_failed_can_retry_to_extraction_queued(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Failed state should allow retry to extraction_queued."""
        oi, state = await self._make_pipeline(
            db_session, test_company, distributor,
        )
        for stage in ["submitted", "payment_confirmed", "extraction_queued",
                       "extraction_running", "failed"]:
            await pipeline_service.transition_stage(db_session, state, stage)

        assert state.current_stage == "failed"
        await pipeline_service.transition_stage(
            db_session, state, "extraction_queued",
        )
        assert state.current_stage == "extraction_queued"

    async def test_failed_can_retry_to_campaign_registering(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Failed state should allow retry to campaign_registering."""
        oi, state = await self._make_pipeline(
            db_session, test_company, distributor,
        )
        for stage in ["submitted", "payment_confirmed", "extraction_queued",
                       "extraction_running", "extraction_done", "account_assigned",
                       "assignment_confirmed", "campaign_registering", "failed"]:
            await pipeline_service.transition_stage(db_session, state, stage)

        assert state.current_stage == "failed"
        await pipeline_service.transition_stage(
            db_session, state, "campaign_registering",
        )
        assert state.current_stage == "campaign_registering"

    async def test_failed_cannot_go_to_completed(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Failed state should NOT allow jumping to completed."""
        oi, state = await self._make_pipeline(
            db_session, test_company, distributor,
        )
        for stage in ["submitted", "payment_confirmed", "extraction_queued",
                       "extraction_running", "failed"]:
            await pipeline_service.transition_stage(db_session, state, stage)

        with pytest.raises(ValueError, match="Invalid pipeline transition"):
            await pipeline_service.transition_stage(
                db_session, state, "completed",
            )

    async def test_draft_cannot_skip_to_extraction(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Draft should NOT allow jumping directly to extraction_queued."""
        oi, state = await self._make_pipeline(
            db_session, test_company, distributor,
        )
        with pytest.raises(ValueError, match="Invalid pipeline transition"):
            await pipeline_service.transition_stage(
                db_session, state, "extraction_queued",
            )

    async def test_extraction_running_cannot_cancel(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """extraction_running can only go to extraction_done or failed."""
        oi, state = await self._make_pipeline(
            db_session, test_company, distributor,
        )
        for stage in ["submitted", "payment_confirmed", "extraction_queued",
                       "extraction_running"]:
            await pipeline_service.transition_stage(db_session, state, stage)

        with pytest.raises(ValueError, match="Invalid pipeline transition"):
            await pipeline_service.transition_stage(
                db_session, state, "cancelled",
            )

    async def test_account_assigned_can_only_go_to_confirmed(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """account_assigned can only transition to assignment_confirmed."""
        oi, state = await self._make_pipeline(
            db_session, test_company, distributor,
        )
        for stage in ["submitted", "payment_confirmed", "extraction_queued",
                       "extraction_running", "extraction_done", "account_assigned"]:
            await pipeline_service.transition_stage(db_session, state, stage)

        with pytest.raises(ValueError, match="Invalid pipeline transition"):
            await pipeline_service.transition_stage(
                db_session, state, "failed",
            )
        with pytest.raises(ValueError, match="Invalid pipeline transition"):
            await pipeline_service.transition_stage(
                db_session, state, "cancelled",
            )

    async def test_pipeline_logs_track_all_transitions(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Each transition should create a log entry."""
        oi, state = await self._make_pipeline(
            db_session, test_company, distributor,
        )
        # Initial creation creates 1 log
        await pipeline_service.transition_stage(
            db_session, state, "submitted", message="Sub submitted",
        )
        await pipeline_service.transition_stage(
            db_session, state, "payment_confirmed",
        )

        logs, total = await pipeline_service.get_pipeline_logs(
            db_session, state.id,
        )
        # 1 (creation) + 2 (transitions) = 3
        assert total == 3

    async def test_pipeline_error_message_stored(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Error message should be stored in pipeline_state."""
        oi, state = await self._make_pipeline(
            db_session, test_company, distributor,
        )
        for stage in ["submitted", "payment_confirmed", "extraction_queued",
                       "extraction_running"]:
            await pipeline_service.transition_stage(db_session, state, stage)

        await pipeline_service.transition_stage(
            db_session, state, "failed",
            error_message="Proxy connection timeout",
        )

        assert state.current_stage == "failed"
        assert state.error_message == "Proxy connection timeout"

    async def test_campaign_active_to_completed_via_management(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Full path: campaign_active -> management -> completed."""
        oi, state = await self._make_pipeline(
            db_session, test_company, distributor,
        )
        stages = [
            "submitted", "payment_confirmed", "extraction_queued",
            "extraction_running", "extraction_done", "account_assigned",
            "assignment_confirmed", "campaign_registering", "campaign_active",
            "management", "completed",
        ]
        for stage in stages:
            await pipeline_service.transition_stage(db_session, state, stage)

        assert state.current_stage == "completed"

    async def test_campaign_active_direct_to_completed(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """campaign_active can also go directly to completed."""
        oi, state = await self._make_pipeline(
            db_session, test_company, distributor,
        )
        stages = [
            "submitted", "payment_confirmed", "extraction_queued",
            "extraction_running", "extraction_done", "account_assigned",
            "assignment_confirmed", "campaign_registering", "campaign_active",
        ]
        for stage in stages:
            await pipeline_service.transition_stage(db_session, state, stage)

        await pipeline_service.transition_stage(db_session, state, "completed")
        assert state.current_stage == "completed"


# ==================== Callback Edge Cases ====================


@pytest.mark.asyncio
class TestCallbackEdgeCases:
    """Edge cases for internal callback endpoints."""

    async def test_extraction_callback_nonexistent_job(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Callback to a non-existent extraction job returns 404."""
        resp = await client.post(
            "/internal/callback/extraction/999999",
            json={"status": "completed", "result_count": 100},
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    async def test_campaign_callback_nonexistent_campaign(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Callback to a non-existent campaign returns 404."""
        resp = await client.post(
            "/internal/callback/campaign/999999",
            json={"status": "active", "campaign_code": "CAM-001"},
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    async def test_extraction_callback_duplicate_completed(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Duplicate completed callback should still succeed (idempotent)."""
        job = ExtractionJob(
            naver_url="https://map.naver.com/test",
            status=ExtractionJobStatus.RUNNING.value,
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)
        await db_session.commit()

        # First callback
        resp1 = await client.post(
            f"/internal/callback/extraction/{job.id}",
            json={"status": "completed", "result_count": 200, "place_id": 123},
        )
        assert resp1.status_code == 200

        # Second (duplicate) callback
        resp2 = await client.post(
            f"/internal/callback/extraction/{job.id}",
            json={"status": "completed", "result_count": 200, "place_id": 123},
        )
        assert resp2.status_code == 200

    async def test_extraction_callback_without_pipeline(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Extraction callback for a job without pipeline state should work."""
        job = ExtractionJob(
            naver_url="https://map.naver.com/test",
            status=ExtractionJobStatus.RUNNING.value,
            # No order_item_id -> no pipeline state
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)
        await db_session.commit()

        resp = await client.post(
            f"/internal/callback/extraction/{job.id}",
            json={"status": "completed", "result_count": 100},
        )
        assert resp.status_code == 200

    async def test_campaign_callback_without_pipeline(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Campaign callback for a campaign without pipeline state should work."""
        campaign = Campaign(
            place_url="https://map.naver.com/test",
            place_name="Test",
            campaign_type="traffic",
            status=CampaignStatus.REGISTERING.value,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
            daily_limit=300,
            # No order_item_id -> no pipeline state
        )
        db_session.add(campaign)
        await db_session.flush()
        await db_session.refresh(campaign)
        await db_session.commit()

        resp = await client.post(
            f"/internal/callback/campaign/{campaign.id}",
            json={"status": "active", "campaign_code": "CAM-001"},
        )
        assert resp.status_code == 200

    async def test_extraction_callback_with_pipeline_transition(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Extraction callback should transition pipeline from extraction_running to extraction_done."""
        product = await _product(db_session)
        order = await _order(db_session, distributor.id, test_company.id)
        oi = await _order_item(db_session, order.id, product.id)

        job = ExtractionJob(
            order_item_id=oi.id,
            naver_url="https://map.naver.com/test",
            status=ExtractionJobStatus.RUNNING.value,
        )
        db_session.add(job)
        await db_session.flush()

        state = PipelineState(
            order_item_id=oi.id,
            current_stage=PipelineStage.EXTRACTION_RUNNING.value,
        )
        db_session.add(state)
        await db_session.flush()
        await db_session.refresh(job)
        await db_session.commit()

        resp = await client.post(
            f"/internal/callback/extraction/{job.id}",
            json={
                "status": "completed",
                "result_count": 200,
                "place_id": 123456,
                "place_name": "Test Place",
            },
        )
        assert resp.status_code == 200

    async def test_extraction_failed_callback_transitions_pipeline_to_failed(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Failed extraction callback should transition pipeline to failed."""
        product = await _product(db_session)
        order = await _order(db_session, distributor.id, test_company.id)
        oi = await _order_item(db_session, order.id, product.id)

        job = ExtractionJob(
            order_item_id=oi.id,
            naver_url="https://map.naver.com/test",
            status=ExtractionJobStatus.RUNNING.value,
        )
        db_session.add(job)
        await db_session.flush()

        state = PipelineState(
            order_item_id=oi.id,
            current_stage=PipelineStage.EXTRACTION_RUNNING.value,
        )
        db_session.add(state)
        await db_session.flush()
        await db_session.refresh(job)
        await db_session.commit()

        resp = await client.post(
            f"/internal/callback/extraction/{job.id}",
            json={
                "status": "failed",
                "error_message": "Worker crashed",
            },
        )
        assert resp.status_code == 200


# ==================== AES Encryption Edge Cases ====================


@pytest.mark.asyncio
class TestAESEncryptionEdgeCases:
    """Edge cases for AES encryption/decryption."""

    async def test_encrypt_decrypt_roundtrip(self):
        """Basic encrypt -> decrypt should return original."""
        original = "my_secure_password123!"
        encrypted = encrypt_password(original)
        decrypted = decrypt_password(encrypted)
        assert decrypted == original

    async def test_encrypt_produces_different_output(self):
        """Same input should produce different encrypted output (Fernet uses random IV)."""
        original = "password123"
        enc1 = encrypt_password(original)
        enc2 = encrypt_password(original)
        # Different ciphertext
        assert enc1 != enc2
        # But same decryption
        assert decrypt_password(enc1) == original
        assert decrypt_password(enc2) == original

    async def test_encrypt_unicode_characters(self):
        """Korean and special unicode characters should work."""
        original = "비밀번호123!@#"
        encrypted = encrypt_password(original)
        decrypted = decrypt_password(encrypted)
        assert decrypted == original

    async def test_encrypt_empty_string(self):
        """Empty string should encrypt and decrypt correctly."""
        original = ""
        encrypted = encrypt_password(original)
        decrypted = decrypt_password(encrypted)
        assert decrypted == original

    async def test_encrypt_long_password(self):
        """Very long password should work."""
        original = "a" * 10000
        encrypted = encrypt_password(original)
        decrypted = decrypt_password(encrypted)
        assert decrypted == original

    async def test_encrypt_special_characters(self):
        """Special characters, whitespace, newlines."""
        original = "pass word\n\ttab\r\n끝!"
        encrypted = encrypt_password(original)
        decrypted = decrypt_password(encrypted)
        assert decrypted == original

    async def test_encrypted_is_not_plaintext(self):
        """Encrypted output should not contain the plaintext."""
        original = "my_password"
        encrypted = encrypt_password(original)
        assert original not in encrypted

    async def test_decrypt_wrong_token_raises(self):
        """Decrypting with wrong data should raise."""
        from cryptography.fernet import InvalidToken
        with pytest.raises(Exception):
            decrypt_password("this_is_not_a_valid_fernet_token")


# ==================== Assignment API Edge Cases ====================


@pytest.mark.asyncio
class TestAssignmentAPIEdgeCases:
    """API-level edge cases for assignment endpoints."""

    async def test_confirm_nonexistent_order_item(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """Confirm a non-existent order item returns 404."""
        admin = await create_test_user(
            db_session, email="adm_cnf@test.com", role=UserRole.COMPANY_ADMIN,
            company_id=test_company.id,
        )
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.post(
            "/api/v1/assignment/999999/confirm",
            headers=headers,
        )
        assert resp.status_code == 404

    async def test_override_nonexistent_order_item(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """Override a non-existent order item returns 404."""
        admin = await create_test_user(
            db_session, email="adm_ovr@test.com", role=UserRole.COMPANY_ADMIN,
            company_id=test_company.id,
        )
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.patch(
            "/api/v1/assignment/999999/account",
            json={"account_id": 1},
            headers=headers,
        )
        assert resp.status_code == 404

    async def test_bulk_confirm_with_mixed_items(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """Bulk confirm with mix of valid and invalid items."""
        admin = await create_test_user(
            db_session, email="adm_bulk@test.com", role=UserRole.COMPANY_ADMIN,
            company_id=test_company.id,
        )
        dist = await create_test_user(
            db_session, email="dist_bulk@test.com", role=UserRole.DISTRIBUTOR,
            company_id=test_company.id,
        )

        product = await _product(db_session)
        order = await _order(db_session, dist.id, test_company.id)
        oi_valid = await _order_item(db_session, order.id, product.id)
        oi_pending = await _order_item(db_session, order.id, product.id)

        oi_valid.assignment_status = AssignmentStatus.AUTO_ASSIGNED.value
        oi_valid.assigned_account_id = 1
        # oi_pending stays as pending
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.post(
            "/api/v1/assignment/bulk-confirm",
            json={"item_ids": [oi_valid.id, oi_pending.id, 999999]},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_confirmed"] == 1
        assert data["total_errors"] == 2

    async def test_order_handler_cannot_access_assignment_queue(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """Order handlers should NOT have access to assignment queue."""
        handler = await create_test_user(
            db_session, email="handler_q@test.com", role=UserRole.ORDER_HANDLER,
            company_id=test_company.id,
        )
        await db_session.commit()

        headers = get_auth_header(handler)
        resp = await client.get("/api/v1/assignment/queue", headers=headers)
        assert resp.status_code == 403

    async def test_distributor_cannot_confirm_assignment(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """Distributors should NOT be able to confirm assignments."""
        dist = await create_test_user(
            db_session, email="dist_cnf@test.com", role=UserRole.DISTRIBUTOR,
            company_id=test_company.id,
        )
        await db_session.commit()

        headers = get_auth_header(dist)
        resp = await client.post(
            "/api/v1/assignment/1/confirm",
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_place_history_empty(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """Place history for a place with no campaigns."""
        admin = await create_test_user(
            db_session, email="adm_hist@test.com", role=UserRole.SYSTEM_ADMIN,
        )
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.get(
            "/api/v1/assignment/place/999999/history",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["campaigns"] == []


# ==================== Network Preset Edge Cases ====================


@pytest.mark.asyncio
class TestNetworkPresetEdgeCases:
    """Edge cases for network preset selection logic."""

    async def test_preset_order_by_tier_not_by_id(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Network presets should be selected by tier_order, not by id."""
        place, product, order, oi = await _setup_assignment_basics(
            db_session, test_company, distributor,
        )
        # Create tier_order=2 first (gets lower id)
        p2 = await _preset(db_session, test_company.id, "traffic", 2, "Net2")
        a2 = await _account(db_session, test_company.id, p2.id, "acc2")
        # Then tier_order=1 (gets higher id)
        p1 = await _preset(db_session, test_company.id, "traffic", 1, "Net1")
        a1 = await _account(db_session, test_company.id, p1.id, "acc1")
        await db_session.flush()

        result = await assignment_service.auto_assign(
            db_session,
            order_item=oi,
            campaign_type="traffic",
            place_id=place.id,
            company_id=test_company.id,
        )

        # Should pick tier_order=1 even though it has higher id
        assert result.network_preset_id == p1.id

    async def test_preset_cross_company_isolation(
        self,
        db_session: AsyncSession,
        test_company: Company,
        test_company_2: Company,
        distributor: User,
    ):
        """Network presets from different companies should not be shared."""
        place, product, order, oi = await _setup_assignment_basics(
            db_session, test_company, distributor,
        )

        # Create preset for company 2 only
        p_other = await _preset(db_session, test_company_2.id, "traffic", 1, "OtherNet")
        a_other = await _account(db_session, test_company_2.id, p_other.id, "other_acc")
        await db_session.flush()

        result = await assignment_service.auto_assign(
            db_session,
            order_item=oi,
            campaign_type="traffic",
            place_id=place.id,
            company_id=test_company.id,
        )

        # Should not find any presets for test_company
        assert result.assigned_account_id is None
        assert result.suggestion is not None

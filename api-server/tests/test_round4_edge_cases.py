"""Round 4 edge case tests: schema validation hardening + additional edge cases.

Covers new validation fixes:
- CampaignCreate: end_date >= start_date validation
- CampaignUpdate: status must be valid CampaignStatus value
- CampaignKeywordAddRequest: empty/whitespace keyword, keyword > 255 chars
- CampaignCallbackRequest: status pattern validation
- ExtractionJobCreate: min_rank <= max_rank cross-validation
- ExtractionCallbackRequest: status pattern validation
- Campaign update with arbitrary status string blocked
- Double payment confirmation idempotency
- Order creation with negative quantity
- Pipeline overview with no data
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
    OrderStatus,
    PaymentStatus,
)
from app.models.pipeline_state import PipelineStage, PipelineState
from app.models.place import Place
from app.models.product import Product
from app.models.superap_account import SuperapAccount
from app.models.user import User, UserRole
from app.services import balance_service
from app.utils.crypto import encrypt_password
from tests.conftest import (
    create_test_company,
    create_test_user,
    get_auth_header,
)


# ==================== Helpers ====================


async def _product(db, code=None, base_price=10000):
    c = code or f"product_{secrets.token_hex(3)}"
    p = Product(name="Test Product", code=c, base_price=base_price, daily_deadline=time(18, 0))
    db.add(p)
    await db.flush()
    return p


async def _place(db, place_id=None):
    pid = place_id or (hash(secrets.token_hex(4)) % 900000 + 100000)
    p = Place(id=pid, name=f"Test Place {pid}", place_type="restaurant")
    db.add(p)
    await db.flush()
    return p


async def _order(db, user_id, company_id, status="payment_confirmed"):
    o = Order(
        order_number=f"ORD-TEST-{secrets.token_hex(3).upper()}",
        user_id=user_id,
        company_id=company_id,
        status=status,
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


# ==================== CampaignCreate Date Validation ====================


@pytest.mark.asyncio
class TestCampaignCreateDateValidation:
    """Verify end_date >= start_date cross-field validation."""

    async def test_create_campaign_end_date_before_start_date(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """end_date before start_date should return 422."""
        admin = await create_test_user(
            db_session, email="admin_cd@test.com",
            role=UserRole.SYSTEM_ADMIN,
        )
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.post(
            "/api/v1/campaigns/",
            json={
                "place_url": "https://map.naver.com/test",
                "campaign_type": "traffic",
                "start_date": "2026-04-01",
                "end_date": "2026-03-01",  # Before start_date
                "daily_limit": 100,
            },
            headers=headers,
        )
        assert resp.status_code == 422
        assert "end_date" in resp.text.lower()

    async def test_create_campaign_same_start_end_date(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """Same start_date and end_date should succeed."""
        admin = await create_test_user(
            db_session, email="admin_cd2@test.com",
            role=UserRole.SYSTEM_ADMIN,
        )
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.post(
            "/api/v1/campaigns/",
            json={
                "place_url": "https://map.naver.com/test",
                "campaign_type": "traffic",
                "start_date": "2026-04-01",
                "end_date": "2026-04-01",
                "daily_limit": 100,
            },
            headers=headers,
        )
        assert resp.status_code == 201


# ==================== CampaignUpdate Status Validation ====================


@pytest.mark.asyncio
class TestCampaignUpdateStatusValidation:
    """Verify campaign update rejects invalid status values."""

    async def test_update_campaign_with_invalid_status(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Arbitrary status string should return 422."""
        admin = await create_test_user(
            db_session, email="admin_us@test.com",
            role=UserRole.SYSTEM_ADMIN,
        )

        campaign = Campaign(
            place_url="https://map.naver.com/test",
            place_name="Test",
            campaign_type="traffic",
            status=CampaignStatus.PENDING.value,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
            daily_limit=300,
        )
        db_session.add(campaign)
        await db_session.flush()
        await db_session.refresh(campaign)
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.patch(
            f"/api/v1/campaigns/{campaign.id}",
            json={"status": "nonexistent_status"},
            headers=headers,
        )
        assert resp.status_code == 422
        assert "Invalid campaign status" in resp.text

    async def test_update_campaign_with_valid_status(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Valid status values should succeed."""
        admin = await create_test_user(
            db_session, email="admin_vs@test.com",
            role=UserRole.SYSTEM_ADMIN,
        )

        campaign = Campaign(
            place_url="https://map.naver.com/test",
            place_name="Test",
            campaign_type="traffic",
            status=CampaignStatus.PENDING.value,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
            daily_limit=300,
        )
        db_session.add(campaign)
        await db_session.flush()
        await db_session.refresh(campaign)
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.patch(
            f"/api/v1/campaigns/{campaign.id}",
            json={"status": "queued"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "queued"


# ==================== Keyword Validation ====================


@pytest.mark.asyncio
class TestKeywordValidation:
    """Verify keyword add request validates individual keywords."""

    async def test_empty_keyword_rejected(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Empty string keyword should return 422."""
        admin = await create_test_user(
            db_session, email="admin_ek@test.com",
            role=UserRole.SYSTEM_ADMIN,
        )
        campaign = Campaign(
            place_url="https://map.naver.com/test",
            place_name="Test",
            campaign_type="traffic",
            status=CampaignStatus.PENDING.value,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
            daily_limit=300,
        )
        db_session.add(campaign)
        await db_session.flush()
        await db_session.refresh(campaign)
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.post(
            f"/api/v1/campaigns/{campaign.id}/keywords",
            json={"keywords": ["valid", "", "also_valid"]},
            headers=headers,
        )
        assert resp.status_code == 422
        assert "empty" in resp.text.lower()

    async def test_whitespace_only_keyword_rejected(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Whitespace-only keyword should return 422."""
        admin = await create_test_user(
            db_session, email="admin_wk@test.com",
            role=UserRole.SYSTEM_ADMIN,
        )
        campaign = Campaign(
            place_url="https://map.naver.com/test",
            place_name="Test",
            campaign_type="traffic",
            status=CampaignStatus.PENDING.value,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
            daily_limit=300,
        )
        db_session.add(campaign)
        await db_session.flush()
        await db_session.refresh(campaign)
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.post(
            f"/api/v1/campaigns/{campaign.id}/keywords",
            json={"keywords": ["   "]},
            headers=headers,
        )
        assert resp.status_code == 422
        assert "empty" in resp.text.lower() or "whitespace" in resp.text.lower()

    async def test_keyword_exceeding_255_chars_rejected(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Keyword > 255 characters should return 422."""
        admin = await create_test_user(
            db_session, email="admin_lk@test.com",
            role=UserRole.SYSTEM_ADMIN,
        )
        campaign = Campaign(
            place_url="https://map.naver.com/test",
            place_name="Test",
            campaign_type="traffic",
            status=CampaignStatus.PENDING.value,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
            daily_limit=300,
        )
        db_session.add(campaign)
        await db_session.flush()
        await db_session.refresh(campaign)
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.post(
            f"/api/v1/campaigns/{campaign.id}/keywords",
            json={"keywords": ["a" * 256]},
            headers=headers,
        )
        assert resp.status_code == 422
        assert "255" in resp.text

    async def test_valid_keywords_accepted(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Valid keywords should be accepted."""
        admin = await create_test_user(
            db_session, email="admin_vk@test.com",
            role=UserRole.SYSTEM_ADMIN,
        )
        campaign = Campaign(
            place_url="https://map.naver.com/test",
            place_name="Test",
            campaign_type="traffic",
            status=CampaignStatus.PENDING.value,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
            daily_limit=300,
        )
        db_session.add(campaign)
        await db_session.flush()
        await db_session.refresh(campaign)
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.post(
            f"/api/v1/campaigns/{campaign.id}/keywords",
            json={"keywords": ["keyword1", "keyword2", "a" * 255]},
            headers=headers,
        )
        assert resp.status_code == 201


# ==================== ExtractionJob Rank Validation ====================


@pytest.mark.asyncio
class TestExtractionJobRankValidation:
    """Verify min_rank <= max_rank cross-field validation."""

    async def test_min_rank_greater_than_max_rank_rejected(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """min_rank > max_rank should return 422."""
        admin = await create_test_user(
            db_session, email="admin_rk@test.com",
            role=UserRole.SYSTEM_ADMIN,
        )
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.post(
            "/api/v1/extraction/start",
            json={
                "naver_url": "https://map.naver.com/test",
                "min_rank": 50,
                "max_rank": 10,
            },
            headers=headers,
        )
        assert resp.status_code == 422
        assert "min_rank" in resp.text.lower()

    async def test_equal_min_max_rank_accepted(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """min_rank == max_rank should succeed."""
        admin = await create_test_user(
            db_session, email="admin_rk2@test.com",
            role=UserRole.SYSTEM_ADMIN,
        )
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.post(
            "/api/v1/extraction/start",
            json={
                "naver_url": "https://map.naver.com/test",
                "min_rank": 25,
                "max_rank": 25,
            },
            headers=headers,
        )
        assert resp.status_code == 201


# ==================== Callback Status Validation ====================


@pytest.mark.asyncio
class TestCallbackStatusValidation:
    """Verify callback requests reject invalid status values."""

    async def test_extraction_callback_invalid_status(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Extraction callback with invalid status should return 422."""
        job = ExtractionJob(
            naver_url="https://map.naver.com/test",
            status=ExtractionJobStatus.RUNNING.value,
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)
        await db_session.commit()

        resp = await client.post(
            f"/internal/callback/extraction/{job.id}",
            json={"status": "invalid_status"},
        )
        assert resp.status_code == 422

    async def test_campaign_callback_invalid_status(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Campaign callback with invalid status should return 422."""
        campaign = Campaign(
            place_url="https://map.naver.com/test",
            place_name="Test",
            campaign_type="traffic",
            status=CampaignStatus.REGISTERING.value,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
            daily_limit=300,
        )
        db_session.add(campaign)
        await db_session.flush()
        await db_session.refresh(campaign)
        await db_session.commit()

        resp = await client.post(
            f"/internal/callback/campaign/{campaign.id}",
            json={"status": "invalid_status"},
        )
        assert resp.status_code == 422


# ==================== Double Payment Confirmation ====================


@pytest.mark.asyncio
class TestDoublePaymentConfirmation:
    """Verify double payment confirmation is rejected."""

    async def test_cannot_confirm_payment_twice(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """Second payment confirmation on the same order should fail."""
        dist = await create_test_user(
            db_session, email="dist_dp@test.com",
            role=UserRole.DISTRIBUTOR,
            company_id=test_company.id,
        )
        admin = await create_test_user(
            db_session, email="admin_dp@test.com",
            role=UserRole.COMPANY_ADMIN,
            company_id=test_company.id,
        )
        product = await _product(db_session)
        await balance_service.deposit(db_session, dist.id, 1000000, "Init")
        await db_session.commit()

        # Create and submit order
        dist_headers = get_auth_header(dist)
        resp = await client.post(
            "/api/v1/orders/",
            json={"items": [{"product_id": product.id, "quantity": 1}]},
            headers=dist_headers,
        )
        assert resp.status_code == 201
        order_id = resp.json()["id"]

        resp = await client.post(
            f"/api/v1/orders/{order_id}/submit",
            headers=dist_headers,
        )
        assert resp.status_code == 200

        # First confirmation - should succeed
        admin_headers = get_auth_header(admin)
        resp1 = await client.post(
            f"/api/v1/orders/{order_id}/confirm-payment",
            headers=admin_headers,
        )
        assert resp1.status_code == 200
        assert resp1.json()["status"] == "payment_confirmed"

        # Second confirmation - should fail
        resp2 = await client.post(
            f"/api/v1/orders/{order_id}/confirm-payment",
            headers=admin_headers,
        )
        assert resp2.status_code == 400


# ==================== Pipeline Overview Edge Cases ====================


@pytest.mark.asyncio
class TestPipelineOverviewEdgeCases:
    """Verify pipeline overview works correctly in edge cases."""

    async def test_pipeline_overview_with_no_data(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Pipeline overview with no pipeline states should return empty stages."""
        admin = await create_test_user(
            db_session, email="admin_po@test.com",
            role=UserRole.SYSTEM_ADMIN,
        )
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.get("/api/v1/pipeline/overview", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["stages"] == []


# ==================== Campaign total_limit Validation ====================


@pytest.mark.asyncio
class TestCampaignTotalLimitValidation:
    """Verify total_limit must be positive if specified."""

    async def test_campaign_create_zero_total_limit_rejected(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """total_limit=0 should return 422."""
        admin = await create_test_user(
            db_session, email="admin_tl@test.com",
            role=UserRole.SYSTEM_ADMIN,
        )
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.post(
            "/api/v1/campaigns/",
            json={
                "place_url": "https://map.naver.com/test",
                "campaign_type": "traffic",
                "start_date": "2026-03-01",
                "end_date": "2026-03-31",
                "daily_limit": 100,
                "total_limit": 0,
            },
            headers=headers,
        )
        assert resp.status_code == 422

    async def test_campaign_create_negative_total_limit_rejected(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """total_limit < 0 should return 422."""
        admin = await create_test_user(
            db_session, email="admin_tl2@test.com",
            role=UserRole.SYSTEM_ADMIN,
        )
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.post(
            "/api/v1/campaigns/",
            json={
                "place_url": "https://map.naver.com/test",
                "campaign_type": "traffic",
                "start_date": "2026-03-01",
                "end_date": "2026-03-31",
                "daily_limit": 100,
                "total_limit": -5,
            },
            headers=headers,
        )
        assert resp.status_code == 422


# ==================== Order with Negative Quantity ====================


@pytest.mark.asyncio
class TestOrderNegativeQuantity:
    """Verify negative quantity is rejected."""

    async def test_order_with_negative_quantity(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """Order with negative quantity should return 422."""
        user = await create_test_user(
            db_session, email="user_nq@test.com",
            role=UserRole.DISTRIBUTOR,
            company_id=test_company.id,
        )
        product = await _product(db_session)
        await db_session.commit()

        headers = get_auth_header(user)
        resp = await client.post(
            "/api/v1/orders/",
            json={"items": [{"product_id": product.id, "quantity": -1}]},
            headers=headers,
        )
        assert resp.status_code == 422


# ==================== Campaign Invalid Type ====================


@pytest.mark.asyncio
class TestCampaignInvalidType:
    """Verify campaign_type validation."""

    async def test_create_campaign_with_invalid_type(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Invalid campaign_type should return 422."""
        admin = await create_test_user(
            db_session, email="admin_ct@test.com",
            role=UserRole.SYSTEM_ADMIN,
        )
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.post(
            "/api/v1/campaigns/",
            json={
                "place_url": "https://map.naver.com/test",
                "campaign_type": "invalid_type",
                "start_date": "2026-03-01",
                "end_date": "2026-03-31",
                "daily_limit": 100,
            },
            headers=headers,
        )
        assert resp.status_code == 422


# ==================== Extraction Cancel Edge Cases ====================


@pytest.mark.asyncio
class TestExtractionCancelEdgeCases:
    """Verify cancellation restrictions for extraction jobs."""

    async def test_cannot_cancel_completed_extraction(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Cannot cancel a completed extraction job."""
        admin = await create_test_user(
            db_session, email="admin_ce@test.com",
            role=UserRole.SYSTEM_ADMIN,
        )
        job = ExtractionJob(
            naver_url="https://map.naver.com/test",
            status=ExtractionJobStatus.COMPLETED.value,
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.post(
            f"/api/v1/extraction/jobs/{job.id}/cancel",
            headers=headers,
        )
        assert resp.status_code == 400
        assert "completed" in resp.json()["detail"].lower()

    async def test_cannot_cancel_failed_extraction(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Cannot cancel a failed extraction job."""
        admin = await create_test_user(
            db_session, email="admin_fe@test.com",
            role=UserRole.SYSTEM_ADMIN,
        )
        job = ExtractionJob(
            naver_url="https://map.naver.com/test",
            status=ExtractionJobStatus.FAILED.value,
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.post(
            f"/api/v1/extraction/jobs/{job.id}/cancel",
            headers=headers,
        )
        assert resp.status_code == 400

    async def test_cannot_cancel_already_cancelled_extraction(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Cannot cancel an already-cancelled extraction job."""
        admin = await create_test_user(
            db_session, email="admin_ac@test.com",
            role=UserRole.SYSTEM_ADMIN,
        )
        job = ExtractionJob(
            naver_url="https://map.naver.com/test",
            status=ExtractionJobStatus.CANCELLED.value,
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.post(
            f"/api/v1/extraction/jobs/{job.id}/cancel",
            headers=headers,
        )
        assert resp.status_code == 400


# ==================== Assignment Confirm Status Edge Case ====================


@pytest.mark.asyncio
class TestAssignmentConfirmStatusEdgeCases:
    """Verify confirm_assignment works only for auto_assigned items."""

    async def test_cannot_confirm_pending_assignment(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Cannot confirm an assignment in 'pending' status."""
        from app.services import assignment_service

        product = await _product(db_session)
        order = await _order(db_session, distributor.id, test_company.id)
        oi = await _order_item(db_session, order.id, product.id)
        await db_session.flush()

        assert oi.assignment_status == AssignmentStatus.PENDING.value

        with pytest.raises(ValueError, match="Cannot confirm"):
            await assignment_service.confirm_assignment(
                db_session, oi, distributor.id,
            )

    async def test_cannot_confirm_already_confirmed_assignment(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Cannot confirm an assignment already in 'confirmed' status."""
        from app.services import assignment_service

        product = await _product(db_session)
        order = await _order(db_session, distributor.id, test_company.id)
        oi = await _order_item(db_session, order.id, product.id)
        oi.assignment_status = AssignmentStatus.CONFIRMED.value
        await db_session.flush()

        with pytest.raises(ValueError, match="Cannot confirm"):
            await assignment_service.confirm_assignment(
                db_session, oi, distributor.id,
            )

    async def test_cannot_confirm_overridden_assignment(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Cannot confirm an assignment in 'overridden' status."""
        from app.services import assignment_service

        product = await _product(db_session)
        order = await _order(db_session, distributor.id, test_company.id)
        oi = await _order_item(db_session, order.id, product.id)
        oi.assignment_status = AssignmentStatus.OVERRIDDEN.value
        await db_session.flush()

        with pytest.raises(ValueError, match="Cannot confirm"):
            await assignment_service.confirm_assignment(
                db_session, oi, distributor.id,
            )


# ==================== Network Preset API Validation ====================


@pytest.mark.asyncio
class TestNetworkPresetAPIValidation:
    """Verify network preset validation at the API level."""

    async def test_network_preset_invalid_campaign_type(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """Network preset with invalid campaign_type should return 422."""
        admin = await create_test_user(
            db_session, email="admin_np@test.com",
            role=UserRole.SYSTEM_ADMIN,
        )
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.post(
            "/api/v1/network-presets/",
            json={
                "company_id": test_company.id,
                "campaign_type": "invalid_type",
                "tier_order": 1,
                "name": "Test Preset",
            },
            headers=headers,
        )
        assert resp.status_code == 422

    async def test_network_preset_zero_tier_order(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """Network preset with tier_order=0 should return 422."""
        admin = await create_test_user(
            db_session, email="admin_np2@test.com",
            role=UserRole.SYSTEM_ADMIN,
        )
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.post(
            "/api/v1/network-presets/",
            json={
                "company_id": test_company.id,
                "campaign_type": "traffic",
                "tier_order": 0,
                "name": "Zero Tier",
            },
            headers=headers,
        )
        assert resp.status_code == 422


# ==================== Withdrawal Exceeding Balance ====================


@pytest.mark.asyncio
class TestWithdrawalExceedingBalance:
    """Verify withdrawal amount checks."""

    async def test_withdraw_exceeding_balance(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """Withdrawing more than balance should fail with 400."""
        admin = await create_test_user(
            db_session, email="admin_we@test.com",
            role=UserRole.SYSTEM_ADMIN,
        )
        user = await create_test_user(
            db_session, email="user_we@test.com",
            role=UserRole.DISTRIBUTOR,
            company_id=test_company.id,
        )
        await balance_service.deposit(db_session, user.id, 5000, "Init")
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.post(
            "/api/v1/balance/withdraw",
            json={"user_id": str(user.id), "amount": 5001},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "Insufficient" in resp.json()["detail"]

    async def test_withdraw_from_zero_balance(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """Withdrawing from zero balance should fail with 400."""
        admin = await create_test_user(
            db_session, email="admin_zb@test.com",
            role=UserRole.SYSTEM_ADMIN,
        )
        user = await create_test_user(
            db_session, email="user_zb@test.com",
            role=UserRole.DISTRIBUTOR,
            company_id=test_company.id,
        )
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.post(
            "/api/v1/balance/withdraw",
            json={"user_id": str(user.id), "amount": 1},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "Insufficient" in resp.json()["detail"]


# ==================== Keyword Round Number Validation ====================


@pytest.mark.asyncio
class TestKeywordRoundNumberValidation:
    """Verify round_number must be >= 1."""

    async def test_keyword_add_zero_round_number(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """round_number=0 should return 422."""
        admin = await create_test_user(
            db_session, email="admin_rn@test.com",
            role=UserRole.SYSTEM_ADMIN,
        )
        campaign = Campaign(
            place_url="https://map.naver.com/test",
            place_name="Test",
            campaign_type="traffic",
            status=CampaignStatus.PENDING.value,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
            daily_limit=300,
        )
        db_session.add(campaign)
        await db_session.flush()
        await db_session.refresh(campaign)
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.post(
            f"/api/v1/campaigns/{campaign.id}/keywords",
            json={"keywords": ["keyword1"], "round_number": 0},
            headers=headers,
        )
        assert resp.status_code == 422

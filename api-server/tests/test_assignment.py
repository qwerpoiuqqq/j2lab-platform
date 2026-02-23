"""Tests for auto-assignment algorithm - core business logic.

Tests the 3-step assignment algorithm:
Step 1: Extension check
Step 2: Network selection
Step 3: Account selection
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign, CampaignStatus
from app.models.company import Company
from app.models.network_preset import NetworkPreset
from app.models.order import Order, OrderItem, OrderStatus, AssignmentStatus
from app.models.place import Place
from app.models.product import Product
from app.models.superap_account import SuperapAccount
from app.models.user import User, UserRole
from app.services import assignment_service
from tests.conftest import (
    create_test_company,
    create_test_user,
    get_auth_header,
)


# === Helper factories ===

async def _place(db, place_id=1111):
    p = Place(id=place_id, name="Test Place", place_type="restaurant")
    db.add(p)
    await db.flush()
    return p


async def _product(db):
    from datetime import time
    p = Product(name="Traffic", code="traffic", base_price=10000, daily_deadline=time(18, 0))
    db.add(p)
    await db.flush()
    return p


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


async def _order(db, user_id, company_id):
    import secrets
    o = Order(
        order_number=f"ORD-TEST-{secrets.token_hex(2).upper()}",
        user_id=user_id,
        company_id=company_id,
        status=OrderStatus.PAYMENT_CONFIRMED.value,
    )
    db.add(o)
    await db.flush()
    return o


async def _preset(db, company_id, campaign_type="traffic", tier_order=1, name="Net 1"):
    np = NetworkPreset(
        company_id=company_id,
        campaign_type=campaign_type,
        tier_order=tier_order,
        name=name,
        media_config={"머니워크": True},
        is_active=True,
    )
    db.add(np)
    await db.flush()
    await db.refresh(np)
    return np


async def _account(db, company_id, preset_id, login_id="acc1", order=0):
    from app.utils.crypto import encrypt_password
    a = SuperapAccount(
        user_id_superap=login_id,
        password_encrypted=encrypt_password("test123"),
        company_id=company_id,
        network_preset_id=preset_id,
        assignment_order=order,
        is_active=True,
    )
    db.add(a)
    await db.flush()
    await db.refresh(a)
    return a


async def _campaign(db, place_id, campaign_type="traffic", end_date=None,
                    total_limit=None, account_id=None, preset_id=None, status="active"):
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


@pytest.mark.asyncio
class TestAutoAssignNewSetup:
    """Test auto-assignment for new campaigns (no extension)."""

    async def test_assign_first_network(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """First assignment picks network with tier_order=1."""
        place = await _place(db_session)
        product = await _product(db_session)
        order = await _order(db_session, distributor.id, test_company.id)
        oi = await _order_item(db_session, order.id, product.id, place.id)

        preset1 = await _preset(db_session, test_company.id, tier_order=1, name="Net 1")
        preset2 = await _preset(db_session, test_company.id, tier_order=2, name="Net 2")
        acc1 = await _account(db_session, test_company.id, preset1.id, login_id="acc1")
        acc2 = await _account(db_session, test_company.id, preset2.id, login_id="acc2")

        await db_session.flush()

        result = await assignment_service.auto_assign(
            db_session,
            order_item=oi,
            campaign_type="traffic",
            place_id=place.id,
            company_id=test_company.id,
        )

        assert result.assigned_account_id == acc1.id
        assert result.network_preset_id == preset1.id
        assert result.is_extension is False
        assert oi.assignment_status == AssignmentStatus.AUTO_ASSIGNED.value

    async def test_assign_second_network_after_first_used(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """If network 1 already used for this place, pick network 2."""
        place = await _place(db_session)
        product = await _product(db_session)
        order = await _order(db_session, distributor.id, test_company.id)
        oi = await _order_item(db_session, order.id, product.id, place.id)

        preset1 = await _preset(db_session, test_company.id, tier_order=1, name="Net 1")
        preset2 = await _preset(db_session, test_company.id, tier_order=2, name="Net 2")
        acc1 = await _account(db_session, test_company.id, preset1.id, login_id="acc1")
        acc2 = await _account(db_session, test_company.id, preset2.id, login_id="acc2")

        # Simulate network 1 already used for this place
        await _campaign(
            db_session, place.id, "traffic",
            account_id=acc1.id, preset_id=preset1.id,
        )
        await db_session.flush()

        result = await assignment_service.auto_assign(
            db_session,
            order_item=oi,
            campaign_type="traffic",
            place_id=place.id,
            company_id=test_company.id,
        )

        assert result.assigned_account_id == acc2.id
        assert result.network_preset_id == preset2.id

    async def test_all_networks_exhausted_suggests_type_change(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """When all networks used, suggest campaign type change."""
        place = await _place(db_session)
        product = await _product(db_session)
        order = await _order(db_session, distributor.id, test_company.id)
        oi = await _order_item(db_session, order.id, product.id, place.id)

        preset1 = await _preset(db_session, test_company.id, tier_order=1)
        acc1 = await _account(db_session, test_company.id, preset1.id, login_id="acc1")

        # All networks used
        await _campaign(
            db_session, place.id, "traffic",
            account_id=acc1.id, preset_id=preset1.id,
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
        assert "save" in result.suggestion


@pytest.mark.asyncio
class TestAutoAssignExtension:
    """Test extension check (Step 1)."""

    async def test_extension_within_7_days_and_under_10000(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Extend if same place, end_date within 7 days, total < 10,000."""
        place = await _place(db_session)
        product = await _product(db_session)
        order = await _order(db_session, distributor.id, test_company.id)
        oi = await _order_item(db_session, order.id, product.id, place.id)

        preset1 = await _preset(db_session, test_company.id, tier_order=1)
        acc1 = await _account(db_session, test_company.id, preset1.id, login_id="acc1")

        # Existing campaign ending recently (within 7 days)
        today = date.today()
        existing = await _campaign(
            db_session, place.id, "traffic",
            end_date=today - timedelta(days=3),
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
            total_limit=3000,  # 5000 + 3000 = 8000 < 10000
        )

        assert result.is_extension is True
        assert result.extend_target_campaign_id == existing.id
        assert result.assigned_account_id == acc1.id
        assert result.network_preset_id == preset1.id

    async def test_no_extension_over_10000(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """New setup if combined total >= 10,000."""
        place = await _place(db_session)
        product = await _product(db_session)
        order = await _order(db_session, distributor.id, test_company.id)
        oi = await _order_item(db_session, order.id, product.id, place.id)

        preset1 = await _preset(db_session, test_company.id, tier_order=1, name="Net 1")
        preset2 = await _preset(db_session, test_company.id, tier_order=2, name="Net 2")
        acc1 = await _account(db_session, test_company.id, preset1.id, login_id="acc1")
        acc2 = await _account(db_session, test_company.id, preset2.id, login_id="acc2")

        today = date.today()
        await _campaign(
            db_session, place.id, "traffic",
            end_date=today - timedelta(days=2),
            total_limit=8000,
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
            total_limit=5000,  # 8000 + 5000 = 13000 >= 10000
        )

        # Should NOT extend, should use next network
        assert result.is_extension is False
        assert result.network_preset_id == preset2.id
        assert result.assigned_account_id == acc2.id

    async def test_no_extension_old_campaign(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """No extension if campaign ended more than 7 days ago."""
        place = await _place(db_session)
        product = await _product(db_session)
        order = await _order(db_session, distributor.id, test_company.id)
        oi = await _order_item(db_session, order.id, product.id, place.id)

        preset1 = await _preset(db_session, test_company.id, tier_order=1)
        acc1 = await _account(db_session, test_company.id, preset1.id, login_id="acc1")

        today = date.today()
        await _campaign(
            db_session, place.id, "traffic",
            end_date=today - timedelta(days=10),  # More than 7 days ago
            total_limit=3000,
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
            total_limit=3000,
        )

        # No extension, but network already used so picks from tier_order
        assert result.is_extension is False


@pytest.mark.asyncio
class TestAccountSelection:
    """Test account selection (Step 3)."""

    async def test_account_selected_by_assignment_order(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Accounts are selected by assignment_order ASC."""
        place = await _place(db_session)
        product = await _product(db_session)
        order = await _order(db_session, distributor.id, test_company.id)
        oi = await _order_item(db_session, order.id, product.id, place.id)

        preset = await _preset(db_session, test_company.id, tier_order=1)
        acc_high = await _account(db_session, test_company.id, preset.id, login_id="high", order=10)
        acc_low = await _account(db_session, test_company.id, preset.id, login_id="low", order=1)

        await db_session.flush()

        result = await assignment_service.auto_assign(
            db_session,
            order_item=oi,
            campaign_type="traffic",
            place_id=place.id,
            company_id=test_company.id,
        )

        assert result.assigned_account_id == acc_low.id
        assert result.assigned_account_name == "low"

    async def test_no_active_accounts(
        self,
        db_session: AsyncSession,
        test_company: Company,
        distributor: User,
    ):
        """Error when no active accounts in the network."""
        place = await _place(db_session)
        product = await _product(db_session)
        order = await _order(db_session, distributor.id, test_company.id)
        oi = await _order_item(db_session, order.id, product.id, place.id)

        preset = await _preset(db_session, test_company.id, tier_order=1)
        # Create inactive account only
        acc = await _account(db_session, test_company.id, preset.id, login_id="inactive")
        acc.is_active = False
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


@pytest.mark.asyncio
class TestConfirmOverride:
    """Test assignment confirmation and override via API."""

    async def test_confirm_assignment(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        admin = await create_test_user(
            db_session, email="cadmin@test.com", role=UserRole.COMPANY_ADMIN,
            company_id=test_company.id,
        )
        dist = await create_test_user(
            db_session, email="dist@test.com", role=UserRole.DISTRIBUTOR,
            company_id=test_company.id,
        )
        place = await _place(db_session)
        product = await _product(db_session)
        order = await _order(db_session, dist.id, test_company.id)
        oi = await _order_item(db_session, order.id, product.id, place.id)

        # Set as auto_assigned
        oi.assignment_status = AssignmentStatus.AUTO_ASSIGNED.value
        oi.assigned_account_id = 1
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.post(
            f"/api/v1/assignment/{oi.id}/confirm",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Assignment confirmed"

    async def test_confirm_not_auto_assigned(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        admin = await create_test_user(
            db_session, email="cadmin@test.com", role=UserRole.COMPANY_ADMIN,
            company_id=test_company.id,
        )
        dist = await create_test_user(
            db_session, email="dist@test.com", role=UserRole.DISTRIBUTOR,
            company_id=test_company.id,
        )
        place = await _place(db_session)
        product = await _product(db_session)
        order = await _order(db_session, dist.id, test_company.id)
        oi = await _order_item(db_session, order.id, product.id, place.id)
        # Status is pending (not auto_assigned)
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.post(
            f"/api/v1/assignment/{oi.id}/confirm",
            headers=headers,
        )
        assert resp.status_code == 400

    async def test_override_assignment(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        admin = await create_test_user(
            db_session, email="cadmin@test.com", role=UserRole.COMPANY_ADMIN,
            company_id=test_company.id,
        )
        dist = await create_test_user(
            db_session, email="dist@test.com", role=UserRole.DISTRIBUTOR,
            company_id=test_company.id,
        )
        preset = await _preset(db_session, test_company.id, tier_order=1)
        acc = await _account(db_session, test_company.id, preset.id, login_id="acc_new")
        place = await _place(db_session)
        product = await _product(db_session)
        order = await _order(db_session, dist.id, test_company.id)
        oi = await _order_item(db_session, order.id, product.id, place.id)
        oi.assignment_status = AssignmentStatus.AUTO_ASSIGNED.value
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.patch(
            f"/api/v1/assignment/{oi.id}/account",
            json={"account_id": acc.id},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Assignment overridden"

    async def test_bulk_confirm(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        admin = await create_test_user(
            db_session, email="cadmin@test.com", role=UserRole.COMPANY_ADMIN,
            company_id=test_company.id,
        )
        dist = await create_test_user(
            db_session, email="dist@test.com", role=UserRole.DISTRIBUTOR,
            company_id=test_company.id,
        )
        place = await _place(db_session)
        product = await _product(db_session)
        order = await _order(db_session, dist.id, test_company.id)
        oi1 = await _order_item(db_session, order.id, product.id, place.id)
        oi2 = await _order_item(db_session, order.id, product.id, place.id)
        oi1.assignment_status = AssignmentStatus.AUTO_ASSIGNED.value
        oi1.assigned_account_id = 1
        oi2.assignment_status = AssignmentStatus.AUTO_ASSIGNED.value
        oi2.assigned_account_id = 1
        await db_session.commit()

        headers = get_auth_header(admin)
        resp = await client.post(
            "/api/v1/assignment/bulk-confirm",
            json={"item_ids": [oi1.id, oi2.id]},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_confirmed"] == 2
        assert data["total_errors"] == 0

    async def test_unauthorized_sub_account(
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
        resp = await client.get("/api/v1/assignment/queue", headers=headers)
        assert resp.status_code == 403

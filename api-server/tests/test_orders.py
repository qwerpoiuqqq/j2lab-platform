"""Tests for orders endpoints: full order lifecycle with state transitions."""

from __future__ import annotations

from datetime import time

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.user import User, UserRole
from tests.conftest import (
    create_test_company,
    create_test_user,
    get_auth_header,
)


async def create_test_product(
    db: AsyncSession,
    name: str = "Traffic Campaign",
    code: str = "traffic",
    base_price: int = 10000,
) -> Product:
    """Create a test product."""
    product = Product(
        name=name,
        code=code,
        base_price=base_price,
        daily_deadline=time(18, 0),
        is_active=True,
    )
    db.add(product)
    await db.flush()
    await db.refresh(product)
    return product


@pytest_asyncio.fixture
async def product(db_session: AsyncSession) -> Product:
    """Create a default test product."""
    return await create_test_product(db_session)


@pytest.mark.asyncio
class TestCreateOrder:
    """Tests for POST /api/v1/orders."""

    async def test_create_order_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        product: Product,
    ):
        """Distributor can create an order in draft status."""
        await db_session.commit()

        headers = get_auth_header(distributor)
        resp = await client.post(
            "/api/v1/orders/",
            json={
                "notes": "Test order",
                "items": [
                    {"product_id": product.id, "quantity": 2},
                ],
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "draft"
        assert data["user_id"] == str(distributor.id)
        assert data["total_amount"] == 20000  # 10000 * 2
        assert data["vat_amount"] == 2000  # 10% of 20000
        assert len(data["items"]) == 1
        assert data["items"][0]["unit_price"] == 10000
        assert data["items"][0]["quantity"] == 2
        assert data["items"][0]["subtotal"] == 20000
        assert data["order_number"].startswith("ORD-")

    async def test_create_order_invalid_product(
        self,
        client: AsyncClient,
        distributor: User,
    ):
        """Creating an order with nonexistent product should fail."""
        headers = get_auth_header(distributor)
        resp = await client.post(
            "/api/v1/orders/",
            json={
                "items": [{"product_id": 9999, "quantity": 1}],
            },
            headers=headers,
        )
        assert resp.status_code == 400

    async def test_create_order_multiple_items(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        product: Product,
    ):
        """Create an order with multiple items."""
        product2 = await create_test_product(
            db_session, name="Save Campaign", code="save", base_price=5000
        )
        await db_session.commit()

        headers = get_auth_header(distributor)
        resp = await client.post(
            "/api/v1/orders/",
            json={
                "items": [
                    {"product_id": product.id, "quantity": 1},
                    {"product_id": product2.id, "quantity": 3},
                ],
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["total_amount"] == 25000  # 10000 + 15000
        assert len(data["items"]) == 2


@pytest.mark.asyncio
class TestListOrders:
    """Tests for GET /api/v1/orders."""

    async def test_list_orders_as_system_admin(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        system_admin: User,
        distributor: User,
        product: Product,
    ):
        """system_admin can see all orders."""
        await db_session.commit()

        # Create order as distributor
        dist_headers = get_auth_header(distributor)
        await client.post(
            "/api/v1/orders/",
            json={"items": [{"product_id": product.id, "quantity": 1}]},
            headers=dist_headers,
        )

        admin_headers = get_auth_header(system_admin)
        resp = await client.get("/api/v1/orders/", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    async def test_list_orders_role_filtering(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        sub_account: User,
        product: Product,
    ):
        """sub_account sees only own orders."""
        await db_session.commit()

        # Create order as distributor
        dist_headers = get_auth_header(distributor)
        await client.post(
            "/api/v1/orders/",
            json={"items": [{"product_id": product.id, "quantity": 1}]},
            headers=dist_headers,
        )

        # Create order as sub_account
        sub_headers = get_auth_header(sub_account)
        await client.post(
            "/api/v1/orders/",
            json={"items": [{"product_id": product.id, "quantity": 1}]},
            headers=sub_headers,
        )

        # sub_account should only see their own order
        resp = await client.get("/api/v1/orders/", headers=sub_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["user_id"] == str(sub_account.id)


@pytest.mark.asyncio
class TestGetOrder:
    """Tests for GET /api/v1/orders/{id}."""

    async def test_get_order_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        product: Product,
    ):
        """Get order with items."""
        await db_session.commit()

        headers = get_auth_header(distributor)
        create_resp = await client.post(
            "/api/v1/orders/",
            json={"items": [{"product_id": product.id, "quantity": 1}]},
            headers=headers,
        )
        order_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/orders/{order_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == order_id
        assert len(data["items"]) == 1

    async def test_get_order_not_found(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Nonexistent order should return 404."""
        headers = get_auth_header(system_admin)
        resp = await client.get("/api/v1/orders/9999", headers=headers)
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestOrderStateTransitions:
    """Tests for the full order state machine."""

    async def _create_draft_order(
        self, client: AsyncClient, user: User, product: Product
    ) -> int:
        """Helper to create a draft order."""
        headers = get_auth_header(user)
        resp = await client.post(
            "/api/v1/orders/",
            json={"items": [{"product_id": product.id, "quantity": 1}]},
            headers=headers,
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    async def test_submit_order(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        product: Product,
    ):
        """draft -> submitted transition."""
        await db_session.commit()

        order_id = await self._create_draft_order(client, distributor, product)

        headers = get_auth_header(distributor)
        resp = await client.post(
            f"/api/v1/orders/{order_id}/submit", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "submitted"
        assert data["submitted_by"] == str(distributor.id)
        assert data["submitted_at"] is not None

    async def test_confirm_payment(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        company_admin: User,
        product: Product,
    ):
        """submitted -> payment_confirmed transition with balance deduction."""
        # Give distributor enough balance
        from app.services import balance_service

        await balance_service.deposit(
            db_session, distributor.id, 100000, "Initial deposit"
        )
        await db_session.commit()

        order_id = await self._create_draft_order(client, distributor, product)

        # Submit
        dist_headers = get_auth_header(distributor)
        await client.post(
            f"/api/v1/orders/{order_id}/submit", headers=dist_headers
        )

        # Confirm payment
        admin_headers = get_auth_header(company_admin)
        resp = await client.post(
            f"/api/v1/orders/{order_id}/confirm-payment", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "payment_confirmed"
        assert data["payment_status"] == "confirmed"

        # Verify balance was deducted
        balance_resp = await client.get(
            f"/api/v1/balance/{distributor.id}", headers=admin_headers
        )
        assert balance_resp.status_code == 200
        assert balance_resp.json()["balance"] == 90000  # 100000 - 10000

    async def test_confirm_payment_insufficient_balance(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        company_admin: User,
        product: Product,
    ):
        """Payment confirmation with insufficient balance should fail."""
        await db_session.commit()

        order_id = await self._create_draft_order(client, distributor, product)

        # Submit
        dist_headers = get_auth_header(distributor)
        await client.post(
            f"/api/v1/orders/{order_id}/submit", headers=dist_headers
        )

        # Confirm payment (balance = 0, order cost = 10000)
        admin_headers = get_auth_header(company_admin)
        resp = await client.post(
            f"/api/v1/orders/{order_id}/confirm-payment", headers=admin_headers
        )
        assert resp.status_code == 400
        assert "Insufficient" in resp.json()["detail"]

    async def test_reject_order(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        company_admin: User,
        product: Product,
    ):
        """submitted -> rejected transition."""
        await db_session.commit()

        order_id = await self._create_draft_order(client, distributor, product)

        # Submit
        dist_headers = get_auth_header(distributor)
        await client.post(
            f"/api/v1/orders/{order_id}/submit", headers=dist_headers
        )

        # Reject
        admin_headers = get_auth_header(company_admin)
        resp = await client.post(
            f"/api/v1/orders/{order_id}/reject",
            json={"reason": "Invalid order details"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"
        assert "Invalid order details" in data["notes"]

    async def test_cancel_draft_order(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        company_admin: User,
        product: Product,
    ):
        """draft -> cancelled transition."""
        await db_session.commit()

        order_id = await self._create_draft_order(client, distributor, product)

        admin_headers = get_auth_header(company_admin)
        resp = await client.post(
            f"/api/v1/orders/{order_id}/cancel", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"

    async def test_cancel_submitted_order(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        company_admin: User,
        product: Product,
    ):
        """submitted -> cancelled transition."""
        await db_session.commit()

        order_id = await self._create_draft_order(client, distributor, product)

        # Submit first
        dist_headers = get_auth_header(distributor)
        await client.post(
            f"/api/v1/orders/{order_id}/submit", headers=dist_headers
        )

        # Cancel
        admin_headers = get_auth_header(company_admin)
        resp = await client.post(
            f"/api/v1/orders/{order_id}/cancel", headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    async def test_cannot_cancel_confirmed_order(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        company_admin: User,
        product: Product,
    ):
        """Cannot cancel a payment_confirmed order."""
        from app.services import balance_service

        await balance_service.deposit(
            db_session, distributor.id, 100000, "Initial deposit"
        )
        await db_session.commit()

        order_id = await self._create_draft_order(client, distributor, product)

        dist_headers = get_auth_header(distributor)
        await client.post(
            f"/api/v1/orders/{order_id}/submit", headers=dist_headers
        )

        admin_headers = get_auth_header(company_admin)
        await client.post(
            f"/api/v1/orders/{order_id}/confirm-payment", headers=admin_headers
        )

        # Try to cancel - should fail
        resp = await client.post(
            f"/api/v1/orders/{order_id}/cancel", headers=admin_headers
        )
        assert resp.status_code == 400

    async def test_cannot_submit_already_submitted(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        product: Product,
    ):
        """Cannot submit an already submitted order."""
        await db_session.commit()

        order_id = await self._create_draft_order(client, distributor, product)

        headers = get_auth_header(distributor)
        # Submit first time
        await client.post(
            f"/api/v1/orders/{order_id}/submit", headers=headers
        )

        # Submit again - should fail
        resp = await client.post(
            f"/api/v1/orders/{order_id}/submit", headers=headers
        )
        assert resp.status_code == 400

    async def test_cannot_reject_draft_order(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        company_admin: User,
        product: Product,
    ):
        """Cannot reject a draft order (only submitted)."""
        await db_session.commit()

        order_id = await self._create_draft_order(client, distributor, product)

        admin_headers = get_auth_header(company_admin)
        resp = await client.post(
            f"/api/v1/orders/{order_id}/reject",
            json={"reason": "No reason"},
            headers=admin_headers,
        )
        assert resp.status_code == 400


@pytest.mark.asyncio
class TestOrderPermissions:
    """Tests for order access control."""

    async def test_distributor_cannot_confirm_payment(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        product: Product,
    ):
        """Distributor cannot confirm payment."""
        await db_session.commit()

        headers = get_auth_header(distributor)
        create_resp = await client.post(
            "/api/v1/orders/",
            json={"items": [{"product_id": product.id, "quantity": 1}]},
            headers=headers,
        )
        order_id = create_resp.json()["id"]

        await client.post(
            f"/api/v1/orders/{order_id}/submit", headers=headers
        )

        resp = await client.post(
            f"/api/v1/orders/{order_id}/confirm-payment", headers=headers
        )
        assert resp.status_code == 403

    async def test_sub_account_cannot_view_others_order(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        sub_account: User,
        product: Product,
    ):
        """sub_account cannot view another user's order."""
        await db_session.commit()

        # Create order as distributor
        dist_headers = get_auth_header(distributor)
        create_resp = await client.post(
            "/api/v1/orders/",
            json={"items": [{"product_id": product.id, "quantity": 1}]},
            headers=dist_headers,
        )
        order_id = create_resp.json()["id"]

        # Try to view as sub_account (not owner)
        sub_headers = get_auth_header(sub_account)
        resp = await client.get(
            f"/api/v1/orders/{order_id}", headers=sub_headers
        )
        assert resp.status_code == 403

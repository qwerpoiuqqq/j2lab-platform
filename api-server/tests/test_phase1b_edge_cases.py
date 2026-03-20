"""Phase 1B edge case tests: orders, products, balance, system_settings.

Covers:
- Order state transition impossible cases (completed->draft, etc.)
- Balance insufficient for payment
- Nonexistent product_id in order
- Cross-company product/order access
- Price policy priority accuracy
- System settings JSON diverse types
- Cancel + refund verification
- Inactive product ordering
- Order update restrictions
- Balance concurrency safety (basic)
- Role permission edge cases
"""

from __future__ import annotations

import uuid
from datetime import date, time

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.order import Order, OrderStatus
from app.models.price_policy import PricePolicy
from app.models.product import Product
from app.models.system_setting import SystemSetting
from app.models.user import User, UserRole
from tests.conftest import (
    create_test_company,
    create_test_user,
    get_auth_header,
)


# === Helpers ===


async def create_test_product(
    db: AsyncSession,
    name: str = "Traffic Campaign",
    code: str = "traffic",
    base_price: int = 10000,
    category: str = "campaign",
    is_active: bool = True,
    daily_deadline: time = time(18, 0),
) -> Product:
    """Create a test product."""
    product = Product(
        name=name,
        code=code,
        base_price=base_price,
        category=category,
        daily_deadline=daily_deadline,
        is_active=is_active,
    )
    db.add(product)
    await db.flush()
    await db.refresh(product)
    return product


async def _create_draft_order(
    client: AsyncClient, user: User, product_id: int, quantity: int = 1
) -> dict:
    """Helper to create a draft order and return the full response data."""
    headers = get_auth_header(user)
    resp = await client.post(
        "/api/v1/orders/",
        json={"items": [{"product_id": product_id, "quantity": quantity}]},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()


async def _submit_order(client: AsyncClient, user: User, order_id: int) -> dict:
    """Helper to submit an order."""
    headers = get_auth_header(user)
    resp = await client.post(f"/api/v1/orders/{order_id}/submit", headers=headers)
    assert resp.status_code == 200
    return resp.json()


async def _confirm_payment(
    client: AsyncClient, admin: User, order_id: int
) -> dict:
    """Helper to confirm payment."""
    headers = get_auth_header(admin)
    resp = await client.post(
        f"/api/v1/orders/{order_id}/confirm-payment", headers=headers
    )
    return resp.json()


# === Order State Transition Impossible Cases ===


@pytest.mark.asyncio
class TestOrderStateTransitionEdgeCases:
    """Test all invalid state transitions are properly rejected."""

    async def test_completed_cannot_transition_to_any_state(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        company_admin: User,
        product: Product,
    ):
        """A completed order should not allow any state transitions."""
        from app.services import balance_service

        await balance_service.deposit(db_session, distributor.id, 1000000, "Init")
        await db_session.commit()

        data = await _create_draft_order(client, distributor, product.id)
        order_id = data["id"]

        await _submit_order(client, distributor, order_id)

        admin_headers = get_auth_header(company_admin)
        await client.post(
            f"/api/v1/orders/{order_id}/confirm-payment", headers=admin_headers
        )

        # Manually set to completed for testing
        from sqlalchemy import update as sql_update
        await db_session.execute(
            sql_update(Order).where(Order.id == order_id).values(status="completed")
        )
        await db_session.commit()

        # Try to submit - should fail
        dist_headers = get_auth_header(distributor)
        resp = await client.post(
            f"/api/v1/orders/{order_id}/submit", headers=dist_headers
        )
        assert resp.status_code == 400

        # Try to cancel - should fail
        resp = await client.post(
            f"/api/v1/orders/{order_id}/cancel", headers=admin_headers
        )
        assert resp.status_code == 400

        # Try to reject - should fail
        resp = await client.post(
            f"/api/v1/orders/{order_id}/reject",
            json={"reason": "test"},
            headers=admin_headers,
        )
        assert resp.status_code == 400

        # Try to confirm payment again - should fail
        resp = await client.post(
            f"/api/v1/orders/{order_id}/confirm-payment", headers=admin_headers
        )
        assert resp.status_code == 400

    async def test_rejected_cannot_transition(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        company_admin: User,
        product: Product,
    ):
        """A rejected order cannot be submitted, cancelled, or confirmed."""
        await db_session.commit()

        data = await _create_draft_order(client, distributor, product.id)
        order_id = data["id"]

        await _submit_order(client, distributor, order_id)

        admin_headers = get_auth_header(company_admin)
        await client.post(
            f"/api/v1/orders/{order_id}/reject",
            json={"reason": "Bad data"},
            headers=admin_headers,
        )

        # Try submit - should fail
        dist_headers = get_auth_header(distributor)
        resp = await client.post(
            f"/api/v1/orders/{order_id}/submit", headers=dist_headers
        )
        assert resp.status_code == 400

        # Try cancel - should fail
        resp = await client.post(
            f"/api/v1/orders/{order_id}/cancel", headers=admin_headers
        )
        assert resp.status_code == 400

        # Try confirm payment - should fail
        resp = await client.post(
            f"/api/v1/orders/{order_id}/confirm-payment", headers=admin_headers
        )
        assert resp.status_code == 400

    async def test_cancelled_cannot_transition(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        company_admin: User,
        product: Product,
    ):
        """A cancelled order cannot be submitted or confirmed."""
        await db_session.commit()

        data = await _create_draft_order(client, distributor, product.id)
        order_id = data["id"]

        admin_headers = get_auth_header(company_admin)
        await client.post(
            f"/api/v1/orders/{order_id}/cancel", headers=admin_headers
        )

        # Try submit - should fail
        dist_headers = get_auth_header(distributor)
        resp = await client.post(
            f"/api/v1/orders/{order_id}/submit", headers=dist_headers
        )
        assert resp.status_code == 400

        # Try confirm payment - should fail
        resp = await client.post(
            f"/api/v1/orders/{order_id}/confirm-payment", headers=admin_headers
        )
        assert resp.status_code == 400

    async def test_draft_cannot_confirm_payment(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        company_admin: User,
        product: Product,
    ):
        """Cannot confirm payment for a draft order (must be submitted first)."""
        await db_session.commit()

        data = await _create_draft_order(client, distributor, product.id)
        order_id = data["id"]

        admin_headers = get_auth_header(company_admin)
        resp = await client.post(
            f"/api/v1/orders/{order_id}/confirm-payment", headers=admin_headers
        )
        assert resp.status_code == 400

    async def test_payment_confirmed_cannot_submit(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        company_admin: User,
        product: Product,
    ):
        """Cannot submit a payment_confirmed order."""
        from app.services import balance_service

        await balance_service.deposit(db_session, distributor.id, 1000000, "Init")
        await db_session.commit()

        data = await _create_draft_order(client, distributor, product.id)
        order_id = data["id"]

        await _submit_order(client, distributor, order_id)

        admin_headers = get_auth_header(company_admin)
        await client.post(
            f"/api/v1/orders/{order_id}/confirm-payment", headers=admin_headers
        )

        # Try to submit again
        dist_headers = get_auth_header(distributor)
        resp = await client.post(
            f"/api/v1/orders/{order_id}/submit", headers=dist_headers
        )
        assert resp.status_code == 400

    async def test_payment_confirmed_cannot_reject(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        company_admin: User,
        product: Product,
    ):
        """Cannot reject a payment_confirmed order."""
        from app.services import balance_service

        await balance_service.deposit(db_session, distributor.id, 1000000, "Init")
        await db_session.commit()

        data = await _create_draft_order(client, distributor, product.id)
        order_id = data["id"]

        await _submit_order(client, distributor, order_id)

        admin_headers = get_auth_header(company_admin)
        await client.post(
            f"/api/v1/orders/{order_id}/confirm-payment", headers=admin_headers
        )

        resp = await client.post(
            f"/api/v1/orders/{order_id}/reject",
            json={"reason": "Too late"},
            headers=admin_headers,
        )
        assert resp.status_code == 400


# === Balance Edge Cases ===


@pytest.mark.asyncio
class TestBalanceEdgeCases:
    """Test balance-related edge cases."""

    async def test_balance_insufficient_for_order_payment(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        company_admin: User,
        product: Product,
    ):
        """When user has some balance but not enough for the order."""
        from app.services import balance_service

        # Deposit only 5000 but product costs 10000
        await balance_service.deposit(db_session, distributor.id, 5000, "Partial")
        await db_session.commit()

        data = await _create_draft_order(client, distributor, product.id)
        order_id = data["id"]
        await _submit_order(client, distributor, order_id)

        admin_headers = get_auth_header(company_admin)
        resp = await client.post(
            f"/api/v1/orders/{order_id}/confirm-payment", headers=admin_headers
        )
        assert resp.status_code == 400
        assert "Insufficient" in resp.json()["detail"]

        # Verify balance was NOT deducted (transaction should have been rolled back)
        balance_resp = await client.get(
            f"/api/v1/balance/{distributor.id}", headers=admin_headers
        )
        assert balance_resp.json()["balance"] == 5000

    async def test_zero_amount_deposit(
        self,
        client: AsyncClient,
        system_admin: User,
        distributor: User,
    ):
        """Depositing zero amount should fail."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/balance/deposit",
            json={"user_id": str(distributor.id), "amount": 0},
            headers=headers,
        )
        assert resp.status_code == 422  # Pydantic validation: gt=0

    async def test_negative_amount_deposit(
        self,
        client: AsyncClient,
        system_admin: User,
        distributor: User,
    ):
        """Depositing negative amount should fail."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/balance/deposit",
            json={"user_id": str(distributor.id), "amount": -1000},
            headers=headers,
        )
        assert resp.status_code == 422  # Pydantic validation: gt=0

    async def test_zero_amount_withdrawal(
        self,
        client: AsyncClient,
        system_admin: User,
        distributor: User,
    ):
        """Withdrawing zero amount should fail."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/balance/withdraw",
            json={"user_id": str(distributor.id), "amount": 0},
            headers=headers,
        )
        assert resp.status_code == 422

    async def test_withdraw_exact_balance(
        self,
        client: AsyncClient,
        system_admin: User,
        distributor: User,
    ):
        """Withdrawing exactly the available balance should succeed."""
        headers = get_auth_header(system_admin)
        await client.post(
            "/api/v1/balance/deposit",
            json={"user_id": str(distributor.id), "amount": 10000},
            headers=headers,
        )

        resp = await client.post(
            "/api/v1/balance/withdraw",
            json={"user_id": str(distributor.id), "amount": 10000},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["balance_after"] == 0

    async def test_company_admin_cannot_deposit_to_other_company(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        company_admin: User,
        test_company_2: Company,
    ):
        """company_admin cannot deposit to users in another company."""
        other_user = await create_test_user(
            db_session,
            email="other@j2lab.com",
            role=UserRole.DISTRIBUTOR,
            company_id=test_company_2.id,
        )
        await db_session.commit()

        headers = get_auth_header(company_admin)
        resp = await client.post(
            "/api/v1/balance/deposit",
            json={"user_id": str(other_user.id), "amount": 10000},
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_company_admin_cannot_withdraw_from_other_company(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        company_admin: User,
        test_company_2: Company,
    ):
        """company_admin cannot withdraw from users in another company."""
        other_user = await create_test_user(
            db_session,
            email="other@j2lab.com",
            role=UserRole.DISTRIBUTOR,
            company_id=test_company_2.id,
        )
        await db_session.commit()

        headers = get_auth_header(company_admin)
        resp = await client.post(
            "/api/v1/balance/withdraw",
            json={"user_id": str(other_user.id), "amount": 10000},
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_company_admin_cannot_view_other_company_balance(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        company_admin: User,
        test_company_2: Company,
    ):
        """company_admin cannot view balance of users in another company."""
        other_user = await create_test_user(
            db_session,
            email="other@j2lab.com",
            role=UserRole.DISTRIBUTOR,
            company_id=test_company_2.id,
        )
        await db_session.commit()

        headers = get_auth_header(company_admin)
        resp = await client.get(
            f"/api/v1/balance/{other_user.id}", headers=headers
        )
        assert resp.status_code == 403

    async def test_company_admin_cannot_view_other_company_transactions(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        company_admin: User,
        test_company_2: Company,
    ):
        """company_admin cannot view transaction history of users in another company."""
        other_user = await create_test_user(
            db_session,
            email="other@j2lab.com",
            role=UserRole.DISTRIBUTOR,
            company_id=test_company_2.id,
        )
        await db_session.commit()

        headers = get_auth_header(company_admin)
        resp = await client.get(
            f"/api/v1/balance/{other_user.id}/transactions", headers=headers
        )
        assert resp.status_code == 403

    async def test_order_handler_cannot_deposit(
        self,
        client: AsyncClient,
        order_handler: User,
        distributor: User,
    ):
        """order_handler cannot perform deposits."""
        headers = get_auth_header(order_handler)
        resp = await client.post(
            "/api/v1/balance/deposit",
            json={"user_id": str(distributor.id), "amount": 10000},
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_order_handler_cannot_withdraw(
        self,
        client: AsyncClient,
        order_handler: User,
        distributor: User,
    ):
        """order_handler cannot perform withdrawals."""
        headers = get_auth_header(order_handler)
        resp = await client.post(
            "/api/v1/balance/withdraw",
            json={"user_id": str(distributor.id), "amount": 10000},
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_deposit_to_nonexistent_user(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Depositing to a nonexistent user should fail 404."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/balance/deposit",
            json={"user_id": str(uuid.uuid4()), "amount": 10000},
            headers=headers,
        )
        assert resp.status_code == 404


# === Product Edge Cases ===


@pytest.mark.asyncio
class TestProductEdgeCases:
    """Test product-related edge cases."""

    async def test_order_with_inactive_product(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
    ):
        """Cannot create an order with an inactive product."""
        inactive_product = await create_test_product(
            db_session, name="Inactive", code="inactive", is_active=False
        )
        await db_session.commit()

        headers = get_auth_header(distributor)
        resp = await client.post(
            "/api/v1/orders/",
            json={"items": [{"product_id": inactive_product.id, "quantity": 1}]},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "not active" in resp.json()["detail"]

    async def test_order_with_nonexistent_product(
        self,
        client: AsyncClient,
        distributor: User,
    ):
        """Cannot create an order with a nonexistent product ID."""
        headers = get_auth_header(distributor)
        resp = await client.post(
            "/api/v1/orders/",
            json={"items": [{"product_id": 99999, "quantity": 1}]},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "not found" in resp.json()["detail"]

    async def test_order_with_zero_quantity(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        product: Product,
    ):
        """Cannot create an order with zero quantity."""
        await db_session.commit()

        headers = get_auth_header(distributor)
        resp = await client.post(
            "/api/v1/orders/",
            json={"items": [{"product_id": product.id, "quantity": 0}]},
            headers=headers,
        )
        assert resp.status_code == 422  # Pydantic ge=1 validation

    async def test_order_with_empty_items(
        self,
        client: AsyncClient,
        distributor: User,
    ):
        """Cannot create an order with no items."""
        headers = get_auth_header(distributor)
        resp = await client.post(
            "/api/v1/orders/",
            json={"items": []},
            headers=headers,
        )
        assert resp.status_code == 422  # min_length=1 validation

    async def test_update_product_code_to_existing(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        system_admin: User,
    ):
        """Cannot update product code to an existing code."""
        p1 = await create_test_product(db_session, name="P1", code="p1")
        p2 = await create_test_product(db_session, name="P2", code="p2")
        await db_session.commit()

        headers = get_auth_header(system_admin)
        resp = await client.patch(
            f"/api/v1/products/{p2.id}",
            json={"code": "p1"},
            headers=headers,
        )
        assert resp.status_code == 409

    async def test_create_product_with_form_schema(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Product with form_schema should be stored correctly."""
        headers = get_auth_header(system_admin)
        schema = [
            {
                "name": "place_url",
                "type": "url",
                "label": "Place URL",
                "required": True,
            },
            {
                "name": "campaign_days",
                "type": "number",
                "label": "Campaign Days",
                "default": 30,
            },
        ]
        resp = await client.post(
            "/api/v1/products/",
            json={
                "name": "Schema Product",
                "code": "schema_product",
                "base_price": 5000,
                "form_schema": schema,
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["form_schema"] == schema

    async def test_create_product_without_base_price(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Product without base_price should default to None."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/products/",
            json={"name": "No Price", "code": "no_price"},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["base_price"] is None

    async def test_update_product_not_found(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Updating nonexistent product should return 404."""
        headers = get_auth_header(system_admin)
        resp = await client.patch(
            "/api/v1/products/99999",
            json={"name": "Not Found"},
            headers=headers,
        )
        assert resp.status_code == 404

    async def test_distributor_cannot_create_product(
        self,
        client: AsyncClient,
        distributor: User,
    ):
        """Distributor cannot create products."""
        headers = get_auth_header(distributor)
        resp = await client.post(
            "/api/v1/products/",
            json={"name": "Forbidden", "code": "forbidden"},
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_distributor_cannot_update_product(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
    ):
        """Distributor cannot update products."""
        product = await create_test_product(db_session)
        await db_session.commit()

        headers = get_auth_header(distributor)
        resp = await client.patch(
            f"/api/v1/products/{product.id}",
            json={"name": "Hacked"},
            headers=headers,
        )
        assert resp.status_code == 403


# === Price Policy Priority Tests ===


@pytest.mark.asyncio
class TestPricePolicyPriority:
    """Test price resolution priority: user > role > base."""

    async def test_user_specific_price_takes_priority(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
    ):
        """User-specific price should override role and base price."""
        product = await create_test_product(
            db_session, name="Priority Test", code="priority", base_price=10000
        )

        # Role-specific price
        role_policy = PricePolicy(
            product_id=product.id,
            role="distributor",
            unit_price=8000,
            effective_from=date(2025, 1, 1),
        )
        db_session.add(role_policy)

        # User-specific price (highest priority)
        user_policy = PricePolicy(
            product_id=product.id,
            user_id=distributor.id,
            unit_price=6000,
            effective_from=date(2025, 1, 1),
        )
        db_session.add(user_policy)
        await db_session.commit()

        headers = get_auth_header(distributor)
        resp = await client.post(
            "/api/v1/orders/",
            json={"items": [{"product_id": product.id, "quantity": 1}]},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        # Should use user-specific price of 6000
        assert data["items"][0]["unit_price"] == 6000
        assert data["total_amount"] == 6000

    async def test_role_specific_price_overrides_base(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
    ):
        """Role-specific price should override base price when no user-specific exists."""
        product = await create_test_product(
            db_session, name="Role Test", code="role_test", base_price=10000
        )

        role_policy = PricePolicy(
            product_id=product.id,
            role="distributor",
            unit_price=7500,
            effective_from=date(2025, 1, 1),
        )
        db_session.add(role_policy)
        await db_session.commit()

        headers = get_auth_header(distributor)
        resp = await client.post(
            "/api/v1/orders/",
            json={"items": [{"product_id": product.id, "quantity": 2}]},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["items"][0]["unit_price"] == 7500
        assert data["total_amount"] == 15000

    async def test_base_price_used_when_no_policy(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
    ):
        """Base price should be used when no price policy exists."""
        product = await create_test_product(
            db_session, name="Base Test", code="base_test", base_price=12000
        )
        await db_session.commit()

        headers = get_auth_header(distributor)
        resp = await client.post(
            "/api/v1/orders/",
            json={"items": [{"product_id": product.id, "quantity": 1}]},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["items"][0]["unit_price"] == 12000

    async def test_expired_policy_not_used(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
    ):
        """Expired price policy should not be used."""
        product = await create_test_product(
            db_session, name="Expired Test", code="expired_test", base_price=10000
        )

        expired_policy = PricePolicy(
            product_id=product.id,
            user_id=distributor.id,
            unit_price=5000,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 12, 31),  # Expired
        )
        db_session.add(expired_policy)
        await db_session.commit()

        headers = get_auth_header(distributor)
        resp = await client.post(
            "/api/v1/orders/",
            json={"items": [{"product_id": product.id, "quantity": 1}]},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        # Should use base price since policy is expired
        assert data["items"][0]["unit_price"] == 10000

    async def test_future_policy_not_used(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
    ):
        """Future price policy (not yet effective) should not be used."""
        product = await create_test_product(
            db_session, name="Future Test", code="future_test", base_price=10000
        )

        future_policy = PricePolicy(
            product_id=product.id,
            user_id=distributor.id,
            unit_price=3000,
            effective_from=date(2099, 1, 1),  # Far future
        )
        db_session.add(future_policy)
        await db_session.commit()

        headers = get_auth_header(distributor)
        resp = await client.post(
            "/api/v1/orders/",
            json={"items": [{"product_id": product.id, "quantity": 1}]},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        # Should use base price since policy hasn't started yet
        assert data["items"][0]["unit_price"] == 10000

    async def test_no_base_price_defaults_to_zero(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
    ):
        """If no price policy and no base_price, unit_price should be 0."""
        product = await create_test_product(
            db_session, name="Free Test", code="free_test", base_price=None
        )
        # Override base_price to None after creation
        product.base_price = None
        await db_session.flush()
        await db_session.commit()

        headers = get_auth_header(distributor)
        resp = await client.post(
            "/api/v1/orders/",
            json={"items": [{"product_id": product.id, "quantity": 1}]},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["items"][0]["unit_price"] == 0

    async def test_campaign_type_specific_user_price_is_used(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
    ):
        """User-specific campaign_type price should override generic product price."""
        product = await create_test_product(
            db_session, name="일류 리워드", code="ilryu_reward", base_price=10000
        )

        generic_policy = PricePolicy(
            product_id=product.id,
            user_id=distributor.id,
            unit_price=9000,
            effective_from=date(2025, 1, 1),
        )
        save_policy = PricePolicy(
            product_id=product.id,
            user_id=distributor.id,
            campaign_type="save",
            unit_price=7000,
            effective_from=date(2025, 1, 1),
        )
        db_session.add_all([generic_policy, save_policy])
        await db_session.commit()

        headers = get_auth_header(distributor)
        resp = await client.post(
            "/api/v1/orders/",
            json={
                "items": [
                    {
                        "product_id": product.id,
                        "quantity": 1,
                        "item_data": {"campaign_type": "save"},
                    }
                ]
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["items"][0]["unit_price"] == 7000
        assert data["total_amount"] == 7000


# === System Settings Edge Cases ===


@pytest.mark.asyncio
class TestSystemSettingsEdgeCases:
    """Test system settings with various JSON types."""

    async def test_setting_string_value(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Store a string setting value."""
        headers = get_auth_header(system_admin)
        resp = await client.put(
            "/api/v1/settings/string_setting",
            json={"value": "hello world"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == "hello world"

    async def test_setting_integer_value(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Store an integer setting value."""
        headers = get_auth_header(system_admin)
        resp = await client.put(
            "/api/v1/settings/int_setting",
            json={"value": 42},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == 42

    async def test_setting_float_value(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Store a float setting value."""
        headers = get_auth_header(system_admin)
        resp = await client.put(
            "/api/v1/settings/float_setting",
            json={"value": 3.14},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == 3.14

    async def test_setting_boolean_value(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Store a boolean setting value."""
        headers = get_auth_header(system_admin)
        resp = await client.put(
            "/api/v1/settings/bool_setting",
            json={"value": True},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["value"] is True

    async def test_setting_null_value(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Store a null setting value."""
        headers = get_auth_header(system_admin)
        resp = await client.put(
            "/api/v1/settings/null_setting",
            json={"value": None},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["value"] is None

    async def test_setting_array_value(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Store an array setting value."""
        headers = get_auth_header(system_admin)
        resp = await client.put(
            "/api/v1/settings/array_setting",
            json={"value": [1, "two", 3.0, True, None]},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == [1, "two", 3.0, True, None]

    async def test_setting_nested_object_value(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Store a nested object setting value."""
        headers = get_auth_header(system_admin)
        nested = {
            "level1": {
                "level2": {"key": "value"},
                "array": [1, 2, 3],
            }
        }
        resp = await client.put(
            "/api/v1/settings/nested_setting",
            json={"value": nested},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == nested

    async def test_setting_upsert_overwrites_value(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Upserting should replace the old value."""
        headers = get_auth_header(system_admin)

        # Create
        await client.put(
            "/api/v1/settings/overwrite_test",
            json={"value": "old_value", "description": "Old desc"},
            headers=headers,
        )

        # Update
        resp = await client.put(
            "/api/v1/settings/overwrite_test",
            json={"value": "new_value", "description": "New desc"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["value"] == "new_value"
        assert data["description"] == "New desc"

    async def test_distributor_cannot_access_settings(
        self,
        client: AsyncClient,
        distributor: User,
    ):
        """Distributor cannot access system settings endpoints."""
        headers = get_auth_header(distributor)

        resp = await client.get("/api/v1/settings/", headers=headers)
        assert resp.status_code == 403

        resp = await client.get("/api/v1/settings/any_key", headers=headers)
        assert resp.status_code == 403

        resp = await client.put(
            "/api/v1/settings/any_key",
            json={"value": "hack"},
            headers=headers,
        )
        assert resp.status_code == 403

        resp = await client.delete("/api/v1/settings/any_key", headers=headers)
        assert resp.status_code == 403


# === Order Permission / Cross-Company Edge Cases ===


@pytest.mark.asyncio
class TestOrderCrossCompanyEdgeCases:
    """Test cross-company order access restrictions."""

    async def test_company_admin_cannot_confirm_other_company_order(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
        test_company_2: Company,
    ):
        """company_admin from company A cannot confirm payment for company B's order."""
        dist_b = await create_test_user(
            db_session,
            email="dist@j2lab.com",
            role=UserRole.DISTRIBUTOR,
            company_id=test_company_2.id,
        )
        admin_a = await create_test_user(
            db_session,
            email="cadmin@ilryu.com",
            role=UserRole.COMPANY_ADMIN,
            company_id=test_company.id,
        )

        product = await create_test_product(db_session)
        await db_session.commit()

        # Create order in company B
        data = await _create_draft_order(client, dist_b, product.id)
        order_id = data["id"]
        await _submit_order(client, dist_b, order_id)

        # company_admin from company A tries to confirm
        admin_a_headers = get_auth_header(admin_a)
        resp = await client.post(
            f"/api/v1/orders/{order_id}/confirm-payment",
            headers=admin_a_headers,
        )
        assert resp.status_code == 403

    async def test_company_admin_cannot_reject_other_company_order(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
        test_company_2: Company,
    ):
        """company_admin from company A cannot reject company B's order."""
        dist_b = await create_test_user(
            db_session,
            email="dist@j2lab.com",
            role=UserRole.DISTRIBUTOR,
            company_id=test_company_2.id,
        )
        admin_a = await create_test_user(
            db_session,
            email="cadmin@ilryu.com",
            role=UserRole.COMPANY_ADMIN,
            company_id=test_company.id,
        )

        product = await create_test_product(db_session)
        await db_session.commit()

        # Create order in company B
        data = await _create_draft_order(client, dist_b, product.id)
        order_id = data["id"]
        await _submit_order(client, dist_b, order_id)

        # company_admin from company A tries to reject
        admin_a_headers = get_auth_header(admin_a)
        resp = await client.post(
            f"/api/v1/orders/{order_id}/reject",
            json={"reason": "Not my company"},
            headers=admin_a_headers,
        )
        assert resp.status_code == 403

    async def test_distributor_cannot_submit_other_distributor_order(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """Distributor A cannot submit Distributor B's order."""
        dist_a = await create_test_user(
            db_session,
            email="dist_a@ilryu.com",
            role=UserRole.DISTRIBUTOR,
            company_id=test_company.id,
        )
        dist_b = await create_test_user(
            db_session,
            email="dist_b@ilryu.com",
            role=UserRole.DISTRIBUTOR,
            company_id=test_company.id,
        )

        product = await create_test_product(db_session)
        await db_session.commit()

        # dist_a creates order
        data = await _create_draft_order(client, dist_a, product.id)
        order_id = data["id"]

        # dist_b tries to submit dist_a's order
        headers_b = get_auth_header(dist_b)
        resp = await client.post(
            f"/api/v1/orders/{order_id}/submit", headers=headers_b
        )
        assert resp.status_code == 403

    async def test_sub_account_can_submit_own_order(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        sub_account: User,
        product: Product,
    ):
        """sub_account can submit their own order into the distributor queue."""
        await db_session.commit()

        data = await _create_draft_order(client, sub_account, product.id)
        order_id = data["id"]

        headers = get_auth_header(sub_account)
        resp = await client.post(
            f"/api/v1/orders/{order_id}/submit", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "submitted"
        assert resp.json()["selection_status"] == "pending"

    async def test_distributor_list_hides_sub_account_queue_orders(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        sub_account: User,
        product: Product,
    ):
        """Submitted sub_account orders stay in queue, not in distributor general list."""
        await db_session.commit()

        data = await _create_draft_order(client, sub_account, product.id)
        order_id = data["id"]

        sub_headers = get_auth_header(sub_account)
        submit_resp = await client.post(
            f"/api/v1/orders/{order_id}/submit", headers=sub_headers
        )
        assert submit_resp.status_code == 200

        dist_headers = get_auth_header(distributor)
        list_resp = await client.get(
            "/api/v1/orders/?status=submitted",
            headers=dist_headers,
        )
        assert list_resp.status_code == 200
        assert all(item["id"] != order_id for item in list_resp.json()["items"])

        queue_resp = await client.get(
            "/api/v1/orders/sub-account-pending",
            headers=dist_headers,
        )
        assert queue_resp.status_code == 200
        assert any(item["id"] == order_id for item in queue_resp.json()["items"])

    async def test_included_sub_account_order_stays_in_queue_until_finalized(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        sub_account: User,
        product: Product,
    ):
        """Included sub_account orders remain in the queue until distributor final confirmation."""
        await db_session.commit()

        data = await _create_draft_order(client, sub_account, product.id)
        order_id = data["id"]

        sub_headers = get_auth_header(sub_account)
        submit_resp = await client.post(
            f"/api/v1/orders/{order_id}/submit", headers=sub_headers
        )
        assert submit_resp.status_code == 200

        dist_headers = get_auth_header(distributor)
        include_resp = await client.post(
            f"/api/v1/orders/{order_id}/include",
            headers=dist_headers,
        )
        assert include_resp.status_code == 200

        queue_resp = await client.get(
            "/api/v1/orders/sub-account-pending",
            headers=dist_headers,
        )
        assert queue_resp.status_code == 200
        included_item = next((item for item in queue_resp.json()["items"] if item["id"] == order_id), None)
        assert included_item is not None
        assert included_item["selection_status"] == "included"

    async def test_distributor_can_view_sub_account_order(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        sub_account: User,
        product: Product,
    ):
        """Distributor can view their sub_account's order."""
        await db_session.commit()

        data = await _create_draft_order(client, sub_account, product.id)
        order_id = data["id"]

        headers = get_auth_header(distributor)
        resp = await client.get(f"/api/v1/orders/{order_id}", headers=headers)
        assert resp.status_code == 200

    async def test_order_handler_can_list_same_company_orders(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        order_handler: User,
        distributor: User,
        product: Product,
    ):
        """order_handler can list orders in their company."""
        await db_session.commit()

        await _create_draft_order(client, distributor, product.id)

        headers = get_auth_header(order_handler)
        resp = await client.get("/api/v1/orders/", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1


# === Order Update Edge Cases ===


@pytest.mark.asyncio
class TestOrderUpdateEdgeCases:
    """Test order update restrictions."""

    async def test_cannot_update_submitted_order(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        company_admin: User,
        product: Product,
    ):
        """Cannot update notes on a submitted order."""
        await db_session.commit()

        data = await _create_draft_order(client, distributor, product.id)
        order_id = data["id"]
        await _submit_order(client, distributor, order_id)

        admin_headers = get_auth_header(company_admin)
        resp = await client.patch(
            f"/api/v1/orders/{order_id}",
            json={"notes": "Updated notes"},
            headers=admin_headers,
        )
        assert resp.status_code == 400
        assert "draft" in resp.json()["detail"].lower()

    async def test_update_nonexistent_order(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Updating a nonexistent order should return 404."""
        headers = get_auth_header(system_admin)
        resp = await client.patch(
            "/api/v1/orders/99999",
            json={"notes": "Not found"},
            headers=headers,
        )
        assert resp.status_code == 404


# === Price Policy Edge Cases ===


@pytest.mark.asyncio
class TestPricePolicyEdgeCases:
    """Test price policy CRUD edge cases."""

    async def test_create_policy_product_id_mismatch(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        system_admin: User,
    ):
        """Body product_id must match URL product_id."""
        product = await create_test_product(db_session, name="P1", code="pp1")
        product2 = await create_test_product(db_session, name="P2", code="pp2")
        await db_session.commit()

        headers = get_auth_header(system_admin)
        resp = await client.post(
            f"/api/v1/products/{product.id}/prices",
            json={
                "product_id": product2.id,  # Mismatch!
                "unit_price": 5000,
                "effective_from": "2026-01-01",
            },
            headers=headers,
        )
        assert resp.status_code == 400
        assert "match" in resp.json()["detail"].lower()

    async def test_create_policy_for_nonexistent_product(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Creating price policy for nonexistent product should fail."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/products/99999/prices",
            json={
                "product_id": 99999,
                "unit_price": 5000,
                "effective_from": "2026-01-01",
            },
            headers=headers,
        )
        assert resp.status_code == 404

    async def test_delete_nonexistent_policy(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Deleting a nonexistent price policy should fail."""
        headers = get_auth_header(system_admin)
        resp = await client.delete(
            "/api/v1/products/prices/99999",
            headers=headers,
        )
        assert resp.status_code == 404

    async def test_distributor_cannot_create_price_policy(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
    ):
        """Distributor cannot create price policies."""
        product = await create_test_product(db_session)
        await db_session.commit()

        headers = get_auth_header(distributor)
        resp = await client.post(
            f"/api/v1/products/{product.id}/prices",
            json={
                "product_id": product.id,
                "unit_price": 100,
                "effective_from": "2026-01-01",
            },
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_distributor_cannot_list_price_policies(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
    ):
        """Distributor cannot list price policies."""
        product = await create_test_product(db_session)
        await db_session.commit()

        headers = get_auth_header(distributor)
        resp = await client.get(
            f"/api/v1/products/{product.id}/prices",
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_distributor_cannot_delete_price_policy(
        self,
        client: AsyncClient,
        distributor: User,
    ):
        """Distributor cannot delete price policies."""
        headers = get_auth_header(distributor)
        resp = await client.delete(
            "/api/v1/products/prices/1",
            headers=headers,
        )
        assert resp.status_code == 403


# === Order with item_data ===


@pytest.mark.asyncio
class TestOrderItemData:
    """Test order items with dynamic form data (item_data)."""

    async def test_order_with_item_data(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        product: Product,
    ):
        """Order items can include item_data JSON."""
        await db_session.commit()

        item_data = {
            "place_url": "https://map.naver.com/p/entry/place/1234567890",
            "start_date": "2026-03-01",
            "end_date": "2026-03-31",
            "daily_limit": 300,
            "campaign_type": "traffic",
        }

        headers = get_auth_header(distributor)
        resp = await client.post(
            "/api/v1/orders/",
            json={
                "items": [
                    {
                        "product_id": product.id,
                        "quantity": 1,
                        "item_data": item_data,
                    },
                ],
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["items"][0]["item_data"] == item_data


# === Full Lifecycle Test ===


@pytest.mark.asyncio
class TestFullOrderLifecycle:
    """Test the complete order lifecycle with balance verification."""

    async def test_full_lifecycle_draft_to_payment_confirmed(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        company_admin: User,
        product: Product,
    ):
        """Full lifecycle: draft -> submitted -> payment_confirmed with balance check."""
        from app.services import balance_service

        # Setup: deposit enough balance
        await balance_service.deposit(db_session, distributor.id, 100000, "Initial")
        await db_session.commit()

        # 1. Create draft order
        data = await _create_draft_order(client, distributor, product.id, quantity=3)
        order_id = data["id"]
        assert data["status"] == "draft"
        assert data["total_amount"] == 30000  # 10000 * 3
        assert data["vat_amount"] == 3000

        # 2. Submit order
        submit_data = await _submit_order(client, distributor, order_id)
        assert submit_data["status"] == "submitted"
        assert submit_data["submitted_by"] == str(distributor.id)

        # 3. Confirm payment
        admin_headers = get_auth_header(company_admin)
        resp = await client.post(
            f"/api/v1/orders/{order_id}/confirm-payment", headers=admin_headers
        )
        assert resp.status_code == 200
        confirm_data = resp.json()
        # After confirm_payment, pipeline auto-starts → order transitions to processing
        assert confirm_data["status"] == "processing"
        assert confirm_data["payment_status"] == "confirmed"

        # 4. Verify balance
        balance_resp = await client.get(
            f"/api/v1/balance/{distributor.id}", headers=admin_headers
        )
        assert balance_resp.json()["balance"] == 70000  # 100000 - 30000

        # 5. Verify transaction history
        tx_resp = await client.get(
            f"/api/v1/balance/{distributor.id}/transactions", headers=admin_headers
        )
        tx_data = tx_resp.json()
        assert tx_data["total"] == 2  # deposit + order_charge
        tx_types = {item["transaction_type"] for item in tx_data["items"]}
        assert "deposit" in tx_types
        assert "order_charge" in tx_types


# === Fixtures ===


@pytest_asyncio.fixture
async def product(db_session: AsyncSession) -> Product:
    """Create a default test product."""
    return await create_test_product(db_session)

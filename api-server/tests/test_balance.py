"""Tests for balance endpoints: deposit, withdraw, transaction history."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.user import User, UserRole
from tests.conftest import (
    create_test_company,
    create_test_user,
    get_auth_header,
)


@pytest.mark.asyncio
class TestGetBalance:
    """Tests for GET /api/v1/balance/{user_id}."""

    async def test_get_own_balance(
        self,
        client: AsyncClient,
        distributor: User,
    ):
        """User can view their own balance."""
        headers = get_auth_header(distributor)
        resp = await client.get(
            f"/api/v1/balance/{distributor.id}", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == str(distributor.id)
        assert data["balance"] == 0

    async def test_company_admin_views_user_balance(
        self,
        client: AsyncClient,
        company_admin: User,
        distributor: User,
    ):
        """company_admin can view balance of users in their company."""
        headers = get_auth_header(company_admin)
        resp = await client.get(
            f"/api/v1/balance/{distributor.id}", headers=headers
        )
        assert resp.status_code == 200

    async def test_sub_account_cannot_view_others_balance(
        self,
        client: AsyncClient,
        sub_account: User,
        distributor: User,
    ):
        """sub_account cannot view another user's balance."""
        headers = get_auth_header(sub_account)
        resp = await client.get(
            f"/api/v1/balance/{distributor.id}", headers=headers
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestDeposit:
    """Tests for POST /api/v1/balance/deposit."""

    async def test_deposit_success(
        self,
        client: AsyncClient,
        system_admin: User,
        distributor: User,
    ):
        """system_admin can deposit balance."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/balance/deposit",
            json={
                "user_id": str(distributor.id),
                "amount": 50000,
                "description": "Initial charge",
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["amount"] == 50000
        assert data["balance_after"] == 50000
        assert data["transaction_type"] == "deposit"

        # Verify balance updated
        resp2 = await client.get(
            f"/api/v1/balance/{distributor.id}", headers=headers
        )
        assert resp2.json()["balance"] == 50000

    async def test_deposit_multiple(
        self,
        client: AsyncClient,
        system_admin: User,
        distributor: User,
    ):
        """Multiple deposits should accumulate."""
        headers = get_auth_header(system_admin)
        await client.post(
            "/api/v1/balance/deposit",
            json={"user_id": str(distributor.id), "amount": 10000},
            headers=headers,
        )
        resp = await client.post(
            "/api/v1/balance/deposit",
            json={"user_id": str(distributor.id), "amount": 20000},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["balance_after"] == 30000

    async def test_deposit_non_admin_forbidden(
        self,
        client: AsyncClient,
        distributor: User,
    ):
        """Distributor cannot deposit."""
        headers = get_auth_header(distributor)
        resp = await client.post(
            "/api/v1/balance/deposit",
            json={"user_id": str(distributor.id), "amount": 10000},
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_deposit_invalid_user(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Deposit to nonexistent user should fail."""
        import uuid

        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/balance/deposit",
            json={"user_id": str(uuid.uuid4()), "amount": 10000},
            headers=headers,
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestWithdraw:
    """Tests for POST /api/v1/balance/withdraw."""

    async def test_withdraw_success(
        self,
        client: AsyncClient,
        system_admin: User,
        distributor: User,
    ):
        """Withdraw from a user with sufficient balance."""
        headers = get_auth_header(system_admin)
        # First deposit
        await client.post(
            "/api/v1/balance/deposit",
            json={"user_id": str(distributor.id), "amount": 50000},
            headers=headers,
        )

        # Then withdraw
        resp = await client.post(
            "/api/v1/balance/withdraw",
            json={
                "user_id": str(distributor.id),
                "amount": 20000,
                "description": "Withdrawal test",
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["amount"] == -20000  # Negative for withdrawal
        assert data["balance_after"] == 30000
        assert data["transaction_type"] == "withdrawal"

    async def test_withdraw_insufficient_balance(
        self,
        client: AsyncClient,
        system_admin: User,
        distributor: User,
    ):
        """Withdraw more than available balance should fail."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/balance/withdraw",
            json={"user_id": str(distributor.id), "amount": 10000},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "Insufficient" in resp.json()["detail"]


@pytest.mark.asyncio
class TestTransactionHistory:
    """Tests for GET /api/v1/balance/{user_id}/transactions."""

    async def test_list_transactions(
        self,
        client: AsyncClient,
        system_admin: User,
        distributor: User,
    ):
        """Transaction history should include all transactions."""
        headers = get_auth_header(system_admin)

        # Create some transactions
        await client.post(
            "/api/v1/balance/deposit",
            json={"user_id": str(distributor.id), "amount": 50000},
            headers=headers,
        )
        await client.post(
            "/api/v1/balance/withdraw",
            json={"user_id": str(distributor.id), "amount": 10000},
            headers=headers,
        )

        resp = await client.get(
            f"/api/v1/balance/{distributor.id}/transactions", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        # Check both transaction types are present
        tx_types = {item["transaction_type"] for item in data["items"]}
        assert "deposit" in tx_types
        assert "withdrawal" in tx_types

    async def test_transaction_pagination(
        self,
        client: AsyncClient,
        system_admin: User,
        distributor: User,
    ):
        """Transaction history should support pagination."""
        headers = get_auth_header(system_admin)

        # Create 3 transactions
        for i in range(3):
            await client.post(
                "/api/v1/balance/deposit",
                json={
                    "user_id": str(distributor.id),
                    "amount": (i + 1) * 1000,
                },
                headers=headers,
            )

        resp = await client.get(
            f"/api/v1/balance/{distributor.id}/transactions?page=1&size=2",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["pages"] == 2

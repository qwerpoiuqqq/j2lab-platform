"""Tests for products endpoints: CRUD operations + price policies."""

from __future__ import annotations

from datetime import date, time

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
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
    category: str = "campaign",
    is_active: bool = True,
) -> Product:
    """Create a test product."""
    product = Product(
        name=name,
        code=code,
        base_price=base_price,
        category=category,
        daily_deadline=time(18, 0),
        is_active=is_active,
    )
    db.add(product)
    await db.flush()
    await db.refresh(product)
    return product


@pytest.mark.asyncio
class TestListProducts:
    """Tests for GET /api/v1/products."""

    async def test_list_products_as_any_user(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """Any authenticated user can list products."""
        user = await create_test_user(
            db_session,
            email="user@test.com",
            role=UserRole.SUB_ACCOUNT,
            company_id=test_company.id,
        )
        await create_test_product(db_session, name="P1", code="p1")
        await create_test_product(db_session, name="P2", code="p2")
        await db_session.commit()

        headers = get_auth_header(user)
        resp = await client.get("/api/v1/products/", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_list_products_filter_active(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        system_admin: User,
    ):
        """Filter products by is_active."""
        await create_test_product(db_session, name="Active", code="active")
        await create_test_product(
            db_session, name="Inactive", code="inactive", is_active=False
        )
        await db_session.commit()

        headers = get_auth_header(system_admin)
        resp = await client.get(
            "/api/v1/products/?is_active=true", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Active"

    async def test_list_products_unauthenticated(self, client: AsyncClient):
        """Unauthenticated access should return 401/403."""
        resp = await client.get("/api/v1/products/")
        assert resp.status_code in (401, 403)


@pytest.mark.asyncio
class TestCreateProduct:
    """Tests for POST /api/v1/products."""

    async def test_create_product_success(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """system_admin can create a product."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/products/",
            json={
                "name": "Traffic Campaign",
                "code": "traffic",
                "base_price": 10000,
                "category": "campaign",
                "daily_deadline": "18:00:00",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Traffic Campaign"
        assert data["code"] == "traffic"
        assert data["base_price"] == 10000
        assert data["is_active"] is True

    async def test_create_product_duplicate_code(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        system_admin: User,
    ):
        """Duplicate code should return 409."""
        await create_test_product(db_session)
        await db_session.commit()

        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/products/",
            json={"name": "Another", "code": "traffic", "base_price": 5000},
            headers=headers,
        )
        assert resp.status_code == 409

    async def test_create_product_non_admin(
        self,
        client: AsyncClient,
        company_admin: User,
    ):
        """Non-system_admin cannot create products."""
        headers = get_auth_header(company_admin)
        resp = await client.post(
            "/api/v1/products/",
            json={"name": "Forbidden", "code": "forbidden", "base_price": 1000},
            headers=headers,
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestGetProduct:
    """Tests for GET /api/v1/products/{id}."""

    async def test_get_product_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        system_admin: User,
    ):
        """Get a product by ID."""
        product = await create_test_product(db_session)
        await db_session.commit()

        headers = get_auth_header(system_admin)
        resp = await client.get(
            f"/api/v1/products/{product.id}", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == product.id
        assert data["name"] == "Traffic Campaign"

    async def test_get_product_not_found(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Nonexistent product should return 404."""
        headers = get_auth_header(system_admin)
        resp = await client.get("/api/v1/products/9999", headers=headers)
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestUpdateProduct:
    """Tests for PATCH /api/v1/products/{id}."""

    async def test_update_product_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        system_admin: User,
    ):
        """system_admin can update a product."""
        product = await create_test_product(db_session)
        await db_session.commit()

        headers = get_auth_header(system_admin)
        resp = await client.patch(
            f"/api/v1/products/{product.id}",
            json={"name": "Updated Name", "base_price": 20000},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Name"
        assert data["base_price"] == 20000
        assert data["code"] == "traffic"  # unchanged


@pytest.mark.asyncio
class TestPricePolicies:
    """Tests for price policies under products."""

    async def test_create_price_policy(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        system_admin: User,
    ):
        """Create a role-based price policy."""
        product = await create_test_product(db_session)
        await db_session.commit()

        headers = get_auth_header(system_admin)
        resp = await client.post(
            f"/api/v1/products/{product.id}/prices",
            json={
                "product_id": product.id,
                "role": "distributor",
                "unit_price": 8000,
                "effective_from": "2026-01-01",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["unit_price"] == 8000
        assert data["role"] == "distributor"

    async def test_list_price_policies(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        system_admin: User,
    ):
        """List price policies for a product."""
        product = await create_test_product(db_session)

        from app.models.price_policy import PricePolicy

        policy = PricePolicy(
            product_id=product.id,
            role="distributor",
            unit_price=8000,
            effective_from=date(2026, 1, 1),
        )
        db_session.add(policy)
        await db_session.commit()

        headers = get_auth_header(system_admin)
        resp = await client.get(
            f"/api/v1/products/{product.id}/prices", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["unit_price"] == 8000

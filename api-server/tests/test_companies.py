"""Tests for companies endpoints: CRUD operations."""

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
class TestListCompanies:
    """Tests for GET /api/v1/companies."""

    async def test_list_companies_as_system_admin(
        self,
        client: AsyncClient,
        system_admin: User,
        test_company: Company,
        test_company_2: Company,
    ):
        """system_admin can see all companies."""
        headers = get_auth_header(system_admin)
        resp = await client.get("/api/v1/companies/", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_list_companies_pagination(
        self,
        client: AsyncClient,
        system_admin: User,
        test_company: Company,
        test_company_2: Company,
    ):
        """Pagination should work correctly."""
        headers = get_auth_header(system_admin)
        resp = await client.get(
            "/api/v1/companies/?page=1&size=1", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 1
        assert data["pages"] == 2

    async def test_list_companies_as_company_admin_forbidden(
        self,
        client: AsyncClient,
        company_admin: User,
    ):
        """company_admin cannot access companies list."""
        headers = get_auth_header(company_admin)
        resp = await client.get("/api/v1/companies/", headers=headers)
        assert resp.status_code == 403

    async def test_list_companies_unauthenticated(
        self, client: AsyncClient
    ):
        """Unauthenticated access should return 401."""
        resp = await client.get("/api/v1/companies/")
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestCreateCompany:
    """Tests for POST /api/v1/companies."""

    async def test_create_company_success(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """system_admin can create a company."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/companies/",
            json={"name": "New Corp", "code": "newcorp"},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "New Corp"
        assert data["code"] == "newcorp"
        assert data["is_active"] is True

    async def test_create_company_duplicate_code(
        self,
        client: AsyncClient,
        system_admin: User,
        test_company: Company,
    ):
        """Duplicate code should return 409."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/companies/",
            json={"name": "Another", "code": test_company.code},
            headers=headers,
        )
        assert resp.status_code == 409

    async def test_create_company_non_admin(
        self,
        client: AsyncClient,
        company_admin: User,
    ):
        """Non-system_admin cannot create companies."""
        headers = get_auth_header(company_admin)
        resp = await client.post(
            "/api/v1/companies/",
            json={"name": "Forbidden Corp", "code": "forbidden"},
            headers=headers,
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestGetCompany:
    """Tests for GET /api/v1/companies/{id}."""

    async def test_get_company_success(
        self,
        client: AsyncClient,
        system_admin: User,
        test_company: Company,
    ):
        """system_admin can get a company by ID."""
        headers = get_auth_header(system_admin)
        resp = await client.get(
            f"/api/v1/companies/{test_company.id}", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == test_company.id
        assert data["name"] == test_company.name

    async def test_get_company_not_found(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Nonexistent company ID should return 404."""
        headers = get_auth_header(system_admin)
        resp = await client.get("/api/v1/companies/9999", headers=headers)
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestUpdateCompany:
    """Tests for PATCH /api/v1/companies/{id}."""

    async def test_update_company_success(
        self,
        client: AsyncClient,
        system_admin: User,
        test_company: Company,
    ):
        """system_admin can update a company."""
        headers = get_auth_header(system_admin)
        resp = await client.patch(
            f"/api/v1/companies/{test_company.id}",
            json={"name": "Updated Name"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Name"
        assert data["code"] == test_company.code  # unchanged

    async def test_update_company_duplicate_code(
        self,
        client: AsyncClient,
        system_admin: User,
        test_company: Company,
        test_company_2: Company,
    ):
        """Updating to a duplicate code should return 409."""
        headers = get_auth_header(system_admin)
        resp = await client.patch(
            f"/api/v1/companies/{test_company.id}",
            json={"code": test_company_2.code},
            headers=headers,
        )
        assert resp.status_code == 409


@pytest.mark.asyncio
class TestDeleteCompany:
    """Tests for DELETE /api/v1/companies/{id}."""

    async def test_delete_company_success(
        self,
        client: AsyncClient,
        system_admin: User,
        test_company: Company,
    ):
        """system_admin can soft-delete a company."""
        headers = get_auth_header(system_admin)
        resp = await client.delete(
            f"/api/v1/companies/{test_company.id}", headers=headers
        )
        assert resp.status_code == 200

        # Verify it's deactivated
        resp = await client.get(
            f"/api/v1/companies/{test_company.id}", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    async def test_delete_company_not_found(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Deleting nonexistent company should return 404."""
        headers = get_auth_header(system_admin)
        resp = await client.delete(
            "/api/v1/companies/9999", headers=headers
        )
        assert resp.status_code == 404

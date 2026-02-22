"""Tests for auth endpoints: login, refresh, logout, register."""

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
class TestLogin:
    """Tests for POST /api/v1/auth/login."""

    async def test_login_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """Valid email + password should return tokens."""
        user = await create_test_user(
            db_session,
            email="login@test.com",
            password="correctpassword",
            role=UserRole.COMPANY_ADMIN,
            company_id=test_company.id,
        )

        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "login@test.com", "password": "correctpassword"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """Wrong password should return 401."""
        await create_test_user(
            db_session,
            email="wrongpw@test.com",
            password="correctpassword",
            role=UserRole.COMPANY_ADMIN,
            company_id=test_company.id,
        )

        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "wrongpw@test.com", "password": "wrongpassword"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_email(self, client: AsyncClient):
        """Nonexistent email should return 401."""
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@test.com", "password": "whatever"},
        )
        assert resp.status_code == 401

    async def test_login_inactive_user(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """Inactive user should return 401."""
        await create_test_user(
            db_session,
            email="inactive@test.com",
            password="password123",
            role=UserRole.COMPANY_ADMIN,
            company_id=test_company.id,
            is_active=False,
        )

        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "inactive@test.com", "password": "password123"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestRefresh:
    """Tests for POST /api/v1/auth/refresh."""

    async def test_refresh_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """Valid refresh token should return new token pair."""
        await create_test_user(
            db_session,
            email="refresh@test.com",
            password="password123",
            role=UserRole.COMPANY_ADMIN,
            company_id=test_company.id,
        )

        # Login first
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "refresh@test.com", "password": "password123"},
        )
        refresh_token = login_resp.json()["refresh_token"]

        # Refresh
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        # New refresh token should be different
        assert data["refresh_token"] != refresh_token

    async def test_refresh_invalid_token(self, client: AsyncClient):
        """Invalid refresh token should return 401."""
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )
        assert resp.status_code == 401

    async def test_refresh_revoked_token(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """Revoked (used) refresh token should return 401."""
        await create_test_user(
            db_session,
            email="revoked@test.com",
            password="password123",
            role=UserRole.COMPANY_ADMIN,
            company_id=test_company.id,
        )

        # Login
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "revoked@test.com", "password": "password123"},
        )
        refresh_token = login_resp.json()["refresh_token"]

        # Use refresh once (this revokes the old token)
        await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        # Try to use the same token again
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestLogout:
    """Tests for POST /api/v1/auth/logout."""

    async def test_logout_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """Valid refresh token should be revoked on logout."""
        await create_test_user(
            db_session,
            email="logout@test.com",
            password="password123",
            role=UserRole.COMPANY_ADMIN,
            company_id=test_company.id,
        )

        # Login
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "logout@test.com", "password": "password123"},
        )
        refresh_token = login_resp.json()["refresh_token"]

        # Logout
        resp = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200

        # Verify token is revoked (cannot refresh anymore)
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 401

    async def test_logout_invalid_token(self, client: AsyncClient):
        """Invalid refresh token should return 400."""
        resp = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": "invalid-token"},
        )
        assert resp.status_code == 400


@pytest.mark.asyncio
class TestRegister:
    """Tests for POST /api/v1/auth/register."""

    async def test_register_by_system_admin(
        self,
        client: AsyncClient,
        system_admin: User,
        test_company: Company,
    ):
        """system_admin can register any role user."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@test.com",
                "password": "password123",
                "name": "New User",
                "role": "company_admin",
                "company_id": test_company.id,
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "newuser@test.com"
        assert data["role"] == "company_admin"
        assert data["company_id"] == test_company.id

    async def test_register_by_company_admin(
        self,
        client: AsyncClient,
        company_admin: User,
        test_company: Company,
    ):
        """company_admin can register distributor in their company."""
        headers = get_auth_header(company_admin)
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newdist@test.com",
                "password": "password123",
                "name": "New Distributor",
                "role": "distributor",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["role"] == "distributor"
        assert data["company_id"] == test_company.id

    async def test_register_company_admin_cannot_create_system_admin(
        self,
        client: AsyncClient,
        company_admin: User,
    ):
        """company_admin cannot create system_admin."""
        headers = get_auth_header(company_admin)
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newadmin@test.com",
                "password": "password123",
                "name": "New Admin",
                "role": "system_admin",
            },
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_register_distributor_creates_sub_account(
        self,
        client: AsyncClient,
        distributor: User,
        test_company: Company,
    ):
        """distributor can create sub_account (automatically set as parent)."""
        headers = get_auth_header(distributor)
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newsub@test.com",
                "password": "password123",
                "name": "New Sub",
                "role": "sub_account",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["role"] == "sub_account"
        assert data["parent_id"] == str(distributor.id)
        assert data["company_id"] == test_company.id

    async def test_register_duplicate_email(
        self,
        client: AsyncClient,
        system_admin: User,
        test_company: Company,
    ):
        """Duplicate email should return 409."""
        headers = get_auth_header(system_admin)

        # Create first user
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "dup@test.com",
                "password": "password123",
                "name": "First",
                "role": "company_admin",
                "company_id": test_company.id,
            },
            headers=headers,
        )

        # Try same email
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "dup@test.com",
                "password": "password123",
                "name": "Second",
                "role": "company_admin",
                "company_id": test_company.id,
            },
            headers=headers,
        )
        assert resp.status_code == 409

    async def test_register_sub_account_cannot_create_users(
        self,
        client: AsyncClient,
        sub_account: User,
    ):
        """sub_account cannot create any users."""
        headers = get_auth_header(sub_account)
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "forbidden@test.com",
                "password": "password123",
                "name": "Forbidden",
                "role": "sub_account",
            },
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_register_unauthenticated(self, client: AsyncClient):
        """Unauthenticated request should return 403."""
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "noauth@test.com",
                "password": "password123",
                "name": "No Auth",
                "role": "sub_account",
            },
        )
        assert resp.status_code == 401

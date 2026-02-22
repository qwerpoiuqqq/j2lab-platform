"""Tests for users endpoints: CRUD + role-based access + descendant tree."""

from __future__ import annotations

import uuid

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
class TestGetMe:
    """Tests for GET /api/v1/users/me."""

    async def test_get_me_success(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Authenticated user can get their own profile."""
        headers = get_auth_header(system_admin)
        resp = await client.get("/api/v1/users/me", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == system_admin.email
        assert data["role"] == "system_admin"

    async def test_get_me_unauthenticated(self, client: AsyncClient):
        """Unauthenticated should return 401."""
        resp = await client.get("/api/v1/users/me")
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestListUsers:
    """Tests for GET /api/v1/users."""

    async def test_list_users_as_system_admin(
        self,
        client: AsyncClient,
        system_admin: User,
        company_admin: User,
        distributor: User,
    ):
        """system_admin sees all users."""
        headers = get_auth_header(system_admin)
        resp = await client.get("/api/v1/users/", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3  # at least admin + cadmin + dist

    async def test_list_users_as_company_admin(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
        test_company_2: Company,
        company_admin: User,
    ):
        """company_admin sees only users in their company."""
        # Create a user in another company
        await create_test_user(
            db_session,
            email="other@j2lab.com",
            role=UserRole.COMPANY_ADMIN,
            company_id=test_company_2.id,
        )

        headers = get_auth_header(company_admin)
        resp = await client.get("/api/v1/users/", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        # Should only see users with company_id == test_company.id
        for item in data["items"]:
            assert item["company_id"] == test_company.id

    async def test_list_users_as_distributor(
        self,
        client: AsyncClient,
        distributor: User,
        sub_account: User,
    ):
        """distributor sees only their sub_accounts."""
        headers = get_auth_header(distributor)
        resp = await client.get("/api/v1/users/", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["parent_id"] == str(distributor.id)

    async def test_list_users_filter_by_role(
        self,
        client: AsyncClient,
        system_admin: User,
        company_admin: User,
        distributor: User,
    ):
        """Filter by role should work."""
        headers = get_auth_header(system_admin)
        resp = await client.get(
            "/api/v1/users/?role=distributor", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["role"] == "distributor"


@pytest.mark.asyncio
class TestCreateUser:
    """Tests for POST /api/v1/users."""

    async def test_create_user_by_system_admin(
        self,
        client: AsyncClient,
        system_admin: User,
        test_company: Company,
    ):
        """system_admin can create any role user."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/users/",
            json={
                "email": "newcadmin@test.com",
                "password": "password123",
                "name": "New CA",
                "role": "company_admin",
                "company_id": test_company.id,
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["role"] == "company_admin"

    async def test_create_user_by_company_admin(
        self,
        client: AsyncClient,
        company_admin: User,
        test_company: Company,
    ):
        """company_admin creates distributor in own company."""
        headers = get_auth_header(company_admin)
        resp = await client.post(
            "/api/v1/users/",
            json={
                "email": "newdist2@test.com",
                "password": "password123",
                "name": "New Dist",
                "role": "distributor",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["company_id"] == test_company.id

    async def test_company_admin_cannot_create_in_other_company(
        self,
        client: AsyncClient,
        company_admin: User,
        test_company_2: Company,
    ):
        """company_admin cannot create users in another company."""
        headers = get_auth_header(company_admin)
        resp = await client.post(
            "/api/v1/users/",
            json={
                "email": "othercorp@test.com",
                "password": "password123",
                "name": "Other Corp",
                "role": "distributor",
                "company_id": test_company_2.id,
            },
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_distributor_creates_sub_account(
        self,
        client: AsyncClient,
        distributor: User,
        test_company: Company,
    ):
        """distributor creates sub_account as parent."""
        headers = get_auth_header(distributor)
        resp = await client.post(
            "/api/v1/users/",
            json={
                "email": "newsub2@test.com",
                "password": "password123",
                "name": "New Sub",
                "role": "sub_account",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["parent_id"] == str(distributor.id)
        assert data["company_id"] == test_company.id

    async def test_distributor_cannot_create_distributor(
        self,
        client: AsyncClient,
        distributor: User,
    ):
        """distributor cannot create another distributor."""
        headers = get_auth_header(distributor)
        resp = await client.post(
            "/api/v1/users/",
            json={
                "email": "faileddist@test.com",
                "password": "password123",
                "name": "Failed",
                "role": "distributor",
            },
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_create_user_duplicate_email(
        self,
        client: AsyncClient,
        system_admin: User,
        company_admin: User,
        test_company: Company,
    ):
        """Duplicate email returns 409."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/users/",
            json={
                "email": company_admin.email,
                "password": "password123",
                "name": "Dup",
                "role": "company_admin",
                "company_id": test_company.id,
            },
            headers=headers,
        )
        assert resp.status_code == 409

    async def test_non_system_admin_requires_company_id(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Non-system_admin role requires company_id."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/users/",
            json={
                "email": "nocompany@test.com",
                "password": "password123",
                "name": "No Company",
                "role": "company_admin",
            },
            headers=headers,
        )
        assert resp.status_code == 400


@pytest.mark.asyncio
class TestGetUser:
    """Tests for GET /api/v1/users/{id}."""

    async def test_get_user_by_system_admin(
        self,
        client: AsyncClient,
        system_admin: User,
        company_admin: User,
    ):
        """system_admin can get any user."""
        headers = get_auth_header(system_admin)
        resp = await client.get(
            f"/api/v1/users/{company_admin.id}", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == str(company_admin.id)

    async def test_get_own_profile(
        self,
        client: AsyncClient,
        company_admin: User,
    ):
        """User can get their own profile."""
        headers = get_auth_header(company_admin)
        resp = await client.get(
            f"/api/v1/users/{company_admin.id}", headers=headers
        )
        assert resp.status_code == 200

    async def test_company_admin_views_same_company_user(
        self,
        client: AsyncClient,
        company_admin: User,
        distributor: User,
    ):
        """company_admin can view users in their own company."""
        headers = get_auth_header(company_admin)
        resp = await client.get(
            f"/api/v1/users/{distributor.id}", headers=headers
        )
        assert resp.status_code == 200

    async def test_company_admin_cannot_view_other_company_user(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        company_admin: User,
        test_company_2: Company,
    ):
        """company_admin cannot view users from another company."""
        other_user = await create_test_user(
            db_session,
            email="other2@j2lab.com",
            role=UserRole.COMPANY_ADMIN,
            company_id=test_company_2.id,
        )

        headers = get_auth_header(company_admin)
        resp = await client.get(
            f"/api/v1/users/{other_user.id}", headers=headers
        )
        assert resp.status_code == 403

    async def test_get_user_not_found(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Nonexistent user ID should return 404."""
        headers = get_auth_header(system_admin)
        fake_id = uuid.uuid4()
        resp = await client.get(
            f"/api/v1/users/{fake_id}", headers=headers
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestUpdateUser:
    """Tests for PATCH /api/v1/users/{id}."""

    async def test_update_user_by_system_admin(
        self,
        client: AsyncClient,
        system_admin: User,
        company_admin: User,
    ):
        """system_admin can update any user."""
        headers = get_auth_header(system_admin)
        resp = await client.patch(
            f"/api/v1/users/{company_admin.id}",
            json={"name": "Updated Name"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"

    async def test_update_user_by_company_admin(
        self,
        client: AsyncClient,
        company_admin: User,
        distributor: User,
    ):
        """company_admin can update users in their company."""
        headers = get_auth_header(company_admin)
        resp = await client.patch(
            f"/api/v1/users/{distributor.id}",
            json={"phone": "010-1234-5678"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["phone"] == "010-1234-5678"

    async def test_company_admin_cannot_update_other_company(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        company_admin: User,
        test_company_2: Company,
    ):
        """company_admin cannot update users from another company."""
        other_user = await create_test_user(
            db_session,
            email="other3@j2lab.com",
            role=UserRole.DISTRIBUTOR,
            company_id=test_company_2.id,
        )

        headers = get_auth_header(company_admin)
        resp = await client.patch(
            f"/api/v1/users/{other_user.id}",
            json={"name": "Hacked"},
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_update_user_password(
        self,
        client: AsyncClient,
        system_admin: User,
        distributor: User,
    ):
        """Updating password should work (can login with new password)."""
        headers = get_auth_header(system_admin)
        resp = await client.patch(
            f"/api/v1/users/{distributor.id}",
            json={"password": "newpassword123"},
            headers=headers,
        )
        assert resp.status_code == 200

        # Verify login with new password
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": distributor.email, "password": "newpassword123"},
        )
        assert login_resp.status_code == 200

    async def test_update_user_email_uniqueness(
        self,
        client: AsyncClient,
        system_admin: User,
        company_admin: User,
        distributor: User,
    ):
        """Updating to existing email should return 409."""
        headers = get_auth_header(system_admin)
        resp = await client.patch(
            f"/api/v1/users/{distributor.id}",
            json={"email": company_admin.email},
            headers=headers,
        )
        assert resp.status_code == 409


@pytest.mark.asyncio
class TestDeleteUser:
    """Tests for DELETE /api/v1/users/{id}."""

    async def test_delete_user_by_system_admin(
        self,
        client: AsyncClient,
        system_admin: User,
        distributor: User,
    ):
        """system_admin can soft-delete a user."""
        headers = get_auth_header(system_admin)
        resp = await client.delete(
            f"/api/v1/users/{distributor.id}", headers=headers
        )
        assert resp.status_code == 200

        # Verify deactivated
        resp = await client.get(
            f"/api/v1/users/{distributor.id}", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    async def test_delete_user_non_admin(
        self,
        client: AsyncClient,
        company_admin: User,
        distributor: User,
    ):
        """Non-system_admin cannot delete users."""
        headers = get_auth_header(company_admin)
        resp = await client.delete(
            f"/api/v1/users/{distributor.id}", headers=headers
        )
        assert resp.status_code == 403

    async def test_delete_user_not_found(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Deleting nonexistent user should return 404."""
        headers = get_auth_header(system_admin)
        fake_id = uuid.uuid4()
        resp = await client.delete(
            f"/api/v1/users/{fake_id}", headers=headers
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestUserDescendants:
    """Tests for GET /api/v1/users/{id}/descendants."""

    async def test_descendants_tree(
        self,
        client: AsyncClient,
        system_admin: User,
        distributor: User,
        sub_account: User,
    ):
        """Should return tree with children."""
        headers = get_auth_header(system_admin)
        resp = await client.get(
            f"/api/v1/users/{distributor.id}/descendants", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(distributor.id)
        assert data["role"] == "distributor"
        assert len(data["children"]) == 1
        assert data["children"][0]["id"] == str(sub_account.id)
        assert data["children"][0]["role"] == "sub_account"

    async def test_descendants_company_admin_same_company(
        self,
        client: AsyncClient,
        company_admin: User,
        distributor: User,
        sub_account: User,
    ):
        """company_admin can view trees in their company."""
        headers = get_auth_header(company_admin)
        resp = await client.get(
            f"/api/v1/users/{distributor.id}/descendants", headers=headers
        )
        assert resp.status_code == 200

    async def test_descendants_company_admin_other_company(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        company_admin: User,
        test_company_2: Company,
    ):
        """company_admin cannot view trees in other companies."""
        other_dist = await create_test_user(
            db_session,
            email="otherdist@j2lab.com",
            role=UserRole.DISTRIBUTOR,
            company_id=test_company_2.id,
        )

        headers = get_auth_header(company_admin)
        resp = await client.get(
            f"/api/v1/users/{other_dist.id}/descendants", headers=headers
        )
        assert resp.status_code == 403

    async def test_descendants_distributor_own_tree(
        self,
        client: AsyncClient,
        distributor: User,
        sub_account: User,
    ):
        """distributor can view their own tree."""
        headers = get_auth_header(distributor)
        resp = await client.get(
            f"/api/v1/users/{distributor.id}/descendants", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["children"]) == 1

    async def test_descendants_distributor_others_tree(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        test_company: Company,
    ):
        """distributor cannot view another distributor's tree."""
        other_dist = await create_test_user(
            db_session,
            email="otherdist2@ilryu.com",
            role=UserRole.DISTRIBUTOR,
            company_id=test_company.id,
        )

        headers = get_auth_header(distributor)
        resp = await client.get(
            f"/api/v1/users/{other_dist.id}/descendants", headers=headers
        )
        assert resp.status_code == 403

    async def test_descendants_not_found(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Nonexistent user should return 404."""
        headers = get_auth_header(system_admin)
        fake_id = uuid.uuid4()
        resp = await client.get(
            f"/api/v1/users/{fake_id}/descendants", headers=headers
        )
        assert resp.status_code == 404

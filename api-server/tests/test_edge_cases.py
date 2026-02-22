"""Edge-case tests: validation, security, authorization boundary conditions.

These tests cover scenarios not covered by the main test files:
- Invalid inputs (empty fields, too long strings, invalid emails)
- Authorization boundary violations
- Expired/malformed tokens
- Duplicate data handling
- Inactive user scenarios
- company_admin creating company_admin (should fail)
- order_handler trying to create users (should fail)
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.company import Company
from app.models.user import User, UserRole
from tests.conftest import (
    create_test_company,
    create_test_user,
    get_auth_header,
)


# ============================================================
# Auth edge cases
# ============================================================


@pytest.mark.asyncio
class TestAuthEdgeCases:
    """Edge-case tests for auth endpoints."""

    async def test_login_empty_password(self, client: AsyncClient):
        """Empty password should return 422 (validation error)."""
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@test.com", "password": ""},
        )
        # Empty password is still a valid string, should reach auth check
        # and return 401 (no such user)
        assert resp.status_code == 401

    async def test_login_invalid_email_format(self, client: AsyncClient):
        """Invalid email format should return 422."""
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "not-an-email", "password": "password123"},
        )
        assert resp.status_code == 422

    async def test_login_missing_fields(self, client: AsyncClient):
        """Missing required fields should return 422."""
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@test.com"},
        )
        assert resp.status_code == 422

    async def test_login_extra_fields_ignored(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """Extra fields in login request should be ignored."""
        await create_test_user(
            db_session,
            email="extra@test.com",
            password="password123",
            role=UserRole.COMPANY_ADMIN,
            company_id=test_company.id,
        )
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "extra@test.com",
                "password": "password123",
                "extra_field": "should_be_ignored",
            },
        )
        assert resp.status_code == 200

    async def test_expired_access_token(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Expired access token should return 401."""
        expired_token = create_access_token(
            data={"sub": str(system_admin.id), "role": system_admin.role},
            expires_delta=timedelta(seconds=-10),
        )
        headers = {"Authorization": f"Bearer {expired_token}"}
        resp = await client.get("/api/v1/users/me", headers=headers)
        assert resp.status_code == 401

    async def test_malformed_bearer_token(self, client: AsyncClient):
        """Malformed JWT token should return 401 or 403."""
        headers = {"Authorization": "Bearer this-is-not-a-jwt"}
        resp = await client.get("/api/v1/users/me", headers=headers)
        assert resp.status_code in (401, 403)

    async def test_missing_bearer_prefix(self, client: AsyncClient):
        """Missing Bearer prefix should return 401 or 403."""
        headers = {"Authorization": "some-token-without-bearer"}
        resp = await client.get("/api/v1/users/me", headers=headers)
        assert resp.status_code in (401, 403)

    async def test_token_with_nonexistent_user_id(
        self, client: AsyncClient
    ):
        """Token with valid format but nonexistent user ID should return 401."""
        fake_id = str(uuid.uuid4())
        token = create_access_token(
            data={"sub": fake_id, "role": "system_admin"}
        )
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.get("/api/v1/users/me", headers=headers)
        assert resp.status_code == 401

    async def test_token_with_invalid_uuid(self, client: AsyncClient):
        """Token with non-UUID sub claim should return 401."""
        token = create_access_token(
            data={"sub": "not-a-uuid", "role": "system_admin"}
        )
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.get("/api/v1/users/me", headers=headers)
        assert resp.status_code == 401

    async def test_token_without_sub_claim(self, client: AsyncClient):
        """Token without sub claim should return 401."""
        token = create_access_token(data={"role": "system_admin"})
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.get("/api/v1/users/me", headers=headers)
        assert resp.status_code == 401

    async def test_refresh_empty_token(self, client: AsyncClient):
        """Empty refresh token should return 401."""
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": ""},
        )
        assert resp.status_code == 401

    async def test_logout_empty_token(self, client: AsyncClient):
        """Empty refresh token on logout should return 400."""
        resp = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": ""},
        )
        assert resp.status_code == 400

    async def test_inactive_user_cannot_access_protected_endpoints(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """User deactivated after token issuance should be blocked."""
        user = await create_test_user(
            db_session,
            email="willdeactivate@test.com",
            password="password123",
            role=UserRole.COMPANY_ADMIN,
            company_id=test_company.id,
            is_active=True,
        )
        headers = get_auth_header(user)

        # Deactivate the user
        user.is_active = False
        await db_session.flush()

        # Try to access protected endpoint
        resp = await client.get("/api/v1/users/me", headers=headers)
        assert resp.status_code == 403
        assert "Inactive user" in resp.json()["detail"]


# ============================================================
# Registration edge cases
# ============================================================


@pytest.mark.asyncio
class TestRegistrationEdgeCases:
    """Edge-case tests for user registration."""

    async def test_register_password_too_short(
        self,
        client: AsyncClient,
        system_admin: User,
        test_company: Company,
    ):
        """Password shorter than 8 characters should return 422."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "shortpw@test.com",
                "password": "short",
                "name": "Short PW",
                "role": "company_admin",
                "company_id": test_company.id,
            },
            headers=headers,
        )
        assert resp.status_code == 422

    async def test_register_password_too_long(
        self,
        client: AsyncClient,
        system_admin: User,
        test_company: Company,
    ):
        """Password longer than 128 characters should return 422."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "longpw@test.com",
                "password": "a" * 129,
                "name": "Long PW",
                "role": "company_admin",
                "company_id": test_company.id,
            },
            headers=headers,
        )
        assert resp.status_code == 422

    async def test_register_name_empty(
        self,
        client: AsyncClient,
        system_admin: User,
        test_company: Company,
    ):
        """Empty name should return 422."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "emptyname@test.com",
                "password": "password123",
                "name": "",
                "role": "company_admin",
                "company_id": test_company.id,
            },
            headers=headers,
        )
        assert resp.status_code == 422

    async def test_register_name_too_long(
        self,
        client: AsyncClient,
        system_admin: User,
        test_company: Company,
    ):
        """Name longer than 50 characters should return 422."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "longname@test.com",
                "password": "password123",
                "name": "A" * 51,
                "role": "company_admin",
                "company_id": test_company.id,
            },
            headers=headers,
        )
        assert resp.status_code == 422

    async def test_register_invalid_role(
        self,
        client: AsyncClient,
        system_admin: User,
        test_company: Company,
    ):
        """Invalid role value should return 422."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "badrole@test.com",
                "password": "password123",
                "name": "Bad Role",
                "role": "superuser",
                "company_id": test_company.id,
            },
            headers=headers,
        )
        assert resp.status_code == 422

    async def test_company_admin_cannot_create_company_admin(
        self,
        client: AsyncClient,
        company_admin: User,
        test_company: Company,
    ):
        """company_admin cannot create another company_admin."""
        headers = get_auth_header(company_admin)
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newcadmin@test.com",
                "password": "password123",
                "name": "New CA",
                "role": "company_admin",
            },
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_order_handler_cannot_create_users(
        self,
        client: AsyncClient,
        order_handler: User,
    ):
        """order_handler cannot create any users."""
        headers = get_auth_header(order_handler)
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "nope@test.com",
                "password": "password123",
                "name": "Nope",
                "role": "sub_account",
            },
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_distributor_cannot_create_order_handler(
        self,
        client: AsyncClient,
        distributor: User,
    ):
        """distributor can only create sub_account, not order_handler."""
        headers = get_auth_header(distributor)
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "handler@test.com",
                "password": "password123",
                "name": "Handler",
                "role": "order_handler",
            },
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_register_system_admin_with_company_id(
        self,
        client: AsyncClient,
        system_admin: User,
        test_company: Company,
    ):
        """system_admin user should NOT have company_id."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "sysadmin2@test.com",
                "password": "password123",
                "name": "SA2",
                "role": "system_admin",
                "company_id": test_company.id,
            },
            headers=headers,
        )
        assert resp.status_code == 400

    async def test_register_non_system_admin_without_company_id(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Non-system_admin user requires company_id."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "nocompany@test.com",
                "password": "password123",
                "name": "No Company",
                "role": "distributor",
            },
            headers=headers,
        )
        assert resp.status_code == 400

    async def test_register_invalid_email_format(
        self,
        client: AsyncClient,
        system_admin: User,
        test_company: Company,
    ):
        """Invalid email format should return 422."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-valid-email",
                "password": "password123",
                "name": "Bad Email",
                "role": "company_admin",
                "company_id": test_company.id,
            },
            headers=headers,
        )
        assert resp.status_code == 422

    async def test_register_with_nonexistent_company_id(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Registering with nonexistent company_id should return 400."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "badcompany@test.com",
                "password": "password123",
                "name": "Bad Company",
                "role": "company_admin",
                "company_id": 99999,
            },
            headers=headers,
        )
        assert resp.status_code == 400


# ============================================================
# Company edge cases
# ============================================================


@pytest.mark.asyncio
class TestCompanyEdgeCases:
    """Edge-case tests for company CRUD."""

    async def test_create_company_empty_name(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Empty company name should return 422."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/companies/",
            json={"name": "", "code": "empty"},
            headers=headers,
        )
        assert resp.status_code == 422

    async def test_create_company_empty_code(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Empty company code should return 422."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/companies/",
            json={"name": "Company", "code": ""},
            headers=headers,
        )
        assert resp.status_code == 422

    async def test_create_company_name_too_long(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Company name > 100 chars should return 422."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/companies/",
            json={"name": "A" * 101, "code": "toolong"},
            headers=headers,
        )
        assert resp.status_code == 422

    async def test_create_company_code_too_long(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Company code > 50 chars should return 422."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/companies/",
            json={"name": "Company", "code": "A" * 51},
            headers=headers,
        )
        assert resp.status_code == 422

    async def test_update_company_empty_name(
        self,
        client: AsyncClient,
        system_admin: User,
        test_company: Company,
    ):
        """Updating company with empty name should return 422."""
        headers = get_auth_header(system_admin)
        resp = await client.patch(
            f"/api/v1/companies/{test_company.id}",
            json={"name": ""},
            headers=headers,
        )
        assert resp.status_code == 422

    async def test_update_nonexistent_company(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Updating nonexistent company should return 404."""
        headers = get_auth_header(system_admin)
        resp = await client.patch(
            "/api/v1/companies/99999",
            json={"name": "Ghost"},
            headers=headers,
        )
        assert resp.status_code == 404

    async def test_get_company_negative_id(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Negative company ID should return 404 (or 422)."""
        headers = get_auth_header(system_admin)
        resp = await client.get("/api/v1/companies/-1", headers=headers)
        assert resp.status_code in (404, 422)

    async def test_list_companies_filter_active(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        system_admin: User,
    ):
        """Filter by is_active should work correctly."""
        headers = get_auth_header(system_admin)

        # Create active and inactive companies
        await create_test_company(db_session, name="Active Corp", code="active_co")
        inactive = await create_test_company(db_session, name="Inactive Corp", code="inactive_co")
        inactive.is_active = False
        await db_session.flush()

        # Filter active only
        resp = await client.get(
            "/api/v1/companies/?is_active=true", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["is_active"] is True

        # Filter inactive only
        resp = await client.get(
            "/api/v1/companies/?is_active=false", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["is_active"] is False

    async def test_list_companies_invalid_page(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Page < 1 should return 422."""
        headers = get_auth_header(system_admin)
        resp = await client.get("/api/v1/companies/?page=0", headers=headers)
        assert resp.status_code == 422

    async def test_list_companies_size_too_large(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Size > 100 should return 422."""
        headers = get_auth_header(system_admin)
        resp = await client.get(
            "/api/v1/companies/?size=101", headers=headers
        )
        assert resp.status_code == 422

    async def test_company_operations_by_distributor(
        self,
        client: AsyncClient,
        distributor: User,
    ):
        """distributor cannot access company management endpoints."""
        headers = get_auth_header(distributor)

        # List
        resp = await client.get("/api/v1/companies/", headers=headers)
        assert resp.status_code == 403

        # Create
        resp = await client.post(
            "/api/v1/companies/",
            json={"name": "Forbidden", "code": "forbidden"},
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_company_operations_by_order_handler(
        self,
        client: AsyncClient,
        order_handler: User,
    ):
        """order_handler cannot access company management endpoints."""
        headers = get_auth_header(order_handler)
        resp = await client.get("/api/v1/companies/", headers=headers)
        assert resp.status_code == 403

    async def test_company_operations_by_sub_account(
        self,
        client: AsyncClient,
        sub_account: User,
    ):
        """sub_account cannot access company management endpoints."""
        headers = get_auth_header(sub_account)
        resp = await client.get("/api/v1/companies/", headers=headers)
        assert resp.status_code == 403


# ============================================================
# User CRUD edge cases
# ============================================================


@pytest.mark.asyncio
class TestUserCrudEdgeCases:
    """Edge-case tests for user CRUD operations."""

    async def test_create_user_with_nonexistent_company_id(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Creating user with non-existent company_id should return 400."""
        headers = get_auth_header(system_admin)
        resp = await client.post(
            "/api/v1/users/",
            json={
                "email": "orphan@test.com",
                "password": "password123",
                "name": "Orphan",
                "role": "company_admin",
                "company_id": 99999,
            },
            headers=headers,
        )
        assert resp.status_code == 400
        assert "not found" in resp.json()["detail"]

    async def test_update_user_with_invalid_uuid(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Invalid UUID format should return 422."""
        headers = get_auth_header(system_admin)
        resp = await client.patch(
            "/api/v1/users/not-a-uuid",
            json={"name": "Hacked"},
            headers=headers,
        )
        assert resp.status_code == 422

    async def test_delete_user_with_invalid_uuid(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Invalid UUID format should return 422."""
        headers = get_auth_header(system_admin)
        resp = await client.delete(
            "/api/v1/users/not-a-uuid", headers=headers
        )
        assert resp.status_code == 422

    async def test_list_users_as_sub_account(
        self,
        client: AsyncClient,
        sub_account: User,
    ):
        """sub_account should only see themselves."""
        headers = get_auth_header(sub_account)
        resp = await client.get("/api/v1/users/", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == str(sub_account.id)

    async def test_sub_account_cannot_view_other_user(
        self,
        client: AsyncClient,
        sub_account: User,
        system_admin: User,
    ):
        """sub_account cannot view other users' details."""
        headers = get_auth_header(sub_account)
        resp = await client.get(
            f"/api/v1/users/{system_admin.id}", headers=headers
        )
        assert resp.status_code == 403

    async def test_distributor_can_view_own_sub_account(
        self,
        client: AsyncClient,
        distributor: User,
        sub_account: User,
    ):
        """distributor can view their own sub_account."""
        headers = get_auth_header(distributor)
        resp = await client.get(
            f"/api/v1/users/{sub_account.id}", headers=headers
        )
        assert resp.status_code == 200

    async def test_distributor_cannot_view_other_user(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        distributor: User,
        test_company: Company,
    ):
        """distributor cannot view users who are not their sub_accounts."""
        other_user = await create_test_user(
            db_session,
            email="othersub@test.com",
            role=UserRole.SUB_ACCOUNT,
            company_id=test_company.id,
            # Different parent (no parent)
            parent_id=None,
        )
        headers = get_auth_header(distributor)
        resp = await client.get(
            f"/api/v1/users/{other_user.id}", headers=headers
        )
        assert resp.status_code == 403

    async def test_distributor_cannot_update_users(
        self,
        client: AsyncClient,
        distributor: User,
        sub_account: User,
    ):
        """distributor cannot update users (only system_admin and company_admin)."""
        headers = get_auth_header(distributor)
        resp = await client.patch(
            f"/api/v1/users/{sub_account.id}",
            json={"name": "Hacked Name"},
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_order_handler_cannot_update_users(
        self,
        client: AsyncClient,
        order_handler: User,
        distributor: User,
    ):
        """order_handler cannot update users."""
        headers = get_auth_header(order_handler)
        resp = await client.patch(
            f"/api/v1/users/{distributor.id}",
            json={"name": "Hacked"},
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_order_handler_cannot_delete_users(
        self,
        client: AsyncClient,
        order_handler: User,
        distributor: User,
    ):
        """order_handler cannot delete users."""
        headers = get_auth_header(order_handler)
        resp = await client.delete(
            f"/api/v1/users/{distributor.id}", headers=headers
        )
        assert resp.status_code == 403

    async def test_company_admin_cannot_delete_users(
        self,
        client: AsyncClient,
        company_admin: User,
        distributor: User,
    ):
        """company_admin cannot delete users (only system_admin can)."""
        headers = get_auth_header(company_admin)
        resp = await client.delete(
            f"/api/v1/users/{distributor.id}", headers=headers
        )
        assert resp.status_code == 403

    async def test_update_own_email_to_same_value(
        self,
        client: AsyncClient,
        system_admin: User,
        company_admin: User,
    ):
        """Updating email to the same value should succeed (no conflict)."""
        headers = get_auth_header(system_admin)
        resp = await client.patch(
            f"/api/v1/users/{company_admin.id}",
            json={"email": company_admin.email},
            headers=headers,
        )
        assert resp.status_code == 200

    async def test_create_user_via_users_endpoint_by_order_handler(
        self,
        client: AsyncClient,
        order_handler: User,
        test_company: Company,
    ):
        """order_handler cannot create users via /users endpoint."""
        headers = get_auth_header(order_handler)
        resp = await client.post(
            "/api/v1/users/",
            json={
                "email": "noperm@test.com",
                "password": "password123",
                "name": "No Permission",
                "role": "sub_account",
                "company_id": test_company.id,
            },
            headers=headers,
        )
        assert resp.status_code == 403


# ============================================================
# User descendants edge cases
# ============================================================


@pytest.mark.asyncio
class TestDescendantsEdgeCases:
    """Edge-case tests for user descendants tree."""

    async def test_descendants_empty_tree(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        system_admin: User,
        test_company: Company,
    ):
        """User with no children should return tree with empty children list."""
        lonely_dist = await create_test_user(
            db_session,
            email="lonely@test.com",
            role=UserRole.DISTRIBUTOR,
            company_id=test_company.id,
        )
        headers = get_auth_header(system_admin)
        resp = await client.get(
            f"/api/v1/users/{lonely_dist.id}/descendants", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["children"] == []

    async def test_descendants_by_sub_account_forbidden(
        self,
        client: AsyncClient,
        sub_account: User,
        distributor: User,
    ):
        """sub_account cannot access descendants endpoint."""
        headers = get_auth_header(sub_account)
        resp = await client.get(
            f"/api/v1/users/{distributor.id}/descendants", headers=headers
        )
        assert resp.status_code == 403

    async def test_descendants_by_order_handler_forbidden(
        self,
        client: AsyncClient,
        order_handler: User,
        distributor: User,
    ):
        """order_handler cannot access descendants endpoint."""
        headers = get_auth_header(order_handler)
        resp = await client.get(
            f"/api/v1/users/{distributor.id}/descendants", headers=headers
        )
        assert resp.status_code == 403

    async def test_descendants_multi_level(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        system_admin: User,
        test_company: Company,
    ):
        """Descendants should handle multi-level nesting (dist -> sub -> ...)."""
        dist = await create_test_user(
            db_session,
            email="mlevel_dist@test.com",
            role=UserRole.DISTRIBUTOR,
            company_id=test_company.id,
        )
        sub1 = await create_test_user(
            db_session,
            email="mlevel_sub1@test.com",
            role=UserRole.SUB_ACCOUNT,
            company_id=test_company.id,
            parent_id=dist.id,
        )
        sub2 = await create_test_user(
            db_session,
            email="mlevel_sub2@test.com",
            role=UserRole.SUB_ACCOUNT,
            company_id=test_company.id,
            parent_id=dist.id,
        )

        headers = get_auth_header(system_admin)
        resp = await client.get(
            f"/api/v1/users/{dist.id}/descendants", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["children"]) == 2
        child_ids = {c["id"] for c in data["children"]}
        assert str(sub1.id) in child_ids
        assert str(sub2.id) in child_ids


# ============================================================
# Cross-endpoint flow tests
# ============================================================


@pytest.mark.asyncio
class TestCrossEndpointFlows:
    """Tests combining multiple endpoints to verify consistent behavior."""

    async def test_register_then_login(
        self,
        client: AsyncClient,
        system_admin: User,
        test_company: Company,
    ):
        """User registered via API should be able to login."""
        headers = get_auth_header(system_admin)

        # Register
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "flow_test@test.com",
                "password": "password123",
                "name": "Flow Test",
                "role": "company_admin",
                "company_id": test_company.id,
            },
            headers=headers,
        )
        assert resp.status_code == 201

        # Login
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "flow_test@test.com", "password": "password123"},
        )
        assert resp.status_code == 200
        tokens = resp.json()

        # Use access token
        resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "flow_test@test.com"

    async def test_login_refresh_logout_flow(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        """Full auth lifecycle: login -> refresh -> logout -> verify revoked."""
        await create_test_user(
            db_session,
            email="lifecycle@test.com",
            password="password123",
            role=UserRole.COMPANY_ADMIN,
            company_id=test_company.id,
        )

        # Login
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "lifecycle@test.com", "password": "password123"},
        )
        assert resp.status_code == 200
        tokens1 = resp.json()

        # Refresh
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens1["refresh_token"]},
        )
        assert resp.status_code == 200
        tokens2 = resp.json()

        # Old refresh token should be revoked
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens1["refresh_token"]},
        )
        assert resp.status_code == 401

        # Logout with new refresh token
        resp = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": tokens2["refresh_token"]},
        )
        assert resp.status_code == 200

        # Verify new refresh token is revoked
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens2["refresh_token"]},
        )
        assert resp.status_code == 401

    async def test_deactivated_user_cannot_login(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        system_admin: User,
        test_company: Company,
    ):
        """Soft-deleted user should not be able to login."""
        user = await create_test_user(
            db_session,
            email="todelete@test.com",
            password="password123",
            role=UserRole.DISTRIBUTOR,
            company_id=test_company.id,
        )

        # Delete the user
        headers = get_auth_header(system_admin)
        resp = await client.delete(
            f"/api/v1/users/{user.id}", headers=headers
        )
        assert resp.status_code == 200

        # Try to login
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "todelete@test.com", "password": "password123"},
        )
        assert resp.status_code == 401

    async def test_company_admin_creates_org_tree(
        self,
        client: AsyncClient,
        company_admin: User,
        test_company: Company,
    ):
        """company_admin can build an org tree: admin -> dist -> sub."""
        headers = get_auth_header(company_admin)

        # Create distributor
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "tree_dist@test.com",
                "password": "password123",
                "name": "Tree Dist",
                "role": "distributor",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        dist_id = resp.json()["id"]

        # Login as distributor
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "tree_dist@test.com", "password": "password123"},
        )
        assert resp.status_code == 200
        dist_headers = {
            "Authorization": f"Bearer {resp.json()['access_token']}"
        }

        # Distributor creates sub_account
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "tree_sub@test.com",
                "password": "password123",
                "name": "Tree Sub",
                "role": "sub_account",
            },
            headers=dist_headers,
        )
        assert resp.status_code == 201
        sub_data = resp.json()
        assert sub_data["parent_id"] == dist_id
        assert sub_data["company_id"] == test_company.id

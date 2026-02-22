"""Tests for system settings endpoints: CRUD operations."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_setting import SystemSetting
from app.models.user import User, UserRole
from tests.conftest import get_auth_header


@pytest.mark.asyncio
class TestListSettings:
    """Tests for GET /api/v1/settings."""

    async def test_list_settings_as_system_admin(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        system_admin: User,
    ):
        """system_admin can list all settings."""
        # Create test settings
        s1 = SystemSetting(key="max_concurrent", value=5, description="Max workers")
        s2 = SystemSetting(key="target_count", value=200, description="Default target")
        db_session.add_all([s1, s2])
        await db_session.commit()

        headers = get_auth_header(system_admin)
        resp = await client.get("/api/v1/settings/", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    async def test_list_settings_non_admin_forbidden(
        self,
        client: AsyncClient,
        company_admin: User,
    ):
        """Non-system_admin cannot access settings."""
        headers = get_auth_header(company_admin)
        resp = await client.get("/api/v1/settings/", headers=headers)
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestGetSetting:
    """Tests for GET /api/v1/settings/{key}."""

    async def test_get_setting_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        system_admin: User,
    ):
        """Get a specific setting by key."""
        setting = SystemSetting(
            key="max_concurrent", value=5, description="Max workers"
        )
        db_session.add(setting)
        await db_session.commit()

        headers = get_auth_header(system_admin)
        resp = await client.get(
            "/api/v1/settings/max_concurrent", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["key"] == "max_concurrent"
        assert data["value"] == 5

    async def test_get_setting_not_found(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Nonexistent setting should return 404."""
        headers = get_auth_header(system_admin)
        resp = await client.get(
            "/api/v1/settings/nonexistent", headers=headers
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestUpsertSetting:
    """Tests for PUT /api/v1/settings/{key}."""

    async def test_create_setting(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Create a new setting via PUT."""
        headers = get_auth_header(system_admin)
        resp = await client.put(
            "/api/v1/settings/new_setting",
            json={"value": 42, "description": "Test setting"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["key"] == "new_setting"
        assert data["value"] == 42
        assert data["description"] == "Test setting"
        assert data["updated_by"] == str(system_admin.id)

    async def test_update_existing_setting(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        system_admin: User,
    ):
        """Update an existing setting via PUT."""
        setting = SystemSetting(key="test_key", value=1, description="Old desc")
        db_session.add(setting)
        await db_session.commit()

        headers = get_auth_header(system_admin)
        resp = await client.put(
            "/api/v1/settings/test_key",
            json={"value": 99, "description": "New desc"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["value"] == 99
        assert data["description"] == "New desc"

    async def test_setting_json_value(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Settings can store JSON values (objects, arrays)."""
        headers = get_auth_header(system_admin)
        resp = await client.put(
            "/api/v1/settings/complex_value",
            json={
                "value": {"key": "val", "list": [1, 2, 3]},
                "description": "Complex JSON",
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["value"] == {"key": "val", "list": [1, 2, 3]}


@pytest.mark.asyncio
class TestDeleteSetting:
    """Tests for DELETE /api/v1/settings/{key}."""

    async def test_delete_setting_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        system_admin: User,
    ):
        """system_admin can delete a setting."""
        setting = SystemSetting(key="to_delete", value="temp")
        db_session.add(setting)
        await db_session.commit()

        headers = get_auth_header(system_admin)
        resp = await client.delete(
            "/api/v1/settings/to_delete", headers=headers
        )
        assert resp.status_code == 204

        # Verify it's deleted
        resp2 = await client.get(
            "/api/v1/settings/to_delete", headers=headers
        )
        assert resp2.status_code == 404

    async def test_delete_setting_not_found(
        self,
        client: AsyncClient,
        system_admin: User,
    ):
        """Deleting nonexistent setting should return 404."""
        headers = get_auth_header(system_admin)
        resp = await client.delete(
            "/api/v1/settings/nonexistent", headers=headers
        )
        assert resp.status_code == 404

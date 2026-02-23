"""Tests for internal API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check(self, client):
        response = client.get("/internal/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "Keyword Worker" in data["service"]


class TestCapacityEndpoint:
    """Test capacity endpoint."""

    def test_capacity_info(self, client):
        response = client.get("/internal/capacity")
        assert response.status_code == 200
        data = response.json()
        assert "max_concurrent_jobs" in data
        assert "running_jobs" in data
        assert "available_slots" in data
        assert data["available_slots"] >= 0

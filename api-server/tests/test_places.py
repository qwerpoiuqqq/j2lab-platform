"""Tests for places endpoints."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.keyword import Keyword
from app.models.place import Place
from app.models.user import User, UserRole
from tests.conftest import (
    create_test_company,
    create_test_user,
    get_auth_header,
)


async def create_test_place(
    db: AsyncSession,
    place_id: int = 1234567890,
    name: str = "Test Restaurant",
    place_type: str = "restaurant",
    gu: str = "강남구",
    major_area: str = "강남",
) -> Place:
    """Create a test place."""
    place = Place(
        id=place_id,
        name=name,
        place_type=place_type,
        gu=gu,
        major_area=major_area,
        category="음식점>이탈리안",
        naver_url=f"https://map.naver.com/p/entry/place/{place_id}",
    )
    db.add(place)
    await db.flush()
    await db.refresh(place)
    return place


async def create_test_keyword(
    db: AsyncSession,
    place_id: int,
    keyword: str = "강남 파스타",
    keyword_type: str = "region",
    current_rank: int | None = 3,
) -> Keyword:
    """Create a test keyword."""
    kw = Keyword(
        place_id=place_id,
        keyword=keyword,
        keyword_type=keyword_type,
        current_rank=current_rank,
    )
    db.add(kw)
    await db.flush()
    await db.refresh(kw)
    return kw


@pytest.mark.asyncio
class TestListPlaces:
    """Tests for GET /api/v1/places."""

    async def test_list_places(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        user = await create_test_user(
            db_session, email="u@test.com", role=UserRole.SUB_ACCOUNT,
            company_id=test_company.id,
        )
        await create_test_place(db_session, place_id=111, name="Place A")
        await create_test_place(db_session, place_id=222, name="Place B")
        await db_session.commit()

        headers = get_auth_header(user)
        resp = await client.get("/api/v1/places/", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    async def test_list_places_filter_by_gu(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        user = await create_test_user(
            db_session, email="u@test.com", role=UserRole.SUB_ACCOUNT,
            company_id=test_company.id,
        )
        await create_test_place(db_session, place_id=111, name="A", gu="강남구")
        await create_test_place(db_session, place_id=222, name="B", gu="서초구")
        await db_session.commit()

        headers = get_auth_header(user)
        resp = await client.get("/api/v1/places/?gu=강남구", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    async def test_list_places_filter_by_type(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        user = await create_test_user(
            db_session, email="u@test.com", role=UserRole.SUB_ACCOUNT,
            company_id=test_company.id,
        )
        await create_test_place(db_session, place_id=111, place_type="restaurant")
        await create_test_place(db_session, place_id=222, place_type="hospital")
        await db_session.commit()

        headers = get_auth_header(user)
        resp = await client.get("/api/v1/places/?place_type=restaurant", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 1


@pytest.mark.asyncio
class TestGetPlace:
    """Tests for GET /api/v1/places/{place_id}."""

    async def test_get_place(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        user = await create_test_user(
            db_session, email="u@test.com", role=UserRole.SUB_ACCOUNT,
            company_id=test_company.id,
        )
        place = await create_test_place(db_session)
        await db_session.commit()

        headers = get_auth_header(user)
        resp = await client.get(f"/api/v1/places/{place.id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test Restaurant"

    async def test_get_place_not_found(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        user = await create_test_user(
            db_session, email="u@test.com", role=UserRole.SUB_ACCOUNT,
            company_id=test_company.id,
        )
        await db_session.commit()

        headers = get_auth_header(user)
        resp = await client.get("/api/v1/places/99999", headers=headers)
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestPlaceKeywords:
    """Tests for GET /api/v1/places/{place_id}/keywords."""

    async def test_list_place_keywords(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        user = await create_test_user(
            db_session, email="u@test.com", role=UserRole.SUB_ACCOUNT,
            company_id=test_company.id,
        )
        place = await create_test_place(db_session)
        await create_test_keyword(db_session, place.id, keyword="강남 파스타")
        await create_test_keyword(db_session, place.id, keyword="역삼역 맛집")
        await db_session.commit()

        headers = get_auth_header(user)
        resp = await client.get(f"/api/v1/places/{place.id}/keywords", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    async def test_list_keywords_filter_by_type(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        user = await create_test_user(
            db_session, email="u@test.com", role=UserRole.SUB_ACCOUNT,
            company_id=test_company.id,
        )
        place = await create_test_place(db_session)
        await create_test_keyword(db_session, place.id, keyword="kw1", keyword_type="region")
        await create_test_keyword(db_session, place.id, keyword="kw2", keyword_type="menu")
        await db_session.commit()

        headers = get_auth_header(user)
        resp = await client.get(
            f"/api/v1/places/{place.id}/keywords?keyword_type=menu",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    async def test_keywords_for_nonexistent_place(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        user = await create_test_user(
            db_session, email="u@test.com", role=UserRole.SUB_ACCOUNT,
            company_id=test_company.id,
        )
        await db_session.commit()

        headers = get_auth_header(user)
        resp = await client.get("/api/v1/places/99999/keywords", headers=headers)
        assert resp.status_code == 404

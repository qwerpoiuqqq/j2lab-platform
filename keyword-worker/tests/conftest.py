"""Test fixtures for keyword-worker tests."""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import Column, BigInteger, Integer, String, Table
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.database import Base
from app.models.extraction_job import ExtractionJob
from app.models.keyword import Keyword
from app.models.keyword_rank_history import KeywordRankHistory
from app.models.place import Place
from app.services.place_scraper import PlaceData, RegionInfo, ReviewKeyword

# Create a stub order_items table that extraction_jobs references.
# In production, this table is managed by api-server's Alembic migrations.
_order_items_stub = Table(
    "order_items",
    Base.metadata,
    Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True),
    Column("status", String(20)),
    extend_existing=True,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for session-scoped async fixtures."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Create an in-memory SQLite async engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for testing."""
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session


@pytest.fixture
def sample_place_data() -> PlaceData:
    """Sample PlaceData for testing."""
    return PlaceData(
        id="1082820234",
        name="미도인 강남",
        category="이탈리아음식",
        road_address="서울 강남구 테헤란로 123",
        jibun_address="서울 강남구 역삼동 123-45",
        region=RegionInfo(
            city="서울",
            si="",
            gu="강남구",
            dong="역삼동",
            road="테헤란로",
            si_without_suffix="",
            gu_without_suffix="강남",
            dong_without_suffix="역삼",
            major_area="",
            stations=["강남역", "역삼역"],
        ),
        phone="02-1234-5678",
        keywords=["파스타", "스테이크", "이탈리안"],
        menus=["크림파스타", "안심스테이크", "리조또", "티라미수"],
        review_menu_keywords=[
            ReviewKeyword(label="파스타", count=150),
            ReviewKeyword(label="스테이크", count=120),
            ReviewKeyword(label="리조또", count=80),
        ],
        review_theme_keywords=[
            ReviewKeyword(label="분위기", count=200),
            ReviewKeyword(label="가격", count=150),
            ReviewKeyword(label="주차", count=100),
        ],
        medical_subjects=[],
        introduction="강남역 근처 이탈리안 레스토랑",
        url="https://m.place.naver.com/restaurant/1082820234/home",
    )


@pytest.fixture
def sample_hospital_data() -> PlaceData:
    """Sample PlaceData for a hospital."""
    return PlaceData(
        id="1984640040",
        name="세라믹치과의원",
        category="치과",
        road_address="경기 고양시 일산동구 중앙로 1234",
        jibun_address="경기 고양시 일산동구 장항동 123",
        region=RegionInfo(
            city="경기",
            si="고양시",
            gu="일산동구",
            dong="장항동",
            road="중앙로",
            si_without_suffix="고양",
            gu_without_suffix="일산동",
            dong_without_suffix="장항",
            major_area="일산",
            stations=["정발산역"],
        ),
        phone="031-123-4567",
        keywords=["치과", "임플란트", "교정"],
        menus=[],
        review_menu_keywords=[],
        review_theme_keywords=[
            ReviewKeyword(label="친절", count=100),
            ReviewKeyword(label="청결", count=80),
        ],
        medical_subjects=["일반치과", "교정치과", "구강외과"],
        introduction="일산 세라믹치과의원",
        url="https://m.place.naver.com/hospital/1984640040/home",
    )

"""Test fixtures: async DB, test client, helper functions."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from typing import Optional

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.company import Company
from app.models.user import User, UserRole

# Use SQLite in-memory for tests
TEST_DATABASE_URL = "sqlite+aiosqlite://"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# We store the active session so that both the app dependency and
# test fixtures can share the same session (and thus the same transaction).
_current_test_session: Optional[AsyncSession] = None


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create tables before each test, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a test database session shared with the app."""
    global _current_test_session
    async with TestSessionLocal() as session:
        _current_test_session = session
        yield session
        # Commit any pending changes from fixtures
        await session.commit()
        _current_test_session = None


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    """Override the get_db dependency - uses the shared test session."""
    global _current_test_session
    if _current_test_session is not None:
        # Use the same session as the test fixture
        yield _current_test_session
    else:
        # Fallback: create a new session
        async with TestSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP test client. Depends on db_session to ensure shared session."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# === Helper factories ===


async def create_test_company(
    db: AsyncSession,
    name: str = "Test Company",
    code: str = "test",
) -> Company:
    """Create a test company in the database."""
    company = Company(name=name, code=code, is_active=True)
    db.add(company)
    await db.flush()
    await db.refresh(company)
    return company


async def create_test_user(
    db: AsyncSession,
    email: str = "test@example.com",
    password: str = "testpassword123",
    name: str = "Test User",
    role: UserRole = UserRole.SUB_ACCOUNT,
    company_id: Optional[int] = None,
    parent_id: Optional[uuid.UUID] = None,
    is_active: bool = True,
) -> User:
    """Create a test user in the database."""
    user = User(
        email=email,
        hashed_password=hash_password(password),
        name=name,
        role=role.value,
        company_id=company_id,
        parent_id=parent_id,
        is_active=is_active,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


def get_auth_header(user: User) -> dict:
    """Generate an Authorization header with a valid JWT token for the user."""
    token = create_access_token(
        data={"sub": str(user.id), "role": user.role}
    )
    return {"Authorization": f"Bearer {token}"}


# === Common fixtures ===


@pytest_asyncio.fixture
async def test_company(db_session: AsyncSession) -> Company:
    """Create a default test company."""
    return await create_test_company(db_session, name="일류기획", code="ilryu")


@pytest_asyncio.fixture
async def test_company_2(db_session: AsyncSession) -> Company:
    """Create a second test company."""
    return await create_test_company(db_session, name="제이투랩", code="j2lab")


@pytest_asyncio.fixture
async def system_admin(db_session: AsyncSession) -> User:
    """Create a system_admin user (no company)."""
    return await create_test_user(
        db_session,
        email="admin@j2lab.com",
        name="System Admin",
        role=UserRole.SYSTEM_ADMIN,
        company_id=None,
    )


@pytest_asyncio.fixture
async def company_admin(
    db_session: AsyncSession, test_company: Company
) -> User:
    """Create a company_admin user."""
    return await create_test_user(
        db_session,
        email="cadmin@ilryu.com",
        name="Company Admin",
        role=UserRole.COMPANY_ADMIN,
        company_id=test_company.id,
    )


@pytest_asyncio.fixture
async def order_handler(
    db_session: AsyncSession, test_company: Company
) -> User:
    """Create an order_handler user."""
    return await create_test_user(
        db_session,
        email="handler@ilryu.com",
        name="Order Handler",
        role=UserRole.ORDER_HANDLER,
        company_id=test_company.id,
    )


@pytest_asyncio.fixture
async def distributor(
    db_session: AsyncSession, test_company: Company
) -> User:
    """Create a distributor user."""
    return await create_test_user(
        db_session,
        email="dist@ilryu.com",
        name="Distributor",
        role=UserRole.DISTRIBUTOR,
        company_id=test_company.id,
    )


@pytest_asyncio.fixture
async def sub_account(
    db_session: AsyncSession, test_company: Company, distributor: User
) -> User:
    """Create a sub_account user under a distributor."""
    return await create_test_user(
        db_session,
        email="sub@ilryu.com",
        name="Sub Account",
        role=UserRole.SUB_ACCOUNT,
        company_id=test_company.id,
        parent_id=distributor.id,
    )

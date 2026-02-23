"""SQLAlchemy 2.0 async database engine and session for keyword-worker.

Connects to the same PostgreSQL database as api-server.
Uses the same Base and model definitions.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models.

    keyword-worker defines its own Base for DB access,
    but operates on the same tables created by api-server's Alembic migrations.
    """

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

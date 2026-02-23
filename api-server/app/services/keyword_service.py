"""Keyword service: queries for keywords and rank history."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.keyword import Keyword
from app.models.keyword_rank_history import KeywordRankHistory


async def get_keywords_for_place(
    db: AsyncSession,
    place_id: int,
    skip: int = 0,
    limit: int = 50,
    keyword_type: str | None = None,
) -> tuple[list[Keyword], int]:
    """Get paginated keywords for a place."""
    query = select(Keyword).where(Keyword.place_id == place_id)
    count_query = select(func.count()).select_from(Keyword).where(
        Keyword.place_id == place_id
    )

    if keyword_type:
        query = query.where(Keyword.keyword_type == keyword_type)
        count_query = count_query.where(Keyword.keyword_type == keyword_type)

    query = query.order_by(Keyword.current_rank.asc().nullslast()).offset(skip).limit(limit)

    result = await db.execute(query)
    keywords = list(result.scalars().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    return keywords, total


async def get_rank_history(
    db: AsyncSession,
    keyword_id: int,
    skip: int = 0,
    limit: int = 30,
) -> tuple[list[KeywordRankHistory], int]:
    """Get rank history for a keyword."""
    query = (
        select(KeywordRankHistory)
        .where(KeywordRankHistory.keyword_id == keyword_id)
        .order_by(KeywordRankHistory.recorded_date.desc())
        .offset(skip)
        .limit(limit)
    )
    count_query = (
        select(func.count())
        .select_from(KeywordRankHistory)
        .where(KeywordRankHistory.keyword_id == keyword_id)
    )

    result = await db.execute(query)
    history = list(result.scalars().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    return history, total

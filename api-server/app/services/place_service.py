"""Place service: CRUD operations for places."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.place import Place
from app.schemas.place import PlaceCreate, PlaceUpdate


async def get_places(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    place_type: str | None = None,
    gu: str | None = None,
    major_area: str | None = None,
    company_id: int | None = None,
) -> tuple[list[Place], int]:
    """Get paginated list of places."""
    query = select(Place)
    count_query = select(func.count()).select_from(Place)

    if place_type:
        query = query.where(Place.place_type == place_type)
        count_query = count_query.where(Place.place_type == place_type)
    if gu:
        query = query.where(Place.gu == gu)
        count_query = count_query.where(Place.gu == gu)
    if major_area:
        query = query.where(Place.major_area == major_area)
        count_query = count_query.where(Place.major_area == major_area)

    query = query.order_by(Place.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    places = list(result.scalars().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    return places, total


async def get_place_by_id(db: AsyncSession, place_id: int) -> Place | None:
    """Get a single place by Naver Place ID."""
    result = await db.execute(select(Place).where(Place.id == place_id))
    return result.scalar_one_or_none()


async def create_or_update_place(
    db: AsyncSession, data: PlaceCreate
) -> Place:
    """Create or update a place (UPSERT by naver place ID)."""
    existing = await get_place_by_id(db, data.id)

    if existing:
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(existing, key, value)
        existing.last_scraped_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(existing)
        return existing

    place = Place(
        **data.model_dump(),
        last_scraped_at=datetime.now(timezone.utc),
    )
    db.add(place)
    await db.flush()
    await db.refresh(place)
    return place


async def update_place(
    db: AsyncSession, place: Place, data: PlaceUpdate
) -> Place:
    """Update an existing place with partial data."""
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(place, key, value)
    await db.flush()
    await db.refresh(place)
    return place

"""Places router: CRUD for Naver Place data."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.keyword import KeywordResponse
from app.schemas.place import PlaceResponse
from app.services import keyword_service, place_service

router = APIRouter(prefix="/places", tags=["places"])


@router.get("/", response_model=PaginatedResponse[PlaceResponse])
async def list_places(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    place_type: str | None = None,
    gu: str | None = None,
    major_area: str | None = None,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
):
    """List places with pagination and filtering."""
    pagination = PaginationParams(page=page, size=size)
    places, total = await place_service.get_places(
        db,
        skip=pagination.offset,
        limit=pagination.size,
        place_type=place_type,
        gu=gu,
        major_area=major_area,
    )
    return PaginatedResponse.create(
        items=[PlaceResponse.model_validate(p) for p in places],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.get("/{place_id}", response_model=PlaceResponse)
async def get_place(
    place_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
):
    """Get a single place by Naver Place ID."""
    place = await place_service.get_place_by_id(db, place_id)
    if place is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Place not found",
        )
    return place


@router.get(
    "/{place_id}/keywords",
    response_model=PaginatedResponse[KeywordResponse],
)
async def list_place_keywords(
    place_id: int,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    keyword_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
):
    """List keywords for a place."""
    place = await place_service.get_place_by_id(db, place_id)
    if place is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Place not found",
        )

    pagination = PaginationParams(page=page, size=size)
    keywords, total = await keyword_service.get_keywords_for_place(
        db,
        place_id=place_id,
        skip=pagination.offset,
        limit=pagination.size,
        keyword_type=keyword_type,
    )
    return PaginatedResponse.create(
        items=[KeywordResponse.model_validate(k) for k in keywords],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )

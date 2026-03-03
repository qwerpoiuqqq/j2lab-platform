"""Places router: CRUD for Naver Place data + AI recommendation."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.schemas.assignment import PlaceRecommendation, PlaceRecommendationV2
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.keyword import KeywordResponse
from app.schemas.place import PlaceResponse
from app.services import assignment_service, keyword_service, place_service

router = APIRouter(prefix="/places", tags=["places"])


def _parse_place_id_from_url(url: str) -> int | None:
    """Extract numeric MID (place_id) from a Naver Place URL."""
    # Patterns: /restaurant/12345, /place/12345, m.place.naver.com/...12345
    match = re.search(r"/(\d{5,15})", url)
    if match:
        return int(match.group(1))
    return None


@router.get("/recommend")
async def get_recommendation(
    place_url: str = Query(..., description="Naver Place URL"),
    company_id: int = Query(..., description="Company ID for network lookup"),
    campaign_type: str | None = Query(default=None, description="traffic or save (None for both)"),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
) -> PlaceRecommendation | PlaceRecommendationV2:
    """Get AI recommendation for a place URL at order time.

    If campaign_type is specified, returns PlaceRecommendation (V1, backward compat).
    If campaign_type is None, returns PlaceRecommendationV2 (both traffic and save).
    """
    place_id = _parse_place_id_from_url(place_url)
    if place_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL에서 플레이스 ID를 추출할 수 없습니다.",
        )

    if campaign_type is not None:
        # V1: single type recommendation (backward compatible)
        recommendation = await assignment_service.get_recommendation(
            db,
            place_id=place_id,
            campaign_type=campaign_type,
            company_id=company_id,
        )
        return recommendation

    # V2: bidirectional recommendation (both traffic and save)
    recommendation_v2 = await assignment_service.get_recommendation_both(
        db,
        place_id=place_id,
        company_id=company_id,
    )
    return recommendation_v2


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

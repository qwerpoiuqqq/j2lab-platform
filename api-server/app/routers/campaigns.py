"""Campaigns router: CRUD + status management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import RoleChecker, get_current_active_user
from app.models.user import User, UserRole
from app.schemas.campaign import (
    CampaignCreate,
    CampaignKeywordAddRequest,
    CampaignKeywordPoolResponse,
    CampaignResponse,
    CampaignUpdate,
)
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.services import campaign_service

router = APIRouter(prefix="/campaigns", tags=["campaigns"])

admin_checker = RoleChecker([
    UserRole.SYSTEM_ADMIN,
    UserRole.COMPANY_ADMIN,
    UserRole.ORDER_HANDLER,
])


@router.get("/", response_model=PaginatedResponse[CampaignResponse])
async def list_campaigns(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    company_id: int | None = None,
    place_id: int | None = None,
    campaign_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List campaigns with filtering."""
    pagination = PaginationParams(page=page, size=size)

    # Company-scoped for non-system_admin
    effective_company_id = company_id
    if UserRole(current_user.role) != UserRole.SYSTEM_ADMIN:
        effective_company_id = current_user.company_id

    campaigns, total = await campaign_service.get_campaigns(
        db,
        skip=pagination.offset,
        limit=pagination.size,
        status=status_filter,
        company_id=effective_company_id,
        place_id=place_id,
        campaign_type=campaign_type,
    )
    return PaginatedResponse.create(
        items=[CampaignResponse.model_validate(c) for c in campaigns],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.post(
    "/",
    response_model=CampaignResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_campaign(
    body: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Create a new campaign."""
    campaign = await campaign_service.create_campaign(db, body)
    return campaign


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
):
    """Get campaign details."""
    campaign = await campaign_service.get_campaign_by_id(db, campaign_id)
    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )
    return campaign


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: int,
    body: CampaignUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Update a campaign."""
    campaign = await campaign_service.get_campaign_by_id(db, campaign_id)
    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )
    updated = await campaign_service.update_campaign(db, campaign, body)
    return updated


@router.get(
    "/{campaign_id}/keywords",
    response_model=PaginatedResponse[CampaignKeywordPoolResponse],
)
async def list_campaign_keywords(
    campaign_id: int,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=100, ge=1, le=500),
    is_used: bool | None = None,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
):
    """Get keywords in a campaign's rotation pool."""
    campaign = await campaign_service.get_campaign_by_id(db, campaign_id)
    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )

    skip = (page - 1) * size
    keywords, total = await campaign_service.get_keyword_pool(
        db,
        campaign_id=campaign_id,
        skip=skip,
        limit=size,
        is_used=is_used,
    )
    return PaginatedResponse.create(
        items=[CampaignKeywordPoolResponse.model_validate(k) for k in keywords],
        total=total,
        page=page,
        size=size,
    )


@router.post(
    "/{campaign_id}/keywords",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_campaign_keywords(
    campaign_id: int,
    body: CampaignKeywordAddRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Add keywords to a campaign's rotation pool."""
    campaign = await campaign_service.get_campaign_by_id(db, campaign_id)
    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )

    added = await campaign_service.add_keywords_to_pool(
        db,
        campaign_id=campaign_id,
        keywords=body.keywords,
        round_number=body.round_number,
    )
    return MessageResponse(
        message=f"Added {added} keywords to campaign pool",
        detail={"added": added, "total_requested": len(body.keywords)},
    )

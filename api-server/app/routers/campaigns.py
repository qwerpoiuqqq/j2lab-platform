"""Campaigns router: CRUD + status management + upload + manual."""

from __future__ import annotations

import io
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
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


# --- Pydantic models for new endpoints ---

class ManualCampaignCreate(BaseModel):
    campaign_code: str
    account_id: int
    place_url: str
    place_name: str | None = None
    template_id: int
    start_date: str
    end_date: str
    daily_limit: int
    keywords: str


class BatchDeleteRequest(BaseModel):
    ids: List[int]


class UploadConfirmRequest(BaseModel):
    items: List[int]

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


# =====================================================================
# Manual campaign creation
# =====================================================================


@router.post("/manual", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_manual_campaign(
    body: ManualCampaignCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Manually create a campaign with a known campaign code."""
    campaign_data = CampaignCreate(
        campaign_code=body.campaign_code,
        superap_account_id=body.account_id,
        place_url=body.place_url,
        place_name=body.place_name or "",
        campaign_type="manual",
        start_date=body.start_date,
        end_date=body.end_date,
        daily_limit=body.daily_limit,
    )
    campaign = await campaign_service.create_campaign(db, campaign_data)

    # Add keywords
    if body.keywords:
        kw_list = [k.strip() for k in body.keywords.split(",") if k.strip()]
        if kw_list:
            await campaign_service.add_keywords_to_pool(
                db, campaign_id=campaign.id, keywords=kw_list, round_number=1
            )

    return campaign


@router.get("/manual/verify/{code}")
async def verify_campaign_code(
    code: str,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Check if a campaign code already exists."""
    existing = await campaign_service.get_campaign_by_code(db, code)
    if existing:
        return {"exists": True, "campaign_id": existing.id}
    return {"exists": False}


# =====================================================================
# Delete / Batch delete
# =====================================================================


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Delete a campaign."""
    campaign = await campaign_service.get_campaign_by_id(db, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    await campaign_service.delete_campaign(db, campaign)


@router.post("/batch/delete", response_model=MessageResponse)
async def batch_delete_campaigns(
    body: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Delete multiple campaigns."""
    deleted = 0
    for cid in body.ids:
        campaign = await campaign_service.get_campaign_by_id(db, cid)
        if campaign:
            await campaign_service.delete_campaign(db, campaign)
            deleted += 1
    return MessageResponse(message=f"Deleted {deleted} campaigns")


# =====================================================================
# Sync / Retry
# =====================================================================


@router.post("/{campaign_id}/sync", response_model=MessageResponse)
async def sync_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Sync campaign settings to superap.io (stub)."""
    campaign = await campaign_service.get_campaign_by_id(db, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return MessageResponse(message="Sync queued (stub)")


@router.post("/registration/retry", response_model=MessageResponse)
async def retry_registration(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Retry a failed campaign registration (stub)."""
    return MessageResponse(message="Retry queued (stub)")


@router.get("/registration/progress")
async def get_registration_progress(
    _current_user: User = Depends(admin_checker),
):
    """Get current registration progress (stub)."""
    return {"items": []}


# =====================================================================
# Upload preview / confirm / template
# =====================================================================


@router.post("/upload/preview")
async def upload_preview(
    file: UploadFile = File(...),
    _current_user: User = Depends(admin_checker),
):
    """Preview campaign Excel upload (stub - returns empty for now)."""
    return {"items": [], "total": 0, "valid_count": 0, "error_count": 0}


@router.post("/upload/confirm", response_model=MessageResponse)
async def upload_confirm(
    body: UploadConfirmRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Confirm and register campaigns from upload (stub)."""
    return MessageResponse(message=f"Registered {len(body.items)} campaigns (stub)")


@router.get("/upload/template")
async def download_upload_template():
    """Download campaign upload Excel template."""
    try:
        from openpyxl import Workbook
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl not installed")

    wb = Workbook()
    ws = wb.active
    ws.title = "캠페인 등록"
    headers = ["대행사", "계정ID", "플레이스URL", "상호명", "캠페인타입", "시작일", "종료일", "일일한도", "키워드"]
    ws.append(headers)
    ws.append(["일류기획", "user1", "https://naver.me/xxx", "카페A", "저장하기", "2026-03-01", "2026-03-31", 5, "키워드1,키워드2,키워드3"])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=campaign_template.xlsx"},
    )

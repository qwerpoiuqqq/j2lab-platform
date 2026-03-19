"""Campaigns router: CRUD + status management + upload + manual."""

from __future__ import annotations

import io
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import RoleChecker, get_current_active_user
from app.models.campaign import Campaign
from app.models.user import User, UserRole
from app.schemas.campaign import (
    CampaignCreate,
    CampaignKeywordAddRequest,
    CampaignKeywordPoolResponse,
    CampaignResponse,
    CampaignUpdate,
    ExtendCampaignRequest,
)
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.services import campaign_service
from app.services.campaign_upload_service import (
    create_campaigns_from_upload,
    detect_extension,
    parse_excel,
    validate_row,
)
from app.services.worker_clients import (
    WorkerDispatchError,
    dispatch_campaign_bulk_sync,
    dispatch_campaign_extension,
    dispatch_campaign_registration,
    dispatch_keyword_rotation,
)

logger = logging.getLogger(__name__)

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
    agency_name: str | None = None


class BatchDeleteRequest(BaseModel):
    ids: List[int]


class UploadConfirmRequest(BaseModel):
    items: List[dict]


class RetryRegistrationRequest(BaseModel):
    campaign_id: int


admin_checker = RoleChecker([
    UserRole.SYSTEM_ADMIN,
    UserRole.COMPANY_ADMIN,
    UserRole.ORDER_HANDLER,
])

# Roles that must NOT see hidden margin details
_MASKED_ROLES = {UserRole.DISTRIBUTOR, UserRole.SUB_ACCOUNT}


def _mask_campaign_for_role(campaign: Campaign, user_role: UserRole) -> CampaignResponse:
    """Return CampaignResponse with limits masked for distributor/sub_account.

    총판/하부 계정에게는 실제 세팅값(감은 후) 대신 원래 접수 타수를 반환한다.
    감은 사실 자체를 절대 노출하지 않는다.
    """
    resp = CampaignResponse.model_validate(campaign)
    if user_role in _MASKED_ROLES:
        # original_*_limit가 있으면 해당 값으로 교체 (감기 전 원래 타수)
        if campaign.original_daily_limit is not None:
            resp.daily_limit = campaign.original_daily_limit
        if campaign.original_total_limit is not None:
            resp.total_limit = campaign.original_total_limit
        # 감은 비율 관련 필드 숨김
        resp.original_daily_limit = None
        resp.original_total_limit = None
    return resp


# =====================================================================
# Literal routes FIRST (before /{campaign_id} parameterized routes)
# =====================================================================


@router.get("/", response_model=PaginatedResponse[CampaignResponse])
async def list_campaigns(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    company_id: int | None = None,
    place_id: int | None = None,
    campaign_type: str | None = None,
    account_id: int | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List campaigns with filtering."""
    pagination = PaginationParams(page=page, size=size)

    # Role-based scoping
    effective_company_id = company_id
    managed_by_id = None
    user_role = UserRole(current_user.role)
    if user_role == UserRole.ORDER_HANDLER:
        # order_handler: 본인 담당 캠페인만
        managed_by_id = current_user.id
        effective_company_id = current_user.company_id
    elif user_role != UserRole.SYSTEM_ADMIN:
        effective_company_id = current_user.company_id

    campaigns, total = await campaign_service.get_campaigns(
        db,
        skip=pagination.offset,
        limit=pagination.size,
        status=status_filter,
        company_id=effective_company_id,
        place_id=place_id,
        campaign_type=campaign_type,
        managed_by=managed_by_id,
        account_id=account_id,
        search=search,
    )
    return PaginatedResponse.create(
        items=[_mask_campaign_for_role(c, user_role) for c in campaigns],
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


# =====================================================================
# Manual campaign creation (literal routes)
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
        agency_name=body.agency_name,
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
# Batch delete (literal route)
# =====================================================================


@router.post("/batch/delete", response_model=MessageResponse)
async def batch_delete_campaigns(
    body: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Delete multiple campaigns."""
    deleted = 0
    errors = []
    for cid in body.ids:
        campaign = await campaign_service.get_campaign_by_id(db, cid)
        if campaign:
            try:
                await campaign_service.delete_campaign(db, campaign)
                deleted += 1
            except ValueError as e:
                errors.append(f"Campaign {cid}: {str(e)}")
    return MessageResponse(
        message=f"Deleted {deleted} campaigns",
        detail={"errors": errors} if errors else None,
    )


# =====================================================================
# Registration retry / progress (literal routes)
# =====================================================================


@router.post("/registration/retry", response_model=MessageResponse)
async def retry_registration(
    body: RetryRegistrationRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Retry a failed campaign registration."""
    campaign = await campaign_service.get_campaign_by_id(db, body.campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    if campaign.status != "failed" and not (
        campaign.status == "pending" and campaign.registration_step == "failed"
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Campaign is not in a failed state",
        )
    try:
        await dispatch_campaign_registration(campaign_id=campaign.id)
    except WorkerDispatchError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    return MessageResponse(message="Registration retry dispatched")


@router.get("/registration/progress")
async def get_registration_progress(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Get current registration progress for campaigns being registered."""
    result = await db.execute(
        select(Campaign).where(
            Campaign.status.in_(["pending", "queued", "registering"]),
            Campaign.registration_step.isnot(None),
        ).order_by(Campaign.created_at.desc())
    )
    campaigns = result.scalars().all()
    items = [
        {
            "campaign_id": c.id,
            "place_name": c.place_name,
            "status": c.status,
            "registration_step": c.registration_step,
            "registration_message": c.registration_message,
            "campaign_code": c.campaign_code,
        }
        for c in campaigns
    ]
    return {"items": items}


# =====================================================================
# Upload preview / confirm / template (literal routes)
# =====================================================================


@router.post("/upload/preview")
async def upload_preview(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Preview campaign Excel upload with validation."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    try:
        headers, rows = parse_excel(content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse Excel file: {e}",
        )

    if not rows:
        return {"items": [], "total": 0, "valid_count": 0, "error_count": 0}

    items = []
    valid_count = 0
    error_count = 0

    for i, row in enumerate(rows):
        row_number = i + 2  # Excel row (1-indexed header + 1-indexed data)
        normalized, errors = validate_row(row, row_number)

        # Check extension eligibility
        extension_eligible = False
        existing_campaign_id = None
        existing_campaign_code = None
        if not errors and normalized["place_url"] and normalized["campaign_type"]:
            extension_eligible, existing_campaign_id, existing_campaign_code = (
                await detect_extension(db, normalized["place_url"], normalized["campaign_type"])
            )

        is_valid = len(errors) == 0
        if is_valid:
            valid_count += 1
        else:
            error_count += 1

        items.append({
            "row_number": row_number,
            "agency_name": normalized.get("agency_name", ""),
            "user_id": normalized.get("account_user_id", ""),
            "start_date": normalized.get("start_date", ""),
            "end_date": normalized.get("end_date", ""),
            "daily_limit": normalized.get("daily_limit", 0),
            "keywords": normalized.get("keywords", []),
            "keyword_count": len(normalized.get("keywords", [])),
            "place_name": normalized.get("place_name", ""),
            "place_url": normalized.get("place_url", ""),
            "campaign_type": normalized.get("campaign_type", ""),
            "is_valid": is_valid,
            "errors": errors,
            "extension_eligible": extension_eligible,
            "existing_campaign_code": existing_campaign_code,
            "existing_campaign_id": existing_campaign_id,
        })

    return {
        "items": items,
        "total": len(items),
        "valid_count": valid_count,
        "error_count": error_count,
    }


@router.post("/upload/confirm", response_model=MessageResponse)
async def upload_confirm(
    body: UploadConfirmRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Confirm and create campaigns from validated upload data."""
    if not body.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No items to confirm",
        )
    results = await create_campaigns_from_upload(db, body.items)
    created = sum(1 for r in results if "campaign_id" in r)
    failed = sum(1 for r in results if "error" in r)
    return MessageResponse(
        message=f"Created {created} campaigns ({failed} failed)",
        detail={"results": results},
    )


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


# =====================================================================
# Parameterized routes (/{campaign_id}) AFTER all literal routes
# =====================================================================


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get campaign details."""
    campaign = await campaign_service.get_campaign_by_id(db, campaign_id)
    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )
    user_role = UserRole(current_user.role)
    return _mask_campaign_for_role(campaign, user_role)


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
    try:
        await campaign_service.delete_campaign(db, campaign)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


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
# Register / Extend / Rotate Keywords / Sync (parameterized)
# =====================================================================


@router.post("/{campaign_id}/register", response_model=MessageResponse)
async def register_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Dispatch campaign registration to campaign-worker."""
    campaign = await campaign_service.get_campaign_by_id(db, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    if campaign.status not in ("pending", "failed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Campaign status '{campaign.status}' is not eligible for registration",
        )
    try:
        await dispatch_campaign_registration(campaign_id=campaign.id)
    except WorkerDispatchError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    return MessageResponse(message="Registration dispatched")


@router.post("/{campaign_id}/extend", response_model=MessageResponse)
async def extend_campaign(
    campaign_id: int,
    body: ExtendCampaignRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Extend an active campaign's end date and total."""
    campaign = await campaign_service.get_campaign_by_id(db, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    if campaign.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Campaign status '{campaign.status}' is not eligible for extension (must be active)",
        )
    try:
        await dispatch_campaign_extension(
            campaign_id=campaign.id,
            new_end_date=body.new_end_date.isoformat(),
            additional_total=body.additional_total,
            new_daily_limit=body.new_daily_limit,
        )
    except WorkerDispatchError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    return MessageResponse(message="Extension dispatched")


@router.post("/{campaign_id}/rotate-keywords", response_model=MessageResponse)
async def rotate_campaign_keywords(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Dispatch keyword rotation for an active campaign."""
    campaign = await campaign_service.get_campaign_by_id(db, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    if campaign.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Campaign status '{campaign.status}' is not eligible for keyword rotation (must be active)",
        )
    try:
        await dispatch_keyword_rotation(campaign_id=campaign.id)
    except WorkerDispatchError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    return MessageResponse(message="Keyword rotation dispatched")


@router.post("/{campaign_id}/sync", response_model=MessageResponse)
async def sync_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Sync a single campaign's status from superap.io."""
    campaign = await campaign_service.get_campaign_by_id(db, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    try:
        await dispatch_campaign_bulk_sync(account_ids=[campaign.superap_account_id] if campaign.superap_account_id else None)
        return MessageResponse(message=f"Sync dispatched for campaign {campaign_id}")
    except WorkerDispatchError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Worker communication failed: {str(e)}")

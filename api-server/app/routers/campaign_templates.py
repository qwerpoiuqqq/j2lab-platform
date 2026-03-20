"""Campaign templates router: read + update for templates."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import RoleChecker, get_current_active_user
from app.models.user import User, UserRole
from app.schemas.campaign_template import CampaignTemplateCreate, CampaignTemplateResponse, CampaignTemplateUpdate
from app.schemas.common import PaginatedResponse, PaginationParams
from app.services import campaign_template_service

router = APIRouter(prefix="/templates", tags=["campaign-templates"])

system_admin_checker = RoleChecker([UserRole.SYSTEM_ADMIN])
template_reader_checker = RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN])


@router.get("/", response_model=PaginatedResponse[CampaignTemplateResponse])
async def list_templates(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=100),
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(template_reader_checker),
):
    """List campaign templates.

    - system_admin: full read access
    - company_admin: read-only access to the shared template catalog
    """
    pagination = PaginationParams(page=page, size=size)
    templates, total = await campaign_template_service.get_templates(
        db,
        skip=pagination.offset,
        limit=pagination.size,
        is_active=is_active,
    )
    return PaginatedResponse.create(
        items=[CampaignTemplateResponse.model_validate(t) for t in templates],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.post(
    "/",
    response_model=CampaignTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_template(
    body: CampaignTemplateCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(system_admin_checker),
):
    """Create a new campaign template (system_admin only)."""
    try:
        template = await campaign_template_service.create_template(db, body)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Template with type_name '{body.type_name}' or code already exists",
        )
    return template


@router.get("/modules")
async def list_modules(
    _current_user: User = Depends(get_current_active_user),
):
    """List available campaign modules and their variables."""
    return {
        "modules": [
            {
                "name": "place_info",
                "description": "플레이스 실제 상호명/주소 추출",
                "variables": ["상호명", "가게주소"],
            },
            {
                "name": "landmark",
                "description": "플레이스 주변 명소 선택",
                "variables": ["명소명", "명소순번"],
            },
            {
                "name": "steps",
                "description": "출발지→업체 도보 걸음수 계산",
                "variables": ["걸음수"],
            },
        ]
    }


@router.get("/{template_id}", response_model=CampaignTemplateResponse)
async def get_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(template_reader_checker),
):
    """Get a single template by ID."""
    template = await campaign_template_service.get_template_by_id(db, template_id)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign template not found",
        )
    return template


@router.patch("/{template_id}", response_model=CampaignTemplateResponse)
async def update_template(
    template_id: int,
    body: CampaignTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(system_admin_checker),
):
    """Update a campaign template (system_admin only)."""
    template = await campaign_template_service.get_template_by_id(db, template_id)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign template not found",
        )
    updated = await campaign_template_service.update_template(db, template, body)
    return updated


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(system_admin_checker),
):
    """Delete a campaign template (system_admin only)."""
    template = await campaign_template_service.get_template_by_id(db, template_id)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign template not found",
        )
    await campaign_template_service.delete_template(db, template)

"""Notices router: CRUD for company-wide announcements."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import RoleChecker, get_current_active_user
from app.models.user import User, UserRole
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.notice import NoticeCreate, NoticeResponse, NoticeUpdate
from app.services import notice_service

router = APIRouter(prefix="/notices", tags=["notices"])

admin_checker = RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN])
system_admin_checker = RoleChecker([UserRole.SYSTEM_ADMIN])


@router.get("/", response_model=PaginatedResponse[NoticeResponse])
async def list_notices(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
):
    """List active notices. Available to all authenticated users."""
    pagination = PaginationParams(page=page, size=size)
    notices, total = await notice_service.get_notices(
        db, skip=pagination.offset, limit=pagination.size,
    )
    return PaginatedResponse.create(
        items=[_notice_to_response(n) for n in notices],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.post(
    "/",
    response_model=NoticeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_notice(
    body: NoticeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_checker),
):
    """Create a new notice (system_admin, company_admin)."""
    notice = await notice_service.create_notice(db, body, author_id=current_user.id)
    return _notice_to_response(notice)


@router.put("/{notice_id}", response_model=NoticeResponse)
async def update_notice(
    notice_id: int,
    body: NoticeUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(admin_checker),
):
    """Update a notice (system_admin, company_admin)."""
    notice = await notice_service.get_notice_by_id(db, notice_id)
    if notice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notice not found",
        )
    updated = await notice_service.update_notice(db, notice, body)
    return _notice_to_response(updated)


@router.delete("/{notice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notice(
    notice_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(system_admin_checker),
):
    """Delete a notice (system_admin only)."""
    notice = await notice_service.get_notice_by_id(db, notice_id)
    if notice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notice not found",
        )
    await notice_service.delete_notice(db, notice)


def _notice_to_response(notice) -> NoticeResponse:
    """Convert Notice model to NoticeResponse, extracting author name."""
    data = NoticeResponse.model_validate(notice)
    if notice.author:
        data.author_name = notice.author.name
    return data

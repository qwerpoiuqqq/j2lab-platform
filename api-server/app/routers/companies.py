"""Companies router: CRUD for company/tenant management (system_admin only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import RoleChecker
from app.models.user import User, UserRole
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.company import CompanyCreate, CompanyResponse, CompanyUpdate
from app.services import company_service

router = APIRouter(prefix="/companies", tags=["companies"])

# system_admin only for all company operations
system_admin_checker = RoleChecker([UserRole.SYSTEM_ADMIN])


@router.get("/", response_model=PaginatedResponse[CompanyResponse])
async def list_companies(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(system_admin_checker),
):
    """List all companies with pagination (system_admin only)."""
    pagination = PaginationParams(page=page, size=size)
    companies, total = await company_service.get_companies(
        db, skip=pagination.offset, limit=pagination.size, is_active=is_active
    )
    return PaginatedResponse.create(
        items=[CompanyResponse.model_validate(c) for c in companies],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.post(
    "/",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_company(
    body: CompanyCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(system_admin_checker),
):
    """Create a new company (system_admin only)."""
    # Check for duplicate code
    existing = await company_service.get_company_by_code(db, body.code)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Company with code '{body.code}' already exists",
        )
    company = await company_service.create_company(db, body)
    return company


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(system_admin_checker),
):
    """Get a single company by ID (system_admin only)."""
    company = await company_service.get_company_by_id(db, company_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )
    return company


@router.patch("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: int,
    body: CompanyUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(system_admin_checker),
):
    """Update a company (system_admin only)."""
    company = await company_service.get_company_by_id(db, company_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    # Check for duplicate code if updating code
    if body.code is not None and body.code != company.code:
        existing = await company_service.get_company_by_code(db, body.code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Company with code '{body.code}' already exists",
            )

    updated = await company_service.update_company(db, company, body)
    return updated


@router.delete("/{company_id}", response_model=MessageResponse)
async def delete_company(
    company_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(system_admin_checker),
):
    """Soft-delete a company (set is_active=False). system_admin only."""
    company = await company_service.get_company_by_id(db, company_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )
    await company_service.delete_company(db, company)
    return MessageResponse(message=f"Company '{company.name}' has been deactivated")

"""Categories router: CRUD + reorder for product categories."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import RoleChecker, get_current_active_user
from app.models.user import User, UserRole
from app.schemas.category import (
    CategoryCreate,
    CategoryReorderRequest,
    CategoryResponse,
    CategoryUpdate,
)
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.services import category_service

router = APIRouter(prefix="/categories", tags=["categories"])

system_admin_checker = RoleChecker([UserRole.SYSTEM_ADMIN])


@router.get("/", response_model=PaginatedResponse[CategoryResponse])
async def list_categories(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
):
    """List categories. Available to all authenticated users."""
    pagination = PaginationParams(page=page, size=size)
    categories, total = await category_service.get_categories(
        db, skip=pagination.offset, limit=pagination.size,
    )
    return PaginatedResponse.create(
        items=[CategoryResponse.model_validate(c) for c in categories],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.post(
    "/",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    body: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(system_admin_checker),
):
    """Create a new category (system_admin only)."""
    category = await category_service.create_category(db, body)
    return CategoryResponse.model_validate(category)


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    body: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(system_admin_checker),
):
    """Update a category (system_admin only)."""
    category = await category_service.get_category_by_id(db, category_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )
    updated = await category_service.update_category(db, category, body)
    return CategoryResponse.model_validate(updated)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(system_admin_checker),
):
    """Delete a category (system_admin only)."""
    category = await category_service.get_category_by_id(db, category_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )
    await category_service.delete_category(db, category)


@router.post("/reorder", response_model=list[CategoryResponse])
async def reorder_categories(
    body: CategoryReorderRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(system_admin_checker),
):
    """Reorder categories by updating sort_order (system_admin only)."""
    updated = await category_service.reorder_categories(db, body.items)
    return [CategoryResponse.model_validate(c) for c in updated]

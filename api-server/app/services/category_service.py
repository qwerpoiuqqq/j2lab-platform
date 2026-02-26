"""Category service: CRUD operations for product categories."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryReorderItem, CategoryUpdate


async def get_categories(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
) -> tuple[list[Category], int]:
    """Get paginated list of categories ordered by sort_order."""
    query = select(Category)
    count_query = select(func.count()).select_from(Category)

    if active_only:
        query = query.where(Category.is_active == True)
        count_query = count_query.where(Category.is_active == True)

    query = query.order_by(Category.sort_order, Category.id).offset(skip).limit(limit)

    result = await db.execute(query)
    items = list(result.scalars().all())

    total = (await db.execute(count_query)).scalar_one()

    return items, total


async def get_category_by_id(
    db: AsyncSession,
    category_id: int,
) -> Category | None:
    """Get a single category by ID."""
    result = await db.execute(
        select(Category).where(Category.id == category_id)
    )
    return result.scalar_one_or_none()


async def create_category(
    db: AsyncSession,
    data: CategoryCreate,
) -> Category:
    """Create a new category."""
    category = Category(
        name=data.name,
        description=data.description,
        sort_order=data.sort_order,
        is_active=data.is_active,
    )
    db.add(category)
    await db.flush()
    await db.refresh(category)
    return category


async def update_category(
    db: AsyncSession,
    category: Category,
    data: CategoryUpdate,
) -> Category:
    """Update an existing category with partial data."""
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(category, key, value)
    await db.flush()
    await db.refresh(category)
    return category


async def delete_category(
    db: AsyncSession,
    category: Category,
) -> None:
    """Delete a category."""
    await db.delete(category)
    await db.flush()


async def reorder_categories(
    db: AsyncSession,
    items: list[CategoryReorderItem],
) -> list[Category]:
    """Reorder categories by updating sort_order for each."""
    updated = []
    for item in items:
        result = await db.execute(
            select(Category).where(Category.id == item.id)
        )
        category = result.scalar_one_or_none()
        if category is not None:
            category.sort_order = item.sort_order
            updated.append(category)

    await db.flush()
    for cat in updated:
        await db.refresh(cat)

    return updated

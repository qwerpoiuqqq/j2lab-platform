"""Product service: CRUD operations for products."""

from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate


def _generate_code(name: str) -> str:
    """Generate a URL-safe code from product name."""
    # Replace whitespace with underscore, remove special chars, lowercase
    code = re.sub(r"\s+", "_", name.strip())
    code = re.sub(r"[^a-zA-Z0-9가-힣_]", "", code)
    return code[:50].lower() or "product"


async def get_products(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    is_active: bool | None = None,
    category: str | None = None,
) -> tuple[list[Product], int]:
    """Get paginated list of products with total count."""
    query = select(Product)
    count_query = select(func.count()).select_from(Product)

    if is_active is not None:
        query = query.where(Product.is_active == is_active)
        count_query = count_query.where(Product.is_active == is_active)
    if category is not None:
        query = query.where(Product.category == category)
        count_query = count_query.where(Product.category == category)

    query = query.order_by(Product.id).offset(skip).limit(limit)

    result = await db.execute(query)
    products = list(result.scalars().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    return products, total


async def get_product_by_id(
    db: AsyncSession,
    product_id: int,
) -> Product | None:
    """Get a single product by ID."""
    result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    return result.scalar_one_or_none()


async def get_product_by_code(
    db: AsyncSession,
    code: str,
) -> Product | None:
    """Get a single product by code."""
    result = await db.execute(
        select(Product).where(Product.code == code)
    )
    return result.scalar_one_or_none()


async def create_product(
    db: AsyncSession,
    data: ProductCreate,
) -> Product:
    """Create a new product."""
    product = Product(
        name=data.name,
        code=data.code or _generate_code(data.name),
        category=data.category,
        description=data.description,
        form_schema=data.form_schema,
        base_price=data.base_price,
        cost_price=data.cost_price,
        reduction_rate=data.reduction_rate,
        min_work_days=data.min_work_days,
        max_work_days=data.max_work_days,
        min_daily_limit=data.min_daily_limit,
        daily_deadline=data.daily_deadline,
        deadline_timezone=data.deadline_timezone,
        setup_delay_minutes=data.setup_delay_minutes,
        is_active=data.is_active,
    )
    db.add(product)
    await db.flush()
    await db.refresh(product)
    return product


async def update_product(
    db: AsyncSession,
    product: Product,
    data: ProductUpdate,
) -> Product:
    """Update an existing product with partial data."""
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(product, key, value)
    await db.flush()
    await db.refresh(product)
    return product


async def delete_product(db: AsyncSession, product: Product) -> None:
    """Hard-delete a product from the database."""
    await db.delete(product)
    await db.flush()

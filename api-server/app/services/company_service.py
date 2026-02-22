"""Company service: CRUD operations for companies."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.schemas.company import CompanyCreate, CompanyUpdate


async def get_companies(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    is_active: bool | None = None,
) -> tuple[list[Company], int]:
    """Get paginated list of companies with total count."""
    query = select(Company)
    count_query = select(func.count()).select_from(Company)

    if is_active is not None:
        query = query.where(Company.is_active == is_active)
        count_query = count_query.where(Company.is_active == is_active)

    query = query.order_by(Company.id).offset(skip).limit(limit)

    result = await db.execute(query)
    companies = list(result.scalars().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    return companies, total


async def get_company_by_id(
    db: AsyncSession,
    company_id: int,
) -> Company | None:
    """Get a single company by ID."""
    result = await db.execute(
        select(Company).where(Company.id == company_id)
    )
    return result.scalar_one_or_none()


async def get_company_by_code(
    db: AsyncSession,
    code: str,
) -> Company | None:
    """Get a single company by code."""
    result = await db.execute(
        select(Company).where(Company.code == code)
    )
    return result.scalar_one_or_none()


async def create_company(
    db: AsyncSession,
    data: CompanyCreate,
) -> Company:
    """Create a new company."""
    company = Company(
        name=data.name,
        code=data.code,
        is_active=data.is_active,
    )
    db.add(company)
    await db.flush()
    await db.refresh(company)
    return company


async def update_company(
    db: AsyncSession,
    company: Company,
    data: CompanyUpdate,
) -> Company:
    """Update an existing company with partial data."""
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(company, key, value)
    await db.flush()
    await db.refresh(company)
    return company


async def delete_company(
    db: AsyncSession,
    company: Company,
) -> Company:
    """Soft-delete a company by setting is_active=False."""
    company.is_active = False
    await db.flush()
    await db.refresh(company)
    return company

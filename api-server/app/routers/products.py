"""Products router: CRUD for product management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import RoleChecker, get_current_active_user
from app.models.user import User, UserRole
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.price_policy import PricePolicyCreate, PricePolicyResponse, PricePolicyUpdate
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate
from app.services import price_service, product_service

router = APIRouter(prefix="/products", tags=["products"])

system_admin_checker = RoleChecker([UserRole.SYSTEM_ADMIN])


@router.get("/", response_model=PaginatedResponse[ProductResponse])
async def list_products(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    is_active: bool | None = None,
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
):
    """List products with pagination. Available to all authenticated users."""
    pagination = PaginationParams(page=page, size=size)
    products, total = await product_service.get_products(
        db,
        skip=pagination.offset,
        limit=pagination.size,
        is_active=is_active,
        category=category,
    )
    return PaginatedResponse.create(
        items=[ProductResponse.model_validate(p) for p in products],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.post(
    "/",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_product(
    body: ProductCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(system_admin_checker),
):
    """Create a new product (system_admin only)."""
    existing = await product_service.get_product_by_code(db, body.code)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Product with code '{body.code}' already exists",
        )
    product = await product_service.create_product(db, body)
    return product


# === Price Matrix (must be before /{product_id} routes) ===


@router.get("/prices/matrix")
async def get_price_matrix(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(
        RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN])
    ),
):
    """Cross-product x user price matrix.

    Returns a matrix of products and their prices per role.
    """
    from app.models.user import UserRole as UR

    products, _ = await product_service.get_products(db, skip=0, limit=500, is_active=True)
    roles = [r.value for r in UR]

    matrix = []
    for product in products:
        row = {
            "product_id": product.id,
            "product_name": product.name,
            "product_code": product.code,
            "base_price": int(product.base_price) if product.base_price else None,
            "prices_by_role": {},
        }
        for role in roles:
            price = await price_service.get_effective_price(
                db, product=product, user_id=_current_user.id, user_role=role,
            )
            row["prices_by_role"][role] = price
        matrix.append(row)

    return {"matrix": matrix}


# === Single Product ===


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
):
    """Get a single product by ID. Available to all authenticated users."""
    product = await product_service.get_product_by_id(db, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    return product


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    body: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(system_admin_checker),
):
    """Update a product (system_admin only)."""
    product = await product_service.get_product_by_id(db, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    # Check code uniqueness if updating code
    if body.code is not None and body.code != product.code:
        existing = await product_service.get_product_by_code(db, body.code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Product with code '{body.code}' already exists",
            )

    updated = await product_service.update_product(db, product, body)
    return updated


# === Price Policies ===


@router.get(
    "/{product_id}/prices",
    response_model=PaginatedResponse[PricePolicyResponse],
)
async def list_price_policies(
    product_id: int,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(
        RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN])
    ),
):
    """List price policies for a product (system_admin, company_admin)."""
    product = await product_service.get_product_by_id(db, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    pagination = PaginationParams(page=page, size=size)
    policies, total = await price_service.get_price_policies(
        db, product_id=product_id, skip=pagination.offset, limit=pagination.size
    )
    return PaginatedResponse.create(
        items=[PricePolicyResponse.model_validate(p) for p in policies],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.post(
    "/{product_id}/prices",
    response_model=PricePolicyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_price_policy(
    product_id: int,
    body: PricePolicyCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(
        RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN])
    ),
):
    """Create a price policy for a product (system_admin, company_admin)."""
    product = await product_service.get_product_by_id(db, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    if body.product_id != product_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="product_id in body must match URL parameter",
        )

    policy = await price_service.create_price_policy(db, body)
    return policy


@router.delete(
    "/prices/{policy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_price_policy(
    policy_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(system_admin_checker),
):
    """Delete a price policy (system_admin only)."""
    policy = await price_service.get_price_policy_by_id(db, policy_id)
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Price policy not found",
        )
    await price_service.delete_price_policy(db, policy)


# === Product Schema ===


@router.get("/{product_id}/schema")
async def get_product_schema(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Return product form_schema + the current user's effective price policies."""
    product = await product_service.get_product_by_id(db, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    # Get price policies relevant to this user
    user_price = await price_service.get_effective_price(
        db, product=product, user_id=current_user.id, user_role=current_user.role,
    )

    return {
        "product_id": product.id,
        "product_name": product.name,
        "form_schema": product.form_schema,
        "base_price": int(product.base_price) if product.base_price else None,
        "effective_price": user_price,
    }

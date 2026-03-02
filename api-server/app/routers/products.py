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
from app.services.pipeline_validation import validate_schema_for_pipeline

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
    product = await product_service.create_product(db, body)
    pipeline_warnings = validate_schema_for_pipeline(body.form_schema) if body.form_schema else []
    result = ProductResponse.model_validate(product).model_dump()
    result["pipeline_warnings"] = pipeline_warnings
    return result


# === Price Matrix (must be before /{product_id} routes) ===


@router.get("/prices/matrix")
async def get_price_matrix(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(
        RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN])
    ),
):
    """Product x role price matrix for management UI."""
    from app.models.user import UserRole as UR

    products, _ = await product_service.get_products(db, skip=0, limit=500, is_active=True)

    # Roles that need pricing (exclude system_admin)
    pricing_roles = [
        {"id": UR.COMPANY_ADMIN.value, "name": "경리"},
        {"id": UR.ORDER_HANDLER.value, "name": "담당자"},
        {"id": UR.DISTRIBUTOR.value, "name": "총판"},
        {"id": UR.SUB_ACCOUNT.value, "name": "셀러"},
    ]

    rows = []
    for product in products:
        prices: dict[str, int] = {}
        for role_info in pricing_roles:
            try:
                price = await price_service.get_effective_price(
                    db, product=product, user_id=_current_user.id, user_role=role_info["id"],
                )
            except ValueError:
                price = 0
            prices[role_info["id"]] = price

        rows.append({
            "product_id": product.id,
            "product_name": product.name,
            "base_price": int(product.base_price) if product.base_price else 0,
            "cost_price": int(product.cost_price) if product.cost_price else None,
            "reduction_rate": product.reduction_rate,
            "prices": prices,
        })

    return {"rows": rows, "sellers": pricing_roles}


@router.get("/prices/user-matrix")
async def get_user_price_matrix(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(
        RoleChecker([UserRole.SYSTEM_ADMIN, UserRole.COMPANY_ADMIN])
    ),
):
    """Per-user price matrix: for each distributor/sub_account user, their effective prices."""
    from sqlalchemy import select as sa_select

    from app.models.user import User as UserModel

    products, _ = await product_service.get_products(db, skip=0, limit=500, is_active=True)

    # Get all active distributor/sub_account users
    result = await db.execute(
        sa_select(UserModel).where(
            UserModel.is_active == True,
            UserModel.role.in_(["distributor", "sub_account"]),
        )
    )
    users = list(result.scalars().all())

    user_list = []
    user_prices: dict[str, dict[int, int]] = {}

    for user in users:
        uid = str(user.id)
        user_list.append({
            "id": uid,
            "name": user.name,
            "role": user.role,
            "email": user.email,
        })
        user_prices[uid] = {}
        for product in products:
            try:
                price = await price_service.get_effective_price(
                    db, product=product, user_id=user.id, user_role=user.role,
                )
            except ValueError:
                price = int(product.base_price) if product.base_price else 0
            user_prices[uid][product.id] = price

    product_list = [
        {
            "id": p.id,
            "name": p.name,
            "category": p.category,
            "base_price": int(p.base_price) if p.base_price else 0,
        }
        for p in products
    ]

    return {
        "users": user_list,
        "products": product_list,
        "prices": user_prices,
    }


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

    updated = await product_service.update_product(db, product, body)
    schema_to_check = body.form_schema if body.form_schema is not None else updated.form_schema
    pipeline_warnings = validate_schema_for_pipeline(schema_to_check) if schema_to_check else []
    result = ProductResponse.model_validate(updated).model_dump()
    result["pipeline_warnings"] = pipeline_warnings
    return result


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(system_admin_checker),
):
    """Soft-delete a product (set is_active=False). system_admin only."""
    product = await product_service.get_product_by_id(db, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    await product_service.delete_product(db, product)


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
    try:
        user_price = await price_service.get_effective_price(
            db, product=product, user_id=current_user.id, user_role=current_user.role,
        )
    except ValueError:
        user_price = int(product.base_price) if product.base_price else 0

    return {
        "product_id": product.id,
        "product_name": product.name,
        "form_schema": product.form_schema,
        "base_price": int(product.base_price) if product.base_price else None,
        "effective_price": user_price,
    }

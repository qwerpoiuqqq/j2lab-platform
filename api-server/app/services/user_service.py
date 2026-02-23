"""User service: CRUD operations for users with role-based logic."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import ROLE_HIERARCHY, User, UserRole
from app.schemas.user import UserCreate, UserTreeNode, UserUpdate


async def get_users(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    company_id: int | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    current_user: User | None = None,
) -> tuple[list[User], int]:
    """Get paginated list of users with role-based filtering.

    - system_admin: sees all users
    - company_admin: sees only users in the same company
    - order_handler: sees only users in the same company
    - distributor: sees only their sub_accounts
    - sub_account: sees only themselves
    """
    query = select(User)
    count_query = select(func.count()).select_from(User)

    # Role-based scope filtering
    if current_user:
        user_role = UserRole(current_user.role)
        if user_role == UserRole.COMPANY_ADMIN or user_role == UserRole.ORDER_HANDLER:
            query = query.where(User.company_id == current_user.company_id)
            count_query = count_query.where(
                User.company_id == current_user.company_id
            )
        elif user_role == UserRole.DISTRIBUTOR:
            query = query.where(User.parent_id == current_user.id)
            count_query = count_query.where(User.parent_id == current_user.id)
        elif user_role == UserRole.SUB_ACCOUNT:
            query = query.where(User.id == current_user.id)
            count_query = count_query.where(User.id == current_user.id)
        # system_admin: no filtering

    # Additional filters
    if company_id is not None:
        query = query.where(User.company_id == company_id)
        count_query = count_query.where(User.company_id == company_id)
    if role is not None:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)

    query = query.order_by(User.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    users = list(result.scalars().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    return users, total


async def get_user_by_id(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> User | None:
    """Get a single user by ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_email(
    db: AsyncSession,
    email: str,
) -> User | None:
    """Get a single user by email."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    data: UserCreate,
) -> User:
    """Create a new user with hashed password."""
    hashed_pw = hash_password(data.password)

    user = User(
        email=data.email,
        hashed_password=hashed_pw,
        name=data.name,
        phone=data.phone,
        company_id=data.company_id,
        role=data.role.value,
        parent_id=data.parent_id,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def update_user(
    db: AsyncSession,
    user: User,
    data: UserUpdate,
) -> User:
    """Update an existing user with partial data."""
    update_data = data.model_dump(exclude_unset=True)

    if "password" in update_data:
        password = update_data.pop("password")
        if password is not None:
            user.hashed_password = hash_password(password)

    for key, value in update_data.items():
        if key == "role" and value is not None:
            setattr(user, key, value.value if isinstance(value, UserRole) else value)
        else:
            setattr(user, key, value)

    await db.flush()
    await db.refresh(user)
    return user


async def delete_user(
    db: AsyncSession,
    user: User,
) -> User:
    """Soft-delete a user by setting is_active=False."""
    user.is_active = False
    await db.flush()
    await db.refresh(user)
    return user


async def get_user_descendants(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[User]:
    """Get all direct children of a user (one level down)."""
    result = await db.execute(
        select(User).where(User.parent_id == user_id).order_by(User.created_at)
    )
    return list(result.scalars().all())


async def build_user_tree(
    db: AsyncSession,
    root_user: User,
    max_depth: int = 5,
) -> UserTreeNode:
    """Build a recursive tree of a user and their descendants.

    Uses max_depth to prevent unbounded recursion (hierarchy is max 5 levels).
    """
    children_nodes: list[UserTreeNode] = []

    if max_depth > 0:
        children = await get_user_descendants(db, root_user.id)
        for child in children:
            child_node = await build_user_tree(db, child, max_depth=max_depth - 1)
            children_nodes.append(child_node)

    return UserTreeNode(
        id=root_user.id,
        email=root_user.email,
        name=root_user.name,
        role=root_user.role,
        is_active=root_user.is_active,
        children=children_nodes,
    )


def can_view_user(viewer: User, target: User) -> bool:
    """Check if viewer has permission to view target user's details.

    Rules:
    - system_admin can view anyone
    - company_admin can view users in the same company
    - order_handler can view users in the same company
    - distributor can view their sub_accounts and themselves
    - sub_account can only view themselves
    """
    viewer_role = UserRole(viewer.role)

    if viewer_role == UserRole.SYSTEM_ADMIN:
        return True
    if viewer.id == target.id:
        return True
    if viewer_role in (UserRole.COMPANY_ADMIN, UserRole.ORDER_HANDLER):
        return viewer.company_id == target.company_id
    if viewer_role == UserRole.DISTRIBUTOR:
        return target.parent_id == viewer.id
    return False

"""Add icon column to categories table.

Revision ID: 008_category_icon
Revises: 007_categories_notices
Create Date: 2026-02-27
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "008_category_icon"
down_revision: Union[str, None] = "007_categories_notices"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column("categories", sa.Column("icon", sa.String(50), nullable=True, server_default=sa.text("'grid'")))

def downgrade() -> None:
    op.drop_column("categories", "icon")

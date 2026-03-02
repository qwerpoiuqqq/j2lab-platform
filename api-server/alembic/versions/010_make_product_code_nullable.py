"""Make product code nullable.

Revision ID: 010_make_product_code_nullable
Revises: 009_workflow_enhancements
"""
from alembic import op
import sqlalchemy as sa

revision = "010_make_product_code_nullable"
down_revision = "009_workflow_enhancements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("products", "code", existing_type=sa.String(50), nullable=True)


def downgrade() -> None:
    op.alter_column("products", "code", existing_type=sa.String(50), nullable=False)

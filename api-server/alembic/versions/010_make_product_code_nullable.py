"""Make product code nullable.

Revision ID: 010
Revises: 009
"""
from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("products", "code", existing_type=sa.String(50), nullable=True)


def downgrade() -> None:
    op.alter_column("products", "code", existing_type=sa.String(50), nullable=False)

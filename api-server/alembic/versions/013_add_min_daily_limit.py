"""Add min_daily_limit to products.

Revision ID: 013_add_min_daily_limit
Revises: 012_preset_handler_user
"""

from alembic import op
import sqlalchemy as sa

revision = "013_add_min_daily_limit"
down_revision = "012_preset_handler_user"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "min_daily_limit",
            sa.Integer(),
            nullable=True,
            comment="최소 일일 한도",
        ),
    )


def downgrade() -> None:
    op.drop_column("products", "min_daily_limit")

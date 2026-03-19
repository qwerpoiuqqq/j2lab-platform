"""Add reject_reason column to orders table.

Revision ID: 023_add_reject_reason
Revises: 022_smart_traffic
"""

from alembic import op
import sqlalchemy as sa


revision = "023_add_reject_reason"
down_revision = "036_drop_agency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("reject_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("orders", "reject_reason")

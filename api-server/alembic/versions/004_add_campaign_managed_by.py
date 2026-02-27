"""Add managed_by field to campaigns for order_handler scoping.

Revision ID: 004_managed_by
Revises: 003_phase1c
Create Date: 2026-02-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "004_managed_by"
down_revision: Union[str, None] = "003_phase1c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column("managed_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("idx_campaigns_managed_by", "campaigns", ["managed_by"])


def downgrade() -> None:
    op.drop_index("idx_campaigns_managed_by", table_name="campaigns")
    op.drop_column("campaigns", "managed_by")

"""Add hidden_margin_rate to products and original_daily/total_limit to campaigns.

Revision ID: 024_hidden_margin
Revises: 023_add_reject_reason
"""

from alembic import op
import sqlalchemy as sa


revision = "024_hidden_margin"
down_revision = "023_add_reject_reason"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Product: 감은 비율 (0-100%)
    op.add_column(
        "products",
        sa.Column("hidden_margin_rate", sa.Integer(), nullable=True, server_default="0"),
    )

    # Campaign: 원래 접수 타수 저장 (감기 전)
    op.add_column(
        "campaigns",
        sa.Column("original_daily_limit", sa.Integer(), nullable=True),
    )
    op.add_column(
        "campaigns",
        sa.Column("original_total_limit", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("campaigns", "original_total_limit")
    op.drop_column("campaigns", "original_daily_limit")
    op.drop_column("products", "hidden_margin_rate")

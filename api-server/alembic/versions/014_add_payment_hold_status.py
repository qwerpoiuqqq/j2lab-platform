"""Add payment_hold columns to orders.

Revision ID: 014_add_payment_hold_status
Revises: 013_add_min_daily_limit
"""

from alembic import op
import sqlalchemy as sa

revision = "014_add_payment_hold_status"
down_revision = "013_add_min_daily_limit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "hold_reason",
            sa.Text(),
            nullable=True,
            comment="보류 사유",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "payment_checked_by",
            sa.Uuid(),
            sa.ForeignKey("users.id"),
            nullable=True,
            comment="정산 체크 처리자",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "payment_checked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="정산 체크 처리 시각",
        ),
    )


def downgrade() -> None:
    op.drop_column("orders", "payment_checked_at")
    op.drop_column("orders", "payment_checked_by")
    op.drop_column("orders", "hold_reason")

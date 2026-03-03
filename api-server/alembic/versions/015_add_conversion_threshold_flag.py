"""Add conversion_threshold_handled flag to campaigns.

Revision ID: 015_conv_threshold_flag
Revises: 014_add_payment_hold_status
"""

from alembic import op
import sqlalchemy as sa

revision = "015_conv_threshold_flag"
down_revision = "014_add_payment_hold_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column(
            "conversion_threshold_handled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="10000 전환수 초과 네트워크 변경 처리 완료 여부",
        ),
    )


def downgrade() -> None:
    op.drop_column("campaigns", "conversion_threshold_handled")

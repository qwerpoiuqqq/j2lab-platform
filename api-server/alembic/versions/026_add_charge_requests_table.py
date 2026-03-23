"""Add charge_requests table.

Revision ID: 026_charge_requests
Revises: 025_price_policy_campaign_type
"""

from alembic import op
import sqlalchemy as sa


revision = "026_charge_requests"
down_revision = "025_price_policy_campaign_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "charge_requests",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("request_type", sa.String(length=20), nullable=False, server_default="charge"),
        sa.Column("amount", sa.Numeric(12, 0), nullable=False),
        sa.Column("payment_amount", sa.Numeric(12, 0), nullable=True),
        sa.Column("vat_amount", sa.Numeric(12, 0), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_charge_requests_user_id", "charge_requests", ["user_id"])
    op.create_index("idx_charge_requests_status", "charge_requests", ["status"])
    op.create_index("idx_charge_requests_created_at", "charge_requests", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_charge_requests_created_at", table_name="charge_requests")
    op.drop_index("idx_charge_requests_status", table_name="charge_requests")
    op.drop_index("idx_charge_requests_user_id", table_name="charge_requests")
    op.drop_table("charge_requests")

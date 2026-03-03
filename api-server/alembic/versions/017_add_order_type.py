"""Add order_type column to orders table.

Revision ID: 017_add_order_type
Revises: 016_seed_campaign_templates

Adds order_type column to differentiate regular orders from
monthly_guarantee and managed orders (which have no revenue).
"""

from alembic import op
import sqlalchemy as sa

revision = "017_add_order_type"
down_revision = "016_seed_campaign_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("order_type", sa.String(30), server_default="regular", nullable=False),
    )
    op.create_index("idx_orders_order_type", "orders", ["order_type"])


def downgrade() -> None:
    op.drop_index("idx_orders_order_type", table_name="orders")
    op.drop_column("orders", "order_type")

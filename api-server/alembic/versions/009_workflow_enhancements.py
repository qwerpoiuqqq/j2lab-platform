"""Workflow enhancements: cost tracking, setup delay, order selection.

Revision ID: 009_workflow_enhancements
Revises: 008_category_icon
Create Date: 2026-03-02
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "009_workflow_enhancements"
down_revision: Union[str, None] = "008_category_icon"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PHASE 0: OrderItem cost tracking
    op.add_column(
        "order_items",
        sa.Column("cost_unit_price", sa.Integer, nullable=True),
    )

    # PHASE 3: Product setup delay
    op.add_column(
        "products",
        sa.Column(
            "setup_delay_minutes",
            sa.Integer,
            nullable=False,
            server_default="30",
        ),
    )

    # Distributor order selection
    op.add_column(
        "orders",
        sa.Column(
            "selection_status",
            sa.String(20),
            nullable=False,
            server_default="included",
        ),
    )
    op.add_column(
        "orders",
        sa.Column("selected_by", sa.Uuid, nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column(
            "selected_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("orders", "selected_at")
    op.drop_column("orders", "selected_by")
    op.drop_column("orders", "selection_status")
    op.drop_column("products", "setup_delay_minutes")
    op.drop_column("order_items", "cost_unit_price")

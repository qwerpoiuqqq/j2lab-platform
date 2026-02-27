"""Add cost_price and reduction_rate to products.

Revision ID: 005_product_fields
Revises: 004_managed_by
Create Date: 2026-02-27
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "005_product_fields"
down_revision: Union[str, None] = "004_managed_by"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column("products", sa.Column("cost_price", sa.Numeric(12, 0), nullable=True))
    op.add_column("products", sa.Column("reduction_rate", sa.Integer(), nullable=True))

def downgrade() -> None:
    op.drop_column("products", "reduction_rate")
    op.drop_column("products", "cost_price")

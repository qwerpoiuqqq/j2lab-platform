"""Add campaign_type to price_policies.

Revision ID: 025_price_policy_campaign_type
Revises: 024_hidden_margin
"""

from alembic import op
import sqlalchemy as sa


revision = "025_price_policy_campaign_type"
down_revision = "024_hidden_margin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "price_policies",
        sa.Column("campaign_type", sa.String(length=20), nullable=True),
    )
    op.create_index(
        "idx_price_policies_campaign_type",
        "price_policies",
        ["campaign_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_price_policies_campaign_type", table_name="price_policies")
    op.drop_column("price_policies", "campaign_type")

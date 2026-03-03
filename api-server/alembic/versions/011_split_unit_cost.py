"""Split unit_cost into unit_cost_traffic and unit_cost_save.

Revision ID: 011
Revises: 010
"""

from alembic import op
import sqlalchemy as sa

revision = "011_split_unit_cost"
down_revision = "010_make_product_code_nullable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns
    op.add_column(
        "superap_accounts",
        sa.Column("unit_cost_traffic", sa.Integer(), nullable=False, server_default="21"),
    )
    op.add_column(
        "superap_accounts",
        sa.Column("unit_cost_save", sa.Integer(), nullable=False, server_default="31"),
    )

    # Copy existing unit_cost to unit_cost_traffic
    op.execute("UPDATE superap_accounts SET unit_cost_traffic = unit_cost")

    # Drop old column
    op.drop_column("superap_accounts", "unit_cost")


def downgrade() -> None:
    op.add_column(
        "superap_accounts",
        sa.Column("unit_cost", sa.Integer(), nullable=False, server_default="21"),
    )
    op.execute("UPDATE superap_accounts SET unit_cost = unit_cost_traffic")
    op.drop_column("superap_accounts", "unit_cost_traffic")
    op.drop_column("superap_accounts", "unit_cost_save")

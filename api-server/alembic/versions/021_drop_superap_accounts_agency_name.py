"""Drop agency_name column from superap_accounts.

Replaced by company_id -> companies.name lookup.

Revision ID: 021
Revises: 020
"""

from alembic import op
import sqlalchemy as sa

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("superap_accounts", "agency_name")


def downgrade() -> None:
    op.add_column(
        "superap_accounts",
        sa.Column("agency_name", sa.String(100), nullable=True),
    )

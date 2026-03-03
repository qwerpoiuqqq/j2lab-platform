"""Add handler_user_id to network_presets.

Revision ID: 012_add_handler_user_id_to_network_presets
Revises: 011_split_unit_cost
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "012_preset_handler_user"
down_revision = "011_split_unit_cost"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "network_presets",
        sa.Column(
            "handler_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
            comment="전용 담당자 ID (NULL=일반, 값 있음=해당 담당자 전용)",
        ),
    )
    op.create_index(
        "idx_network_presets_handler",
        "network_presets",
        ["handler_user_id"],
    )
    # Drop old unique constraint and create new one including handler_user_id
    op.drop_constraint(
        "uq_network_presets_company_type_tier",
        "network_presets",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_network_presets_company_type_tier_handler",
        "network_presets",
        ["company_id", "campaign_type", "tier_order", "handler_user_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_network_presets_company_type_tier_handler",
        "network_presets",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_network_presets_company_type_tier",
        "network_presets",
        ["company_id", "campaign_type", "tier_order"],
    )
    op.drop_index("idx_network_presets_handler", "network_presets")
    op.drop_column("network_presets", "handler_user_id")

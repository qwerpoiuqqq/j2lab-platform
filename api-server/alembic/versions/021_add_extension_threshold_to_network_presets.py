"""Add per-network extension threshold column.

Revision ID: 021_network_ext_threshold
Revises: 020_add_actor_pipeline_logs
"""

from alembic import op
import sqlalchemy as sa

revision = "021_network_ext_threshold"
down_revision = "020_add_actor_pipeline_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "network_presets",
        sa.Column(
            "extension_threshold",
            sa.Integer(),
            nullable=False,
            server_default="10000",
            comment="연장/신규 판단 기준 타수 (네트워크별)",
        ),
    )


def downgrade() -> None:
    op.drop_column("network_presets", "extension_threshold")

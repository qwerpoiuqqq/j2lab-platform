"""Add actor tracking to pipeline_logs and seed extension_threshold.

Revision ID: 020_add_actor_to_pipeline_logs
Revises: 019_add_missing_templates

Changes:
- Add actor_id (UUID FK → users.id) to pipeline_logs
- Add actor_name (VARCHAR 50) to pipeline_logs
- Seed 'extension_threshold' = 10000 into system_settings
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "020_add_actor_pipeline_logs"
down_revision = "019_add_missing_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add actor columns to pipeline_logs
    op.add_column(
        "pipeline_logs",
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "pipeline_logs",
        sa.Column("actor_name", sa.String(50), nullable=True),
    )

    # 2. Seed extension_threshold into system_settings
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO system_settings (key, value, description) "
            "VALUES (:key, :value, :desc) "
            "ON CONFLICT (key) DO NOTHING"
        ),
        {
            "key": "extension_threshold",
            "value": "10000",
            "desc": "연장/신규 판단 기준 타수 (combined total_limit 기준)",
        },
    )


def downgrade() -> None:
    op.drop_column("pipeline_logs", "actor_name")
    op.drop_column("pipeline_logs", "actor_id")

    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM system_settings WHERE key = 'extension_threshold'")
    )

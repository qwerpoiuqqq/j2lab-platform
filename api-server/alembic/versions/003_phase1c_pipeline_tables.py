"""Phase 1C tables: places, keywords, keyword_rank_history, extraction_jobs,
network_presets, superap_accounts, campaigns, campaign_keyword_pool,
campaign_templates, pipeline_states, pipeline_logs.

Also adds place_id FK and assigned_account_id FK to order_items.

Revision ID: 003_phase1c
Revises: 002_phase1b
Create Date: 2026-02-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "003_phase1c"
down_revision: Union[str, None] = "002_phase1b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === places table ===
    op.create_table(
        "places",
        sa.Column("id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("place_type", sa.String(20), nullable=False, server_default="place"),
        sa.Column("category", sa.String(500), nullable=True),
        sa.Column("main_category", sa.String(100), nullable=True),
        sa.Column("city", sa.String(50), nullable=True),
        sa.Column("si", sa.String(50), nullable=True),
        sa.Column("gu", sa.String(50), nullable=True),
        sa.Column("dong", sa.String(50), nullable=True),
        sa.Column("major_area", sa.String(50), nullable=True),
        sa.Column("road_address", sa.String(500), nullable=True),
        sa.Column("jibun_address", sa.String(500), nullable=True),
        sa.Column("stations", sa.JSON(), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("virtual_phone", sa.String(20), nullable=True),
        sa.Column("business_hours", sa.Text(), nullable=True),
        sa.Column("introduction", sa.Text(), nullable=True),
        sa.Column("naver_url", sa.String(500), nullable=True),
        sa.Column("keywords", sa.JSON(), nullable=True),
        sa.Column("conveniences", sa.JSON(), nullable=True),
        sa.Column("micro_reviews", sa.JSON(), nullable=True),
        sa.Column("review_menu_keywords", sa.JSON(), nullable=True),
        sa.Column("review_theme_keywords", sa.JSON(), nullable=True),
        sa.Column("voted_keywords", sa.JSON(), nullable=True),
        sa.Column("payment_info", sa.JSON(), nullable=True),
        sa.Column("seat_items", sa.JSON(), nullable=True),
        sa.Column("specialties", sa.JSON(), nullable=True),
        sa.Column("menus", sa.JSON(), nullable=True),
        sa.Column("medical_subjects", sa.JSON(), nullable=True),
        sa.Column("discovered_regions", sa.JSON(), nullable=True),
        sa.Column("has_booking", sa.Boolean(), server_default="false"),
        sa.Column("booking_type", sa.String(20), nullable=True),
        sa.Column("booking_hub_id", sa.String(100), nullable=True),
        sa.Column("booking_url", sa.Text(), nullable=True),
        sa.Column("last_scraped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_places_place_type", "places", ["place_type"])
    op.create_index("idx_places_gu", "places", ["gu"])
    op.create_index("idx_places_major_area", "places", ["major_area"])

    # === keywords table ===
    op.create_table(
        "keywords",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("place_id", sa.BigInteger(), nullable=False),
        sa.Column("keyword", sa.String(200), nullable=False),
        sa.Column("keyword_type", sa.String(20), nullable=True),
        sa.Column("search_query", sa.String(300), nullable=True),
        sa.Column("current_rank", sa.Integer(), nullable=True),
        sa.Column("current_map_type", sa.String(10), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("place_id", "keyword", name="uq_keywords_place_keyword"),
    )
    op.create_index("idx_keywords_place_id", "keywords", ["place_id"])
    op.create_index("idx_keywords_current_rank", "keywords", ["current_rank"])
    op.create_index("idx_keywords_keyword_type", "keywords", ["keyword_type"])

    # === keyword_rank_history table ===
    op.create_table(
        "keyword_rank_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("keyword_id", sa.BigInteger(), nullable=False),
        sa.Column("rank_position", sa.Integer(), nullable=True),
        sa.Column("map_type", sa.String(10), nullable=True),
        sa.Column("recorded_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["keyword_id"], ["keywords.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("keyword_id", "recorded_date", name="uq_rank_history_keyword_date"),
    )
    op.create_index("idx_rank_history_keyword_id", "keyword_rank_history", ["keyword_id"])
    op.create_index("idx_rank_history_recorded_date", "keyword_rank_history", ["recorded_date"])

    # === network_presets table ===
    op.create_table(
        "network_presets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("campaign_type", sa.String(20), nullable=False),
        sa.Column("tier_order", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("media_config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.UniqueConstraint("company_id", "campaign_type", "tier_order", name="uq_network_presets_company_type_tier"),
    )
    op.create_index("idx_network_presets_company_id", "network_presets", ["company_id"])

    # === superap_accounts table ===
    op.create_table(
        "superap_accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id_superap", sa.String(100), nullable=False),
        sa.Column("password_encrypted", sa.Text(), nullable=False),
        sa.Column("agency_name", sa.String(100), nullable=True),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("network_preset_id", sa.Integer(), nullable=True),
        sa.Column("unit_cost", sa.Integer(), nullable=False, server_default="21"),
        sa.Column("assignment_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id_superap"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["network_preset_id"], ["network_presets.id"]),
    )
    op.create_index("idx_superap_accounts_company_id", "superap_accounts", ["company_id"])
    op.create_index("idx_superap_accounts_network_preset_id", "superap_accounts", ["network_preset_id"])

    # === extraction_jobs table ===
    op.create_table(
        "extraction_jobs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("order_item_id", sa.BigInteger(), nullable=True),
        sa.Column("place_id", sa.BigInteger(), nullable=True),
        sa.Column("naver_url", sa.Text(), nullable=False),
        sa.Column("target_count", sa.Integer(), server_default="100"),
        sa.Column("max_rank", sa.Integer(), server_default="50"),
        sa.Column("min_rank", sa.Integer(), server_default="1"),
        sa.Column("name_keyword_ratio", sa.Float(), server_default="0.30"),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("place_name", sa.String(200), nullable=True),
        sa.Column("result_count", sa.Integer(), server_default="0"),
        sa.Column("results", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("proxy_slot", sa.Integer(), nullable=True),
        sa.Column("worker_id", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_extraction_jobs_status", "extraction_jobs", ["status"])
    op.create_index("idx_extraction_jobs_place_id", "extraction_jobs", ["place_id"])
    op.create_index("idx_extraction_jobs_order_item_id", "extraction_jobs", ["order_item_id"])

    # === campaign_templates table ===
    op.create_table(
        "campaign_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("type_name", sa.String(50), nullable=False),
        sa.Column("description_template", sa.Text(), nullable=False),
        sa.Column("hint_text", sa.Text(), nullable=False),
        sa.Column("campaign_type_selection", sa.String(100), nullable=True),
        sa.Column("links", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("hashtag", sa.String(100), nullable=True),
        sa.Column("image_url_200x600", sa.Text(), nullable=True),
        sa.Column("image_url_720x780", sa.Text(), nullable=True),
        sa.Column("conversion_text_template", sa.Text(), nullable=True),
        sa.Column("steps_start", sa.Text(), nullable=True),
        sa.Column("modules", sa.JSON(), server_default="[]"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("type_name"),
    )

    # === campaigns table ===
    op.create_table(
        "campaigns",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("campaign_code", sa.String(20), nullable=True),
        sa.Column("superap_account_id", sa.Integer(), nullable=True),
        sa.Column("order_item_id", sa.BigInteger(), nullable=True),
        sa.Column("place_id", sa.BigInteger(), nullable=True),
        sa.Column("extraction_job_id", sa.BigInteger(), nullable=True),
        sa.Column("agency_name", sa.String(100), nullable=True),
        sa.Column("place_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("place_url", sa.Text(), nullable=False),
        sa.Column("campaign_type", sa.String(50), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("daily_limit", sa.Integer(), nullable=False),
        sa.Column("total_limit", sa.Integer(), nullable=True),
        sa.Column("current_conversions", sa.Integer(), server_default="0"),
        sa.Column("landmark_name", sa.String(200), nullable=True),
        sa.Column("step_count", sa.Integer(), nullable=True),
        sa.Column("module_context", sa.JSON(), nullable=True),
        sa.Column("original_keywords", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("registration_step", sa.String(30), nullable=True),
        sa.Column("registration_message", sa.Text(), nullable=True),
        sa.Column("extend_target_id", sa.BigInteger(), nullable=True),
        sa.Column("extension_history", sa.JSON(), nullable=True),
        sa.Column("last_keyword_change", sa.DateTime(timezone=True), nullable=True),
        sa.Column("network_preset_id", sa.Integer(), nullable=True),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["superap_account_id"], ["superap_accounts.id"]),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"]),
        sa.ForeignKeyConstraint(["extraction_job_id"], ["extraction_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["network_preset_id"], ["network_presets.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
    )
    op.create_index("idx_campaigns_status", "campaigns", ["status"])
    op.create_index("idx_campaigns_place_id", "campaigns", ["place_id"])
    op.create_index("idx_campaigns_superap_account_id", "campaigns", ["superap_account_id"])
    op.create_index("idx_campaigns_order_item_id", "campaigns", ["order_item_id"])
    op.create_index("idx_campaigns_end_date", "campaigns", ["end_date"])
    op.create_index("idx_campaigns_company_id", "campaigns", ["company_id"])
    op.create_index("idx_campaigns_network_preset_id", "campaigns", ["network_preset_id"])

    # === campaign_keyword_pool table ===
    op.create_table(
        "campaign_keyword_pool",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("campaign_id", sa.BigInteger(), nullable=False),
        sa.Column("keyword", sa.String(255), nullable=False),
        sa.Column("is_used", sa.Boolean(), server_default="false"),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("round_number", sa.Integer(), server_default="1"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("campaign_id", "keyword", name="uq_campaign_kw_pool_campaign_keyword"),
    )
    op.create_index("idx_campaign_kw_pool_campaign_id", "campaign_keyword_pool", ["campaign_id"])
    op.create_index("idx_campaign_kw_pool_is_used", "campaign_keyword_pool", ["is_used"])

    # === pipeline_states table ===
    op.create_table(
        "pipeline_states",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("order_item_id", sa.BigInteger(), nullable=False),
        sa.Column("current_stage", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("previous_stage", sa.String(30), nullable=True),
        sa.Column("extraction_job_id", sa.BigInteger(), nullable=True),
        sa.Column("campaign_id", sa.BigInteger(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["extraction_job_id"], ["extraction_jobs.id"]),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.UniqueConstraint("order_item_id", name="uq_pipeline_states_order_item_id"),
    )
    op.create_index("idx_pipeline_order_item_id", "pipeline_states", ["order_item_id"])
    op.create_index("idx_pipeline_current_stage", "pipeline_states", ["current_stage"])

    # === pipeline_logs table ===
    op.create_table(
        "pipeline_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("pipeline_state_id", sa.BigInteger(), nullable=False),
        sa.Column("from_stage", sa.String(30), nullable=True),
        sa.Column("to_stage", sa.String(30), nullable=False),
        sa.Column("trigger_type", sa.String(50), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["pipeline_state_id"], ["pipeline_states.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_pipeline_logs_state_id", "pipeline_logs", ["pipeline_state_id"])

    # === Add place_id to order_items (FK to places) ===
    op.add_column("order_items", sa.Column("place_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_order_items_place_id", "order_items", "places", ["place_id"], ["id"])
    op.create_index("idx_order_items_place_id", "order_items", ["place_id"])

    # === Update assigned_account_id FK on order_items ===
    op.create_foreign_key(
        "fk_order_items_assigned_account_id",
        "order_items",
        "superap_accounts",
        ["assigned_account_id"],
        ["id"],
    )


def downgrade() -> None:
    # Drop FK constraints on order_items
    op.drop_constraint("fk_order_items_assigned_account_id", "order_items", type_="foreignkey")
    op.drop_index("idx_order_items_place_id", "order_items")
    op.drop_constraint("fk_order_items_place_id", "order_items", type_="foreignkey")
    op.drop_column("order_items", "place_id")

    # Drop tables in reverse dependency order
    op.drop_table("pipeline_logs")
    op.drop_table("pipeline_states")
    op.drop_table("campaign_keyword_pool")
    op.drop_table("campaigns")
    op.drop_table("campaign_templates")
    op.drop_table("extraction_jobs")
    op.drop_table("superap_accounts")
    op.drop_table("network_presets")
    op.drop_table("keyword_rank_history")
    op.drop_table("keywords")
    op.drop_table("places")

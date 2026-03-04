"""Add missing indexes to improve query performance.

Revision ID: 018_add_missing_indexes
Revises: 017_add_order_type

Adds indexes on commonly filtered columns:
- companies.is_active
- products.is_active, products.code
- categories.is_active, categories.sort_order
- campaign_templates.is_active
"""

from alembic import op

revision = "018_add_missing_indexes"
down_revision = "017_add_order_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("idx_companies_is_active", "companies", ["is_active"])
    op.create_index("idx_products_is_active", "products", ["is_active"])
    op.create_index(
        "idx_products_code",
        "products",
        ["code"],
        unique=False,
        postgresql_where="code IS NOT NULL",
    )
    op.create_index("idx_categories_is_active", "categories", ["is_active"])
    op.create_index("idx_categories_sort_order", "categories", ["sort_order"])
    op.create_index("idx_campaign_templates_is_active", "campaign_templates", ["is_active"])


def downgrade() -> None:
    op.drop_index("idx_campaign_templates_is_active", table_name="campaign_templates")
    op.drop_index("idx_categories_sort_order", table_name="categories")
    op.drop_index("idx_categories_is_active", table_name="categories")
    op.drop_index("idx_products_code", table_name="products")
    op.drop_index("idx_products_is_active", table_name="products")
    op.drop_index("idx_companies_is_active", table_name="companies")

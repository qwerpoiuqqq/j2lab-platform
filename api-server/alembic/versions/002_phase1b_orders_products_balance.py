"""Phase 1B tables: products, price_policies, orders, order_items,
balance_transactions, system_settings.

Revision ID: 002_phase1b
Revises: 001_initial
Create Date: 2026-02-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002_phase1b"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === products table ===
    op.create_table(
        "products",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("form_schema", sa.JSON(), nullable=True),
        sa.Column("base_price", sa.Numeric(precision=12, scale=0), nullable=True),
        sa.Column("min_work_days", sa.Integer(), nullable=True),
        sa.Column("max_work_days", sa.Integer(), nullable=True),
        sa.Column(
            "daily_deadline",
            sa.Time(),
            server_default=sa.text("'18:00'"),
            nullable=False,
        ),
        sa.Column(
            "deadline_timezone",
            sa.String(30),
            server_default="Asia/Seoul",
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    # === price_policies table ===
    op.create_table(
        "price_policies",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("role", sa.String(20), nullable=True),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=0), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "idx_price_policies_product_id", "price_policies", ["product_id"]
    )
    op.create_index(
        "idx_price_policies_user_id", "price_policies", ["user_id"]
    )

    # === orders table ===
    op.create_table(
        "orders",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("order_number", sa.String(30), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "payment_status",
            sa.String(20),
            server_default="unpaid",
            nullable=True,
        ),
        sa.Column(
            "total_amount",
            sa.Numeric(precision=12, scale=0),
            server_default=sa.text("0"),
            nullable=True,
        ),
        sa.Column(
            "vat_amount",
            sa.Numeric(precision=12, scale=0),
            server_default=sa.text("0"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "source",
            sa.String(20),
            server_default="web",
            nullable=True,
        ),
        sa.Column("submitted_by", sa.Uuid(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_confirmed_by", sa.Uuid(), nullable=True),
        sa.Column(
            "payment_confirmed_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_number"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["payment_confirmed_by"], ["users.id"]),
    )
    op.create_index("idx_orders_user_id", "orders", ["user_id"])
    op.create_index("idx_orders_status", "orders", ["status"])
    op.create_index("idx_orders_created_at", "orders", ["created_at"])

    # === order_items table ===
    op.create_table(
        "order_items",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=True),
        sa.Column(
            "quantity",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=0), nullable=False),
        sa.Column("subtotal", sa.Numeric(precision=12, scale=0), nullable=False),
        sa.Column("item_data", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("result_message", sa.Text(), nullable=True),
        sa.Column("assigned_account_id", sa.Integer(), nullable=True),
        sa.Column(
            "assignment_status",
            sa.String(20),
            server_default="pending",
            nullable=True,
        ),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"]),
    )
    op.create_index("idx_order_items_order_id", "order_items", ["order_id"])
    op.create_index("idx_order_items_status", "order_items", ["status"])

    # === balance_transactions table ===
    op.create_table(
        "balance_transactions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=12, scale=0), nullable=False),
        sa.Column(
            "balance_after", sa.Numeric(precision=12, scale=0), nullable=False
        ),
        sa.Column("transaction_type", sa.String(20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )
    op.create_index(
        "idx_balance_tx_user_id", "balance_transactions", ["user_id"]
    )
    op.create_index(
        "idx_balance_tx_order_id", "balance_transactions", ["order_id"]
    )
    op.create_index(
        "idx_balance_tx_created_at", "balance_transactions", ["created_at"]
    )

    # === system_settings table ===
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
    )


def downgrade() -> None:
    op.drop_table("system_settings")
    op.drop_table("balance_transactions")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("price_policies")
    op.drop_table("products")

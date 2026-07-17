"""stock: autoincrement local PK + gsystem_if_id/lg_stock_id columns

Revision ID: c2dfb08cc6a6
Revises: 72c8bf3dd570
Create Date: 2026-07-17

G-System's lgstock response carries two distinct ids: "id" (interface
pending-queue row, can change across sync cycles) and "lgStockId" (the
stable business stock-record id). The previous schema used "id" directly
as a non-autoincrement PK, risking duplicate rows across resyncs. This
migration drops and recreates aps_stock with a proper autoincrement local
PK plus gsystem_if_id/lg_stock_id columns, keying upserts off lg_stock_id.

aps_stock is synced/computed data only (no FK dependents) — safe to drop
and recreate; a fresh sync repopulates it.
"""
from alembic import op
import sqlalchemy as sa

revision: str = "c2dfb08cc6a6"
down_revision: str | None = "72c8bf3dd570"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.drop_table("aps_stock", schema="aps_input")
    op.create_table(
        "aps_stock",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("gsystem_if_id", sa.BigInteger(), nullable=True),
        sa.Column("lg_stock_id", sa.BigInteger(), nullable=True),
        sa.Column("corp_id", sa.String(50), nullable=True),
        sa.Column("parea_id", sa.String(50), nullable=True),
        sa.Column("biz_id", sa.String(50), nullable=True),
        sa.Column("stk_ym", sa.String(10), nullable=True),
        sa.Column("stk_type", sa.String(20), nullable=True),
        sa.Column("wh_cd", sa.String(50), nullable=True),
        sa.Column("location_id", sa.String(50), nullable=True),
        sa.Column("item_id", sa.String(50), nullable=True),
        sa.Column("unit_cd", sa.String(20), nullable=True),
        sa.Column("lotno", sa.String(100), nullable=True),
        sa.Column("prev_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("prev_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("prev_amt", sa.Numeric(18, 4), nullable=True),
        sa.Column("in_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("buy_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("buy_amt", sa.Numeric(18, 4), nullable=True),
        sa.Column("make_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("make_amt", sa.Numeric(18, 4), nullable=True),
        sa.Column("etc_in_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("etc_in_amt", sa.Numeric(18, 4), nullable=True),
        sa.Column("mv_in_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("mv_in_amt", sa.Numeric(18, 4), nullable=True),
        sa.Column("out_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("invoice_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("invoice_amt", sa.Numeric(18, 4), nullable=True),
        sa.Column("mat_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("mat_amt", sa.Numeric(18, 4), nullable=True),
        sa.Column("mv_out_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("mv_out_amt", sa.Numeric(18, 4), nullable=True),
        sa.Column("etc_out_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("etc_out_amt", sa.Numeric(18, 4), nullable=True),
        sa.Column("able_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("reg_user_id", sa.String(50), nullable=True),
        sa.Column("reg_dt", sa.DateTime(), nullable=True),
        sa.Column("reg_ip", sa.String(50), nullable=True),
        sa.Column("mod_user_id", sa.String(50), nullable=True),
        sa.Column("mod_dt", sa.DateTime(), nullable=True),
        sa.Column("mod_ip", sa.String(50), nullable=True),
        schema="aps_input",
    )
    op.create_index("ix_aps_stock_gsystem_if_id", "aps_stock", ["gsystem_if_id"], schema="aps_input")
    op.create_index("ix_aps_stock_lg_stock_id", "aps_stock", ["lg_stock_id"], schema="aps_input", unique=True)
    op.create_index("ix_aps_stock_stk_ym", "aps_stock", ["stk_ym"], schema="aps_input")
    op.create_index("ix_aps_stock_wh_cd", "aps_stock", ["wh_cd"], schema="aps_input")
    op.create_index("ix_aps_stock_item_id", "aps_stock", ["item_id"], schema="aps_input")
    op.create_index("ix_aps_stock_able_qty", "aps_stock", ["able_qty"], schema="aps_input")


def downgrade() -> None:
    op.drop_table("aps_stock", schema="aps_input")
    op.create_table(
        "aps_stock",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("corp_id", sa.String(50), nullable=True),
        sa.Column("parea_id", sa.String(50), nullable=True),
        sa.Column("biz_id", sa.String(50), nullable=True),
        sa.Column("stk_ym", sa.String(10), nullable=True),
        sa.Column("stk_type", sa.String(20), nullable=True),
        sa.Column("wh_cd", sa.String(50), nullable=True),
        sa.Column("location_id", sa.String(50), nullable=True),
        sa.Column("item_id", sa.String(50), nullable=True),
        sa.Column("unit_cd", sa.String(20), nullable=True),
        sa.Column("lotno", sa.String(100), nullable=True),
        sa.Column("prev_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("prev_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("prev_amt", sa.Numeric(18, 4), nullable=True),
        sa.Column("in_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("buy_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("buy_amt", sa.Numeric(18, 4), nullable=True),
        sa.Column("make_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("make_amt", sa.Numeric(18, 4), nullable=True),
        sa.Column("etc_in_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("etc_in_amt", sa.Numeric(18, 4), nullable=True),
        sa.Column("mv_in_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("mv_in_amt", sa.Numeric(18, 4), nullable=True),
        sa.Column("out_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("invoice_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("invoice_amt", sa.Numeric(18, 4), nullable=True),
        sa.Column("mat_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("mat_amt", sa.Numeric(18, 4), nullable=True),
        sa.Column("mv_out_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("mv_out_amt", sa.Numeric(18, 4), nullable=True),
        sa.Column("etc_out_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("etc_out_amt", sa.Numeric(18, 4), nullable=True),
        sa.Column("able_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("reg_user_id", sa.String(50), nullable=True),
        sa.Column("reg_dt", sa.DateTime(), nullable=True),
        sa.Column("reg_ip", sa.String(50), nullable=True),
        sa.Column("mod_user_id", sa.String(50), nullable=True),
        sa.Column("mod_dt", sa.DateTime(), nullable=True),
        sa.Column("mod_ip", sa.String(50), nullable=True),
        schema="aps_input",
    )
    op.create_index("ix_aps_stock_stk_ym", "aps_stock", ["stk_ym"], schema="aps_input")
    op.create_index("ix_aps_stock_wh_cd", "aps_stock", ["wh_cd"], schema="aps_input")
    op.create_index("ix_aps_stock_item_id", "aps_stock", ["item_id"], schema="aps_input")
    op.create_index("ix_aps_stock_able_qty", "aps_stock", ["able_qty"], schema="aps_input")

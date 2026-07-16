"""add mps_plan and item_routing tables

Revision ID: a6c2e9d4f817
Revises: d3f8a1c6b04e
Create Date: 2026-07-14 16:20:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a6c2e9d4f817"
down_revision: Union[str, Sequence[str], None] = "d3f8a1c6b04e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "aps_mps_plan",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("gsystem_id", sa.Integer(), nullable=False),
        sa.Column("plan_no", sa.String(length=50), nullable=True),
        sa.Column("dmd_no", sa.String(length=50), nullable=True),
        sa.Column("item_id", sa.Integer(), nullable=True),
        sa.Column("gsystem_item_id", sa.Integer(), nullable=True),
        sa.Column("item_rev", sa.Integer(), nullable=True),
        sa.Column("routing_id", sa.Integer(), nullable=True),
        sa.Column("gsystem_routing_id", sa.Integer(), nullable=True),
        sa.Column("parea_id", sa.Integer(), nullable=True),
        sa.Column("plan_qty", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("order_qty", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("plan_date", sa.Date(), nullable=True),
        sa.Column("plan_start_date", sa.Date(), nullable=True),
        sa.Column("plan_end_date", sa.Date(), nullable=True),
        sa.Column("delivery_date", sa.Date(), nullable=True),
        sa.Column("prod_end_date", sa.Date(), nullable=True),
        sa.Column("status_cd", sa.String(length=20), nullable=True),
        sa.Column("plan_gbn", sa.String(length=20), nullable=True),
        sa.Column("bom_yn", sa.Boolean(), nullable=True),
        sa.Column("mrp_calc_yn", sa.Boolean(), nullable=True),
        sa.Column("from_work_plan_yn", sa.Boolean(), nullable=True),
        sa.Column("wbs_id", sa.String(length=50), nullable=True),
        sa.Column("wbs_dtl", sa.String(length=50), nullable=True),
        sa.Column("project_no", sa.String(length=50), nullable=True),
        sa.Column("project_nm", sa.String(length=200), nullable=True),
        sa.Column("po_no", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(["item_id"], ["aps_input.aps_item.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["routing_id"], ["aps_input.aps_routing.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gsystem_id", name="uq_mps_plan_gsystem_id"),
        schema="aps_input",
    )
    for column in ("gsystem_id", "plan_no", "item_id", "gsystem_item_id", "routing_id", "parea_id"):
        op.create_index(f"ix_aps_mps_plan_{column}", "aps_mps_plan", [column], schema="aps_input")

    op.create_table(
        "aps_item_routing",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("gsystem_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=True),
        sa.Column("gsystem_item_id", sa.Integer(), nullable=True),
        sa.Column("item_rev", sa.Integer(), nullable=True),
        sa.Column("routing_id", sa.Integer(), nullable=True),
        sa.Column("gsystem_routing_id", sa.Integer(), nullable=True),
        sa.Column("routing_no", sa.String(length=50), nullable=True),
        sa.Column("routing_name", sa.String(length=200), nullable=True),
        sa.Column("gsystem_proc_id", sa.Integer(), nullable=True),
        sa.Column("proc_sno", sa.Integer(), nullable=True),
        sa.Column("proc_name", sa.String(length=200), nullable=True),
        sa.Column("making_gb", sa.String(length=50), nullable=True),
        sa.Column("lead_time", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("inspec_type", sa.String(length=20), nullable=True),
        sa.Column("inspection_yn", sa.Boolean(), nullable=True),
        sa.Column("work_ins_yn", sa.Boolean(), nullable=True),
        sa.Column("sample_qty", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("stock_yn", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["item_id"], ["aps_input.aps_item.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["routing_id"], ["aps_input.aps_routing.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gsystem_id", name="uq_item_routing_gsystem_id"),
        schema="aps_input",
    )
    for column in ("gsystem_id", "item_id", "gsystem_item_id", "item_rev", "routing_id"):
        op.create_index(f"ix_aps_item_routing_{column}", "aps_item_routing", [column], schema="aps_input")


def downgrade() -> None:
    for column in ("gsystem_id", "item_id", "gsystem_item_id", "item_rev", "routing_id"):
        op.drop_index(f"ix_aps_item_routing_{column}", table_name="aps_item_routing", schema="aps_input")
    op.drop_table("aps_item_routing", schema="aps_input")

    for column in ("gsystem_id", "plan_no", "item_id", "gsystem_item_id", "routing_id", "parea_id"):
        op.drop_index(f"ix_aps_mps_plan_{column}", table_name="aps_mps_plan", schema="aps_input")
    op.drop_table("aps_mps_plan", schema="aps_input")

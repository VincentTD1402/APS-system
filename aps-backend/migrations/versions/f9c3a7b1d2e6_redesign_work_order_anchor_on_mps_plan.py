"""redesign work_order to anchor on mps_plan instead of plan_operation

Revision ID: f9c3a7b1d2e6
Revises: a8d1e6f4c3b9
Create Date: 2026-07-20 00:00:00

plan_operation/plan_scenario have no producer since the scheduler was removed
from the backend, so the old work_order FKs pointed at tables nobody writes
to. Drop the old aps_result.work_order and recreate it in aps_input (same
domain as aps_mps_plan/aps_item_routing_spec, which it now anchors on), with
temp_id as a stable local key before G-System confirms the real
work_order_no/id.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f9c3a7b1d2e6"
down_revision: Union[str, Sequence[str], None] = "a8d1e6f4c3b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("work_order", schema="aps_result")

    op.create_table(
        "work_order",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("temp_id", sa.String(length=50), nullable=True),
        sa.Column("mps_plan_id", sa.Integer(), nullable=True),
        sa.Column("item_id", sa.Integer(), nullable=True),
        sa.Column("item_routing_id", sa.Integer(), nullable=True),
        sa.Column("workcenter_id", sa.Integer(), nullable=True),
        sa.Column("work_order_no", sa.String(length=50), nullable=True),
        sa.Column("work_order_serl", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("gsystem_work_order_id", sa.Integer(), nullable=True),
        sa.Column("work_order_date", sa.Date(), nullable=True),
        sa.Column("work_date", sa.Date(), nullable=True),
        sa.Column("qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PLANNED"),
        sa.Column("sync_status", sa.String(length=20), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("response_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["mps_plan_id"], ["aps_input.aps_mps_plan.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["item_id"], ["aps_input.aps_item.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["item_routing_id"], ["aps_input.aps_item_routing_spec.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["workcenter_id"], ["aps_input.aps_workcenter.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("temp_id", name="uq_work_order_temp_id"),
        sa.UniqueConstraint("mps_plan_id", "item_routing_id", name="uq_work_order_mps_plan_item_routing"),
        schema="aps_input",
    )
    for column in (
        "temp_id",
        "mps_plan_id",
        "item_id",
        "item_routing_id",
        "workcenter_id",
        "work_order_no",
        "gsystem_work_order_id",
        "work_date",
    ):
        op.create_index(
            f"ix_work_order_{column}",
            "work_order",
            [column],
            schema="aps_input",
        )


def downgrade() -> None:
    for column in (
        "work_date",
        "gsystem_work_order_id",
        "work_order_no",
        "workcenter_id",
        "item_routing_id",
        "item_id",
        "mps_plan_id",
        "temp_id",
    ):
        op.drop_index(f"ix_work_order_{column}", table_name="work_order", schema="aps_input")
    op.drop_table("work_order", schema="aps_input")

    op.create_table(
        "work_order",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scenario_id", sa.String(length=50), nullable=False),
        sa.Column("plan_op_id", sa.String(length=50), nullable=False),
        sa.Column("plan_id", sa.String(length=50), nullable=False),
        sa.Column("plan_no", sa.String(length=50), nullable=True),
        sa.Column("work_order_no", sa.String(length=50), nullable=False),
        sa.Column("work_order_serl", sa.Integer(), nullable=False),
        sa.Column("work_order_date", sa.Date(), nullable=True),
        sa.Column("work_date", sa.Date(), nullable=True),
        sa.Column("item_id", sa.Integer(), nullable=True),
        sa.Column("item_no", sa.String(length=50), nullable=True),
        sa.Column("workcenter_id", sa.Integer(), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["plan_op_id"], ["aps_result.plan_operation.plan_op_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["scenario_id"], ["aps_result.plan_scenario.scenario_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scenario_id", "plan_op_id", name="uq_work_order_scenario_plan_op"),
        schema="aps_result",
    )
    for column in (
        "scenario_id",
        "plan_op_id",
        "plan_id",
        "plan_no",
        "work_order_no",
        "work_order_date",
        "work_date",
        "item_id",
        "item_no",
        "workcenter_id",
    ):
        op.create_index(
            f"ix_work_order_{column}",
            "work_order",
            [column],
            schema="aps_result",
        )

"""create work_order table

Revision ID: a2d4f6b8c0e1
Revises: f1e2d3c4b5a6
Create Date: 2026-06-01 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a2d4f6b8c0e1"
down_revision: Union[str, Sequence[str], None] = "f1e2d3c4b5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
            ["plan_op_id"],
            ["aps_result.plan_operation.plan_op_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["aps_result.plan_scenario.scenario_id"],
            ondelete="CASCADE",
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


def downgrade() -> None:
    for column in (
        "workcenter_id",
        "item_no",
        "item_id",
        "work_date",
        "work_order_date",
        "work_order_no",
        "plan_no",
        "plan_id",
        "plan_op_id",
        "scenario_id",
    ):
        op.drop_index(f"ix_work_order_{column}", table_name="work_order", schema="aps_result")
    op.drop_table("work_order", schema="aps_result")

"""drop schedule_run and scheduled_operation

Revision ID: b17837ce3bf6
Revises: c9d7f3e8b512
Create Date: 2026-07-16 05:57:13.299757

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b17837ce3bf6'
down_revision: Union[str, Sequence[str], None] = 'c9d7f3e8b512'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop child first (self-FK: aps_scheduled_operation -> aps_schedule_run).
    op.drop_index(
        op.f("ix_aps_input_aps_scheduled_operation_schedule_run_id"),
        table_name="aps_scheduled_operation",
        schema="aps_input",
    )
    op.drop_index(
        op.f("ix_aps_input_aps_scheduled_operation_schedule_lot_key"),
        table_name="aps_scheduled_operation",
        schema="aps_input",
    )
    op.drop_table("aps_scheduled_operation", schema="aps_input")
    op.drop_index(
        op.f("ix_aps_input_aps_schedule_run_status"),
        table_name="aps_schedule_run",
        schema="aps_input",
    )
    op.drop_table("aps_schedule_run", schema="aps_input")


def downgrade() -> None:
    """Downgrade schema — recreate final schema (init + warnings + data_source columns)."""
    op.create_table(
        "aps_schedule_run",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("horizon_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("horizon_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("horizon_minutes", sa.Integer(), nullable=False),
        sa.Column("solver_status", sa.String(length=64), nullable=True),
        sa.Column("objective_value", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("warnings", sa.Text(), nullable=True),
        sa.Column("data_source", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="aps_input",
    )
    op.create_index(
        op.f("ix_aps_input_aps_schedule_run_status"),
        "aps_schedule_run",
        ["status"],
        unique=False,
        schema="aps_input",
    )
    op.create_table(
        "aps_scheduled_operation",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("schedule_run_id", sa.Integer(), nullable=False),
        sa.Column("demand_id", sa.Integer(), nullable=False),
        sa.Column("schedule_lot_key", sa.String(length=200), nullable=True),
        sa.Column("operation_id", sa.Integer(), nullable=False),
        sa.Column("routing_id", sa.Integer(), nullable=False),
        sa.Column("workcenter_id", sa.Integer(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("start_minute", sa.Integer(), nullable=False),
        sa.Column("end_minute", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["demand_id"], ["aps_input.aps_demand.id"]),
        sa.ForeignKeyConstraint(["operation_id"], ["aps_input.aps_operation.id"]),
        sa.ForeignKeyConstraint(["routing_id"], ["aps_input.aps_routing.id"]),
        sa.ForeignKeyConstraint(
            ["schedule_run_id"], ["aps_input.aps_schedule_run.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["workcenter_id"], ["aps_input.aps_workcenter.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="aps_input",
    )
    op.create_index(
        op.f("ix_aps_input_aps_scheduled_operation_schedule_lot_key"),
        "aps_scheduled_operation",
        ["schedule_lot_key"],
        unique=False,
        schema="aps_input",
    )
    op.create_index(
        op.f("ix_aps_input_aps_scheduled_operation_schedule_run_id"),
        "aps_scheduled_operation",
        ["schedule_run_id"],
        unique=False,
        schema="aps_input",
    )

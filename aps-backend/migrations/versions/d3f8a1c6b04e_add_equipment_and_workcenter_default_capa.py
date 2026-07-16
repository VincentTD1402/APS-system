"""add aps_equipment table and workcenter default capacity

Revision ID: d3f8a1c6b04e
Revises: a2d4f6b8c0e1
Create Date: 2026-07-14 14:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d3f8a1c6b04e"
down_revision: Union[str, Sequence[str], None] = "a2d4f6b8c0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Workcenter default operating capacity → 480 min/day (was nullable, no default)
    op.alter_column(
        "aps_workcenter",
        "std_capa",
        server_default="480",
        schema="aps_input",
    )
    op.execute("UPDATE aps_input.aps_workcenter SET std_capa = 480 WHERE std_capa IS NULL")

    op.create_table(
        "aps_equipment",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("gsystem_id", sa.Integer(), nullable=False),
        sa.Column("equipment_id", sa.Integer(), nullable=True),
        sa.Column("equipment_name", sa.String(length=200), nullable=True),
        sa.Column("workcenter_id", sa.Integer(), nullable=True),
        sa.Column("gsystem_workshop_id", sa.Integer(), nullable=True),
        sa.Column("cycle_factor", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("normal_capacity_min", sa.Integer(), nullable=True),
        sa.Column("max_capacity_min", sa.Integer(), nullable=True),
        sa.Column("ot_capacity_min", sa.Integer(), nullable=True),
        sa.Column("holiday_capacity_min", sa.Integer(), nullable=True),
        sa.Column("min_lot_qty", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("max_lot_qty", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("concurrent_lot_qty", sa.Integer(), nullable=True),
        sa.Column("oee_rate", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("efficiency_rate", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("quality_factor", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("availability_rate", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("assign_rate", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("priority_order", sa.Integer(), nullable=True),
        sa.Column("required_skill_level", sa.String(length=20), nullable=True),
        sa.Column("split_allowed", sa.String(length=1), nullable=True),
        sa.Column("valid_from", sa.String(length=8), nullable=True),
        sa.Column("valid_to", sa.String(length=8), nullable=True),
        sa.ForeignKeyConstraint(
            ["workcenter_id"],
            ["aps_input.aps_workcenter.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gsystem_id", name="uq_equipment_gsystem_id"),
        schema="aps_input",
    )
    for column in ("gsystem_id", "equipment_id", "workcenter_id", "gsystem_workshop_id"):
        op.create_index(
            f"ix_aps_equipment_{column}",
            "aps_equipment",
            [column],
            schema="aps_input",
        )


def downgrade() -> None:
    for column in ("gsystem_workshop_id", "workcenter_id", "equipment_id", "gsystem_id"):
        op.drop_index(f"ix_aps_equipment_{column}", table_name="aps_equipment", schema="aps_input")
    op.drop_table("aps_equipment", schema="aps_input")
    op.alter_column(
        "aps_workcenter",
        "std_capa",
        server_default=None,
        schema="aps_input",
    )

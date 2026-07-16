"""create input overlay tables

Revision ID: c1d2e3f4a5b6
Revises: 2169c8ce60d1
Create Date: 2026-05-03 09:00:00.000000

"""
from typing import Union, Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "2169c8ce60d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade: create `aps_input_overlay` schema and overlay tables."""
    # Create schema if not exists
    op.execute("CREATE SCHEMA IF NOT EXISTS aps_input_overlay")

    # aps_demand_overlay
    op.create_table(
        "aps_demand_overlay",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("scenario_id", sa.String(50), nullable=False),
        sa.Column("original_id", sa.Integer(), nullable=True),
        sa.Column("plan_no", sa.String(50), nullable=True),
        sa.Column("item_id", sa.Integer(), nullable=True),
        sa.Column("routing_id", sa.Integer(), nullable=True),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("plan_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("plan_date", sa.Date(), nullable=True),
        sa.Column("delivery_date", sa.Date(), nullable=True),
        sa.Column("status_cd", sa.String(20), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text('false')),
        schema="aps_input_overlay",
    )
    op.create_index(
        "ix_aps_input_overlay_demand_scenario_original",
        "aps_demand_overlay",
        ["scenario_id", "original_id"],
        unique=False,
        schema="aps_input_overlay",
    )
    op.create_unique_constraint(
        "uq_aps_input_overlay_demand_scenario_original",
        "aps_demand_overlay",
        ["scenario_id", "original_id"],
        schema="aps_input_overlay",
    )

    # aps_bom_component_overlay
    op.create_table(
        "aps_bom_component_overlay",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("scenario_id", sa.String(50), nullable=False),
        sa.Column("original_id", sa.Integer(), nullable=True),
        sa.Column("bom_id", sa.Integer(), nullable=True),
        sa.Column("component_item_id", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=True),
        sa.Column("bom_seq", sa.Integer(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text('false')),
        schema="aps_input_overlay",
    )
    op.create_index(
        "ix_aps_input_overlay_bomcomp_scenario_original",
        "aps_bom_component_overlay",
        ["scenario_id", "original_id"],
        schema="aps_input_overlay",
    )
    op.create_unique_constraint(
        "uq_aps_input_overlay_bomcomp_scenario_original",
        "aps_bom_component_overlay",
        ["scenario_id", "original_id"],
        schema="aps_input_overlay",
    )

    # aps_workcenter_overlay
    op.create_table(
        "aps_workcenter_overlay",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("scenario_id", sa.String(50), nullable=False),
        sa.Column("original_id", sa.Integer(), nullable=True),
        sa.Column("gsystem_id", sa.Integer(), nullable=True),
        sa.Column("workcenter_no", sa.String(50), nullable=True),
        sa.Column("workcenter_name", sa.String(200), nullable=True),
        sa.Column("workshop_cd", sa.String(50), nullable=True),
        sa.Column("std_capa", sa.Numeric(10, 2), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text('false')),
        schema="aps_input_overlay",
    )
    op.create_index(
        "ix_aps_input_overlay_wc_scenario_original",
        "aps_workcenter_overlay",
        ["scenario_id", "original_id"],
        schema="aps_input_overlay",
    )
    op.create_unique_constraint(
        "uq_aps_input_overlay_wc_scenario_original",
        "aps_workcenter_overlay",
        ["scenario_id", "original_id"],
        schema="aps_input_overlay",
    )


def downgrade() -> None:
    """Downgrade: drop overlay tables and schema."""
    op.drop_constraint(
        "uq_aps_input_overlay_wc_scenario_original",
        "aps_workcenter_overlay",
        schema="aps_input_overlay",
    )
    op.drop_index("ix_aps_input_overlay_wc_scenario_original", table_name="aps_workcenter_overlay", schema="aps_input_overlay")
    op.drop_table("aps_workcenter_overlay", schema="aps_input_overlay")

    op.drop_constraint(
        "uq_aps_input_overlay_bomcomp_scenario_original",
        "aps_bom_component_overlay",
        schema="aps_input_overlay",
    )
    op.drop_index("ix_aps_input_overlay_bomcomp_scenario_original", table_name="aps_bom_component_overlay", schema="aps_input_overlay")
    op.drop_table("aps_bom_component_overlay", schema="aps_input_overlay")

    op.drop_constraint(
        "uq_aps_input_overlay_demand_scenario_original",
        "aps_demand_overlay",
        schema="aps_input_overlay",
    )
    op.drop_index("ix_aps_input_overlay_demand_scenario_original", table_name="aps_demand_overlay", schema="aps_input_overlay")
    op.drop_table("aps_demand_overlay", schema="aps_input_overlay")

    op.execute("DROP SCHEMA IF EXISTS aps_input_overlay CASCADE")

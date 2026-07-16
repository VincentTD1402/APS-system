"""add workcenter_id to aps_item_routing

Revision ID: b7e19c5a2d43
Revises: f4b8d2a1c630
Create Date: 2026-07-14 18:40:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7e19c5a2d43"
down_revision: Union[str, Sequence[str], None] = "f4b8d2a1c630"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "aps_item_routing",
        sa.Column("workcenter_id", sa.Integer(), nullable=True),
        schema="aps_input",
    )
    op.add_column(
        "aps_item_routing",
        sa.Column("gsystem_workcenter_id", sa.Integer(), nullable=True),
        schema="aps_input",
    )
    op.create_foreign_key(
        "aps_item_routing_workcenter_id_fkey",
        "aps_item_routing",
        "aps_workcenter",
        ["workcenter_id"],
        ["id"],
        source_schema="aps_input",
        referent_schema="aps_input",
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_aps_item_routing_workcenter_id", "aps_item_routing", ["workcenter_id"], schema="aps_input"
    )


def downgrade() -> None:
    op.drop_index("ix_aps_item_routing_workcenter_id", table_name="aps_item_routing", schema="aps_input")
    op.drop_constraint(
        "aps_item_routing_workcenter_id_fkey", "aps_item_routing", schema="aps_input", type_="foreignkey"
    )
    op.drop_column("aps_item_routing", "gsystem_workcenter_id", schema="aps_input")
    op.drop_column("aps_item_routing", "workcenter_id", schema="aps_input")

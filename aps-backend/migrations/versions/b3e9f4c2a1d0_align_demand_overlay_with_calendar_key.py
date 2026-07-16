"""align demand overlay key with calendar style

Revision ID: b3e9f4c2a1d0
Revises: a8b9c0d1e2f3
Create Date: 2026-05-05 09:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b3e9f4c2a1d0"
down_revision: Union[str, Sequence[str], None] = "a8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove invalid rows before enforcing NOT NULL on original_id
    op.execute("DELETE FROM aps_input_overlay.aps_demand_overlay WHERE original_id IS NULL")

    # Drop old PK on surrogate id and align key to (scenario_id, original_id)
    op.drop_constraint(
        "aps_demand_overlay_pkey",
        "aps_demand_overlay",
        schema="aps_input_overlay",
        type_="primary",
    )

    op.alter_column(
        "aps_demand_overlay",
        "original_id",
        existing_type=sa.Integer(),
        nullable=False,
        schema="aps_input_overlay",
    )

    # Unique constraint becomes redundant once this composite PK is in place.
    op.drop_constraint(
        "uq_aps_input_overlay_demand_scenario_original",
        "aps_demand_overlay",
        schema="aps_input_overlay",
        type_="unique",
    )

    op.create_primary_key(
        "aps_demand_overlay_pkey",
        "aps_demand_overlay",
        ["scenario_id", "original_id"],
        schema="aps_input_overlay",
    )


def downgrade() -> None:
    op.drop_constraint(
        "aps_demand_overlay_pkey",
        "aps_demand_overlay",
        schema="aps_input_overlay",
        type_="primary",
    )

    op.create_primary_key(
        "aps_demand_overlay_pkey",
        "aps_demand_overlay",
        ["id"],
        schema="aps_input_overlay",
    )

    op.create_unique_constraint(
        "uq_aps_input_overlay_demand_scenario_original",
        "aps_demand_overlay",
        ["scenario_id", "original_id"],
        schema="aps_input_overlay",
    )

    op.alter_column(
        "aps_demand_overlay",
        "original_id",
        existing_type=sa.Integer(),
        nullable=True,
        schema="aps_input_overlay",
    )

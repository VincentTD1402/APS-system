"""add data_source column to demand and schedule_run

Revision ID: 7f4bc6f20887
Revises: b1c8e14f5867
Create Date: 2026-05-04 15:51:36.476181

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f4bc6f20887'
down_revision: Union[str, Sequence[str], None] = 'b1c8e14f5867'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "aps_demand",
        sa.Column("data_source", sa.String(20), nullable=False, server_default="gsystem"),
        schema="aps_input",
    )
    op.create_index(
        "ix_aps_demand_data_source", "aps_demand", ["data_source"], schema="aps_input"
    )
    op.add_column(
        "aps_schedule_run",
        sa.Column("data_source", sa.String(20), nullable=True),
        schema="aps_input",
    )


def downgrade() -> None:
    op.drop_column("aps_schedule_run", "data_source", schema="aps_input")
    op.drop_index("ix_aps_demand_data_source", "aps_demand", schema="aps_input")
    op.drop_column("aps_demand", "data_source", schema="aps_input")

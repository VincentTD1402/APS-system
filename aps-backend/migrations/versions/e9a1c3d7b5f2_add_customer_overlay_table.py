"""add customer overlay table

Revision ID: e9a1c3d7b5f2
Revises: c4f1b2a9d8e7
Create Date: 2026-05-11 15:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e9a1c3d7b5f2"
down_revision: Union[str, Sequence[str], None] = "c4f1b2a9d8e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Keep idempotent for environments where schema may be missing.
    op.execute("CREATE SCHEMA IF NOT EXISTS aps_input_overlay")

    op.create_table(
        "aps_customer_overlay",
        sa.Column("scenario_id", sa.String(length=50), nullable=False),
        sa.Column("original_id", sa.Integer(), nullable=False),
        sa.Column("customer_no", sa.String(length=50), nullable=True),
        sa.Column("customer_name", sa.String(length=200), nullable=True),
        sa.Column("customer_type", sa.String(length=20), nullable=True),
        sa.Column("impact_score", sa.Integer(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.PrimaryKeyConstraint("scenario_id", "original_id", name="pk_aps_customer_overlay"),
        schema="aps_input_overlay",
    )
    op.create_index(
        "ix_aps_input_overlay_customer_scenario_original",
        "aps_customer_overlay",
        ["scenario_id", "original_id"],
        unique=False,
        schema="aps_input_overlay",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_aps_input_overlay_customer_scenario_original",
        table_name="aps_customer_overlay",
        schema="aps_input_overlay",
    )
    op.drop_table("aps_customer_overlay", schema="aps_input_overlay")


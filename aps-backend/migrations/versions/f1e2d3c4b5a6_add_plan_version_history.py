"""add plan version history

Revision ID: f1e2d3c4b5a6
Revises: e9a1c3d7b5f2
Create Date: 2026-05-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f1e2d3c4b5a6"
down_revision: Union[str, Sequence[str], None] = "e9a1c3d7b5f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plan_version",
        sa.Column("version_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("scenario_id", sa.String(length=50), nullable=False),
        sa.Column("run_id", sa.String(length=50), nullable=True),
        sa.Column("parent_version_id", sa.Integer(), nullable=True),
        sa.Column("version_type", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("horizon_start", sa.Date(), nullable=False),
        sa.Column("horizon_end", sa.Date(), nullable=False),
        sa.Column("change_summary", sa.String(length=500), nullable=True),
        sa.Column("created_by", sa.String(length=100), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(
            ["parent_version_id"],
            ["aps_result.plan_version.version_id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("version_id"),
        schema="aps_result",
    )
    op.create_index("ix_aps_result_plan_version_created_at", "plan_version", ["created_at"], schema="aps_result")
    op.create_index("ix_aps_result_plan_version_current", "plan_version", ["is_current"], schema="aps_result")
    op.create_index("ix_aps_result_plan_version_parent_version_id", "plan_version", ["parent_version_id"], schema="aps_result")
    op.create_index("ix_aps_result_plan_version_run_id", "plan_version", ["run_id"], schema="aps_result")
    op.create_index("ix_aps_result_plan_version_scenario_created", "plan_version", ["scenario_id", "created_at"], schema="aps_result")
    op.create_index("ix_aps_result_plan_version_scenario_id", "plan_version", ["scenario_id"], schema="aps_result")
    op.create_index("ix_aps_result_plan_version_version_no", "plan_version", ["version_no"], schema="aps_result")
    op.create_index("ix_aps_result_plan_version_version_type", "plan_version", ["version_type"], schema="aps_result")

    op.create_table(
        "plan_version_snapshot",
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("scenario_id", sa.String(length=50), nullable=False),
        sa.Column("snapshot_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["aps_result.plan_version.version_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("version_id"),
        schema="aps_result",
    )
    op.create_index(
        "ix_aps_result_plan_version_snapshot_scenario_id",
        "plan_version_snapshot",
        ["scenario_id"],
        schema="aps_result",
    )


def downgrade() -> None:
    op.drop_index("ix_aps_result_plan_version_snapshot_scenario_id", table_name="plan_version_snapshot", schema="aps_result")
    op.drop_table("plan_version_snapshot", schema="aps_result")
    op.drop_index("ix_aps_result_plan_version_version_type", table_name="plan_version", schema="aps_result")
    op.drop_index("ix_aps_result_plan_version_version_no", table_name="plan_version", schema="aps_result")
    op.drop_index("ix_aps_result_plan_version_scenario_id", table_name="plan_version", schema="aps_result")
    op.drop_index("ix_aps_result_plan_version_scenario_created", table_name="plan_version", schema="aps_result")
    op.drop_index("ix_aps_result_plan_version_run_id", table_name="plan_version", schema="aps_result")
    op.drop_index("ix_aps_result_plan_version_parent_version_id", table_name="plan_version", schema="aps_result")
    op.drop_index("ix_aps_result_plan_version_current", table_name="plan_version", schema="aps_result")
    op.drop_index("ix_aps_result_plan_version_created_at", table_name="plan_version", schema="aps_result")
    op.drop_table("plan_version", schema="aps_result")

"""drop orphaned evaluation/material/version/overlay tables

Revision ID: d4a7f92e6c31
Revises: b17837ce3bf6
Create Date: 2026-07-16

Drops 13 tables left with no application code reading/writing them after the
action-execution, plan-version, and scenario-overlay feature removals:
  aps_result: plan_evaluation_detail, plan_evaluation_summary, plan_material,
              plan_material_override, plan_version, plan_version_snapshot
  aps_input_overlay: aps_bom_component_overlay, aps_calendar_overlay,
              aps_customer_overlay, aps_demand_overlay, aps_workcenter_overlay
  aps_result_overlay: plan_material_overlay, plan_order_overlay

plan_evaluation_action (kept — still read by suggestion_service) had a FK to
plan_evaluation_summary; that FK is dropped first and scenario_id/impacted_id
become plain (unconstrained) columns.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd4a7f92e6c31'
down_revision = 'b17837ce3bf6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop FKs on the kept plan_evaluation_action pointing at tables being dropped.
    op.drop_constraint(
        "plan_evaluation_action_scenario_id_fkey",
        "plan_evaluation_action",
        schema="aps_result",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_plan_eval_action_impacted_id",
        "plan_evaluation_action",
        schema="aps_result",
        type_="foreignkey",
    )

    op.drop_table("plan_evaluation_detail", schema="aps_result")
    op.drop_table("plan_evaluation_summary", schema="aps_result")
    op.drop_table("plan_material", schema="aps_result")
    op.drop_table("plan_material_override", schema="aps_result")
    op.drop_table("plan_version_snapshot", schema="aps_result")
    op.drop_table("plan_version", schema="aps_result")

    op.drop_table("aps_bom_component_overlay", schema="aps_input_overlay")
    op.drop_table("aps_calendar_overlay", schema="aps_input_overlay")
    op.drop_table("aps_customer_overlay", schema="aps_input_overlay")
    op.drop_table("aps_demand_overlay", schema="aps_input_overlay")
    op.drop_table("aps_workcenter_overlay", schema="aps_input_overlay")

    op.drop_table("plan_material_overlay", schema="aps_result_overlay")
    op.drop_table("plan_order_overlay", schema="aps_result_overlay")


def downgrade() -> None:
    op.create_table(
        "plan_evaluation_summary",
        sa.Column("scenario_id", sa.String(50), sa.ForeignKey("aps_result.plan_scenario.scenario_id"), primary_key=True),
        sa.Column("due_date_compliance", sa.Numeric(5, 2), nullable=False),
        sa.Column("due_date_status", sa.String(20), nullable=False),
        sa.Column("material_shortage_cnt", sa.Integer, nullable=False),
        sa.Column("material_status", sa.String(20), nullable=False),
        sa.Column("max_utilization_rate", sa.Numeric(10, 2), nullable=False),
        sa.Column("utilization_status", sa.String(20), nullable=False),
        sa.Column("risk_count", sa.Integer, nullable=False),
        sa.Column("risk_status", sa.String(20), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        schema="aps_result",
    )
    op.create_index(
        "ix_plan_evaluation_summary_evaluated_at",
        "plan_evaluation_summary",
        ["evaluated_at"],
        schema="aps_result",
    )

    op.create_table(
        "plan_evaluation_detail",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "scenario_id", sa.String(50),
            sa.ForeignKey("aps_result.plan_evaluation_summary.scenario_id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("plan_id", sa.String(50), index=True),
        sa.Column("metric_type", sa.String(20), nullable=False, index=True),
        sa.Column("ref_type", sa.String(20), nullable=False, index=True),
        sa.Column("ref_id", sa.String(50), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, index=True),
        schema="aps_result",
    )

    op.create_table(
        "plan_material",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("scenario_id", sa.String(50), nullable=False),
        sa.Column("plan_id", sa.String(50), nullable=False),
        sa.Column("item_id", sa.Integer, sa.ForeignKey("aps_input.aps_item.id"), nullable=False),
        sa.Column("allocated_qty", sa.Numeric(18, 4), server_default="0.0"),
        schema="aps_result",
    )

    op.create_table(
        "plan_material_override",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("scenario_id", sa.String(50), nullable=False),
        sa.Column("plan_id", sa.String(50), nullable=False),
        sa.Column("original_item_id", sa.Integer, nullable=False),
        sa.Column("substitute_item_id", sa.Integer, nullable=False),
        sa.Column("substitute_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("status", sa.String(20), server_default="APPLIED"),
        schema="aps_result",
    )

    op.create_table(
        "plan_version",
        sa.Column("version_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("version_no", sa.Integer, nullable=False, index=True),
        sa.Column("scenario_id", sa.String(50), nullable=False, index=True),
        sa.Column("run_id", sa.String(50), index=True),
        sa.Column("parent_version_id", sa.Integer, sa.ForeignKey("aps_result.plan_version.version_id", ondelete="SET NULL"), index=True),
        sa.Column("version_type", sa.String(30), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("horizon_start", sa.Date, nullable=False),
        sa.Column("horizon_end", sa.Date, nullable=False),
        sa.Column("change_summary", sa.String(500)),
        sa.Column("created_by", sa.String(100), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("restored_at", sa.DateTime(timezone=True)),
        sa.Column("is_current", sa.Boolean, nullable=False, server_default=sa.false()),
        schema="aps_result",
    )
    op.create_index(
        "ix_plan_version_scenario_created", "plan_version",
        ["scenario_id", "created_at"], schema="aps_result",
    )
    op.create_index(
        "ix_plan_version_current", "plan_version", ["is_current"], schema="aps_result",
    )

    op.create_table(
        "plan_version_snapshot",
        sa.Column("version_id", sa.Integer, sa.ForeignKey("aps_result.plan_version.version_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("scenario_id", sa.String(50), nullable=False, index=True),
        sa.Column("snapshot_data", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="aps_result",
    )

    op.create_table(
        "aps_demand_overlay",
        sa.Column("scenario_id", sa.String(50), primary_key=True),
        sa.Column("original_id", sa.Integer, primary_key=True),
        sa.Column("plan_no", sa.String(50)),
        sa.Column("item_id", sa.Integer),
        sa.Column("routing_id", sa.Integer),
        sa.Column("customer_id", sa.Integer),
        sa.Column("plan_qty", sa.Numeric(18, 4)),
        sa.Column("plan_date", sa.Date),
        sa.Column("delivery_date", sa.Date),
        sa.Column("status_cd", sa.String(20)),
        sa.Column("is_deleted", sa.Boolean, nullable=False),
        schema="aps_input_overlay",
    )

    op.create_table(
        "aps_bom_component_overlay",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("scenario_id", sa.String(50), nullable=False),
        sa.Column("original_id", sa.Integer, index=True),
        sa.Column("bom_id", sa.Integer),
        sa.Column("component_item_id", sa.Integer),
        sa.Column("quantity", sa.Numeric(18, 4)),
        sa.Column("bom_seq", sa.Integer),
        sa.Column("is_deleted", sa.Boolean, nullable=False),
        schema="aps_input_overlay",
    )

    op.create_table(
        "aps_workcenter_overlay",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("scenario_id", sa.String(50), nullable=False),
        sa.Column("original_id", sa.Integer, index=True),
        sa.Column("gsystem_id", sa.Integer),
        sa.Column("workcenter_no", sa.String(50)),
        sa.Column("workcenter_name", sa.String(200)),
        sa.Column("workshop_cd", sa.String(50)),
        sa.Column("std_capa", sa.Numeric(10, 2)),
        sa.Column("is_deleted", sa.Boolean, nullable=False),
        schema="aps_input_overlay",
    )

    op.create_table(
        "aps_customer_overlay",
        sa.Column("scenario_id", sa.String(50), primary_key=True),
        sa.Column("original_id", sa.Integer, primary_key=True),
        sa.Column("customer_no", sa.String(50)),
        sa.Column("customer_name", sa.String(200)),
        sa.Column("customer_type", sa.String(20)),
        sa.Column("impact_score", sa.Integer),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.false()),
        schema="aps_input_overlay",
    )

    op.create_table(
        "aps_calendar_overlay",
        sa.Column("scenario_id", sa.String(50), primary_key=True),
        sa.Column("work_date", sa.Date, primary_key=True),
        sa.Column("day_of_week_cd", sa.String(20)),
        sa.Column("work_gb_cd", sa.String(20)),
        sa.Column("is_holiday", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("work_hours", sa.Numeric(6, 4), nullable=False, server_default="0.0"),
        sa.CheckConstraint("work_hours >= 0", name="ck_calendar_overlay_work_hours_non_negative"),
        schema="aps_input_overlay",
    )

    op.create_table(
        "plan_order_overlay",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("scenario_id", sa.String(50), nullable=False, index=True),
        sa.Column("original_plan_id", sa.String(50), nullable=False, index=True),
        sa.Column("priority_score", sa.Numeric(10, 2), nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.false()),
        schema="aps_result_overlay",
    )
    op.create_index(
        "ix_plan_order_overlay_scenario_plan", "plan_order_overlay",
        ["scenario_id", "original_plan_id"], schema="aps_result_overlay",
    )

    op.create_table(
        "plan_material_overlay",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("scenario_id", sa.String(50), nullable=False, index=True),
        sa.Column("original_id", sa.Integer, nullable=False, index=True),
        sa.Column("allocated_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.false()),
        schema="aps_result_overlay",
    )
    op.create_index(
        "ix_plan_material_overlay_scenario_id", "plan_material_overlay",
        ["scenario_id", "original_id"], schema="aps_result_overlay",
    )

    op.create_foreign_key(
        "plan_evaluation_action_scenario_id_fkey",
        "plan_evaluation_action", "plan_evaluation_summary",
        ["scenario_id"], ["scenario_id"],
        source_schema="aps_result", referent_schema="aps_result",
    )
    op.create_foreign_key(
        "fk_plan_eval_action_impacted_id",
        "plan_evaluation_action", "plan_impacted_order",
        ["impacted_id"], ["impacted_id"],
        source_schema="aps_result", referent_schema="aps_result",
        ondelete="SET NULL",
    )

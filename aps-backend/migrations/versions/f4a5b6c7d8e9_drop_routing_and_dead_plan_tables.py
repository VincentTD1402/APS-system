"""drop routing/process-step and dead plan_* tables; rebuild item_routing_spec

Revision ID: f4a5b6c7d8e9
Revises: e2f3a4b5c6d7
Create Date: 2026-07-28 06:00:00

itemRoutingMng (GET /pd/itemRoutingMng?itemId=) is now the ONLY routing/
process-step source APS uses. The routing/routing_item/routing_process/
item_process pending feeds fed aps_routing/aps_routing_item/aps_routing_step/
aps_item_process_step, none of which had any real downstream reader (only
the disabled ontology ABox pipeline touched them) — dropped.

That cascades into a second, unrelated dead cluster: plan_order/
plan_operation/plan_scenario/plan_shortage/plan_impacted_order/
plan_utilization/workcenter_load (an old scenario-based planning subsystem,
zero route/service ever queries or creates them) — plan_operation and
workcenter_load hard-FK to aps_routing_step/aps_routing, so they must go too.
plan_evaluation_action is KEPT (still read by services/llm/suggestion_service.py)
— its scenario_id/plan_id/impacted_id were already plain unconstrained columns
(set in a prior migration), so nothing to change there.

aps_item_routing_spec is rebuilt to mirror the verified live itemRoutingMng
response exactly — columns that never matched any real field (routing_id,
gsystem_routing_id, routing_no, routing_name, lead_time, inspec_type,
sample_qty) are dropped; the remaining raw response fields are added.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f4a5b6c7d8e9'
down_revision = 'e2f3a4b5c6d7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # llm_response_cache.scenario_id is a live, actively-used cache key
    # (services/llm/llm_cache.py) — drop only its FK to plan_scenario, keep the column.
    op.drop_constraint(
        "llm_response_cache_scenario_id_fkey", "llm_response_cache", schema="aps_result", type_="foreignkey"
    )

    # ── Drop dead plan_* cluster (children before parents) ────────────────────
    op.drop_table("workcenter_load", schema="aps_result")
    op.drop_table("plan_utilization", schema="aps_result")
    op.drop_table("plan_impacted_order", schema="aps_result")
    op.drop_table("plan_shortage", schema="aps_result")
    op.drop_table("plan_operation", schema="aps_result")
    op.drop_table("plan_order", schema="aps_result")
    op.drop_table("plan_scenario", schema="aps_result")

    # ── Drop dead routing/process-step cluster (children before parents) ──────
    op.drop_table("aps_item_process_step", schema="aps_input")
    op.drop_table("aps_routing_item", schema="aps_input")
    op.drop_table("aps_routing_step", schema="aps_input")

    # ── Drop routing_id FKs on surviving tables before dropping aps_routing ────
    op.drop_column("aps_mps_plan", "routing_id", schema="aps_input")
    op.drop_column("aps_mps_plan", "gsystem_routing_id", schema="aps_input")
    op.drop_column("aps_demand", "routing_id", schema="aps_input")
    op.drop_constraint("aps_item_routing_routing_id_fkey", "aps_item_routing_spec", schema="aps_input", type_="foreignkey")
    op.drop_column("aps_item_routing_spec", "routing_id", schema="aps_input")

    op.drop_table("aps_routing", schema="aps_input")

    # ── Rebuild the rest of aps_item_routing_spec to mirror the real itemRoutingMng response ──
    op.drop_column("aps_item_routing_spec", "gsystem_routing_id", schema="aps_input")
    op.drop_column("aps_item_routing_spec", "routing_no", schema="aps_input")
    op.drop_column("aps_item_routing_spec", "routing_name", schema="aps_input")
    op.drop_column("aps_item_routing_spec", "lead_time", schema="aps_input")
    op.drop_column("aps_item_routing_spec", "inspec_type", schema="aps_input")
    op.drop_column("aps_item_routing_spec", "sample_qty", schema="aps_input")

    op.add_column("aps_item_routing_spec", sa.Column("item_no", sa.String(50), nullable=True), schema="aps_input")
    op.add_column("aps_item_routing_spec", sa.Column("item_name", sa.String(200), nullable=True), schema="aps_input")
    op.add_column("aps_item_routing_spec", sa.Column("workcenter_name_raw", sa.String(200), nullable=True), schema="aps_input")
    op.add_column("aps_item_routing_spec", sa.Column("corp_id", sa.Integer(), nullable=True), schema="aps_input")
    op.add_column("aps_item_routing_spec", sa.Column("corp_name", sa.String(200), nullable=True), schema="aps_input")
    op.add_column("aps_item_routing_spec", sa.Column("biz_id", sa.Integer(), nullable=True), schema="aps_input")
    op.add_column("aps_item_routing_spec", sa.Column("item_cls1", sa.String(50), nullable=True), schema="aps_input")
    op.add_column("aps_item_routing_spec", sa.Column("reg_dt", sa.DateTime(), nullable=True), schema="aps_input")
    op.add_column("aps_item_routing_spec", sa.Column("reg_user_id", sa.Integer(), nullable=True), schema="aps_input")
    op.add_column("aps_item_routing_spec", sa.Column("reg_user_name", sa.String(100), nullable=True), schema="aps_input")


def downgrade() -> None:
    # ── Revert aps_item_routing_spec ───────────────────────────────────────────
    op.drop_column("aps_item_routing_spec", "reg_user_name", schema="aps_input")
    op.drop_column("aps_item_routing_spec", "reg_user_id", schema="aps_input")
    op.drop_column("aps_item_routing_spec", "reg_dt", schema="aps_input")
    op.drop_column("aps_item_routing_spec", "item_cls1", schema="aps_input")
    op.drop_column("aps_item_routing_spec", "biz_id", schema="aps_input")
    op.drop_column("aps_item_routing_spec", "corp_name", schema="aps_input")
    op.drop_column("aps_item_routing_spec", "corp_id", schema="aps_input")
    op.drop_column("aps_item_routing_spec", "workcenter_name_raw", schema="aps_input")
    op.drop_column("aps_item_routing_spec", "item_name", schema="aps_input")
    op.drop_column("aps_item_routing_spec", "item_no", schema="aps_input")

    op.add_column("aps_item_routing_spec", sa.Column("sample_qty", sa.Numeric(10, 2), nullable=True), schema="aps_input")
    op.add_column("aps_item_routing_spec", sa.Column("inspec_type", sa.String(20), nullable=True), schema="aps_input")
    op.add_column("aps_item_routing_spec", sa.Column("lead_time", sa.Numeric(10, 2), nullable=True), schema="aps_input")
    op.add_column("aps_item_routing_spec", sa.Column("routing_name", sa.String(200), nullable=True), schema="aps_input")
    op.add_column("aps_item_routing_spec", sa.Column("routing_no", sa.String(50), nullable=True), schema="aps_input")
    op.add_column("aps_item_routing_spec", sa.Column("gsystem_routing_id", sa.Integer(), nullable=True), schema="aps_input")
    op.add_column("aps_item_routing_spec", sa.Column("routing_id", sa.Integer(), nullable=True), schema="aps_input")

    # ── Recreate aps_routing (parent first) ────────────────────────────────────
    op.create_table(
        "aps_routing",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("gsystem_id", sa.Integer(), unique=True, nullable=True),
        sa.Column("routing_no", sa.String(50), nullable=True),
        sa.Column("routing_name", sa.String(200), nullable=True),
        sa.Column("routing_type_cd", sa.String(20), nullable=True),
        sa.Column("std_capa", sa.Numeric(10, 2), nullable=True),
        schema="aps_input",
    )

    op.create_foreign_key(
        "aps_item_routing_routing_id_fkey",
        "aps_item_routing_spec", "aps_routing",
        ["routing_id"], ["id"],
        source_schema="aps_input", referent_schema="aps_input",
        ondelete="SET NULL",
    )

    op.add_column("aps_demand", sa.Column("routing_id", sa.Integer(), nullable=True), schema="aps_input")
    op.create_foreign_key(
        "aps_demand_routing_id_fkey", "aps_demand", "aps_routing",
        ["routing_id"], ["id"],
        source_schema="aps_input", referent_schema="aps_input",
    )

    op.add_column("aps_mps_plan", sa.Column("gsystem_routing_id", sa.Integer(), nullable=True), schema="aps_input")
    op.add_column("aps_mps_plan", sa.Column("routing_id", sa.Integer(), nullable=True), schema="aps_input")
    op.create_foreign_key(
        "aps_mps_plan_routing_id_fkey", "aps_mps_plan", "aps_routing",
        ["routing_id"], ["id"],
        source_schema="aps_input", referent_schema="aps_input",
        ondelete="SET NULL",
    )

    op.create_table(
        "aps_routing_step",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("routing_id", sa.Integer(), sa.ForeignKey("aps_input.aps_routing.id"), nullable=False),
        sa.Column("process_seq", sa.Integer(), nullable=False),
        sa.Column("gsystem_process_id", sa.Integer(), nullable=True),
        sa.Column("proc_no", sa.String(50), nullable=True),
        sa.Column("proc_name", sa.String(200), nullable=True),
        sa.Column("workcenter_id", sa.Integer(), sa.ForeignKey("aps_input.aps_workcenter.id"), nullable=True),
        sa.Column("work_time_hours", sa.Numeric(10, 4), nullable=True),
        sa.Column("setup_time_hours", sa.Numeric(10, 4), nullable=True),
        sa.UniqueConstraint("routing_id", "process_seq"),
        sa.CheckConstraint("work_time_hours IS NULL OR work_time_hours >= 0", name="ck_operation_work_time_non_negative"),
        sa.CheckConstraint("setup_time_hours IS NULL OR setup_time_hours >= 0", name="ck_operation_setup_time_non_negative"),
        schema="aps_input",
    )

    op.create_table(
        "aps_routing_item",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("routing_id", sa.Integer(), sa.ForeignKey("aps_input.aps_routing.id"), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("aps_input.aps_item.id"), nullable=False),
        sa.UniqueConstraint("routing_id", "item_id"),
        schema="aps_input",
    )

    op.create_table(
        "aps_item_process_step",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("aps_input.aps_item.id"), nullable=False),
        sa.Column("routing_id", sa.Integer(), sa.ForeignKey("aps_input.aps_routing.id"), nullable=True),
        sa.Column("gsystem_proc_id", sa.Integer(), nullable=True),
        sa.Column("proc_sno", sa.Integer(), nullable=False),
        sa.Column("making_gb", sa.String(20), nullable=True),
        sa.Column("inspection_yn", sa.Boolean(), nullable=True),
        sa.Column("work_ins_yn", sa.Boolean(), nullable=True),
        sa.Column("stock_yn", sa.Boolean(), nullable=True),
        sa.Column("rev_no", sa.Integer(), nullable=True),
        sa.Column("work_time_hours", sa.Numeric(10, 4), nullable=True),
        sa.UniqueConstraint("routing_id", "item_id", "proc_sno", name="uq_item_process_routing_item_sno"),
        schema="aps_input",
    )

    # ── Recreate plan_scenario (parent first) ──────────────────────────────────
    op.create_table(
        "plan_scenario",
        sa.Column("scenario_id", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("horizon_start", sa.Date(), nullable=False),
        sa.Column("horizon_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_message", sa.String(500), nullable=True),
        sa.Column("scenario_type", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("what_if_index", sa.Integer(), nullable=True),
        sa.Column("parent_scenario_id", sa.String(50), sa.ForeignKey("aps_result.plan_scenario.scenario_id", ondelete="SET NULL"), nullable=True, index=True),
        schema="aps_result",
    )

    op.create_table(
        "plan_order",
        sa.Column("plan_id", sa.String(50), primary_key=True),
        sa.Column("scenario_id", sa.String(50), sa.ForeignKey("aps_result.plan_scenario.scenario_id"), nullable=False),
        sa.Column("demand_id", sa.Integer(), sa.ForeignKey("aps_input.aps_demand.id"), nullable=True, index=True),
        sa.Column("demand_line_id", sa.String(50), nullable=True, index=True),
        sa.Column("planned_start_date", sa.Date(), nullable=False, index=True),
        sa.Column("planned_finish_date", sa.Date(), nullable=False, index=True),
        sa.Column("planned_ship_date", sa.Date(), nullable=False),
        sa.Column("plan_status", sa.String(20), nullable=False, index=True),
        sa.Column("late_days", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(50), nullable=True, index=True),
        sa.Column("priority_score", sa.Numeric(10, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="aps_result",
    )

    op.create_table(
        "plan_operation",
        sa.Column("plan_op_id", sa.String(50), primary_key=True),
        sa.Column("plan_id", sa.String(50), sa.ForeignKey("aps_result.plan_order.plan_id", ondelete="CASCADE"), nullable=False),
        sa.Column("op_code", sa.String(50), nullable=False),
        sa.Column("workcenter_id", sa.Integer(), sa.ForeignKey("aps_input.aps_workcenter.id"), nullable=False, index=True),
        sa.Column("operation_id", sa.Integer(), sa.ForeignKey("aps_input.aps_routing_step.id"), nullable=False, index=True),
        sa.Column("routing_id", sa.Integer(), sa.ForeignKey("aps_input.aps_routing.id"), nullable=False),
        sa.Column("planned_start_dt", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("planned_end_dt", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("load_minutes", sa.Numeric(10, 2), nullable=False),
        sa.Column("scenario_id", sa.String(50), sa.ForeignKey("aps_result.plan_scenario.scenario_id"), nullable=False),
        sa.Column("run_id", sa.String(50), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="aps_result",
    )

    op.create_table(
        "plan_shortage",
        sa.Column("shortage_id", sa.String(50), primary_key=True),
        sa.Column("plan_id", sa.String(50), sa.ForeignKey("aps_result.plan_order.plan_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("aps_input.aps_item.id"), nullable=False, index=True),
        sa.Column("op_code", sa.String(50), nullable=False, index=True),
        sa.Column("need_date", sa.Date(), nullable=False, index=True),
        sa.Column("required_qty", sa.Numeric(15, 4), nullable=False),
        sa.Column("available_qty", sa.Numeric(15, 4), nullable=False),
        sa.Column("shortage_qty", sa.Numeric(15, 4), nullable=False, index=True),
        sa.Column("cause", sa.String(20), nullable=False, index=True),
        sa.Column("scenario_id", sa.String(50), sa.ForeignKey("aps_result.plan_scenario.scenario_id"), nullable=False, index=True),
        sa.Column("run_id", sa.String(50), nullable=True),
        sa.Column("impact_score", sa.Numeric(10, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="aps_result",
    )

    op.create_table(
        "plan_impacted_order",
        sa.Column("impacted_id", sa.String(50), primary_key=True),
        sa.Column("scenario_id", sa.String(50), sa.ForeignKey("aps_result.plan_scenario.scenario_id"), nullable=False),
        sa.Column("plan_id", sa.String(50), sa.ForeignKey("aps_result.plan_order.plan_id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(50), nullable=True),
        sa.Column("demand_id", sa.Integer(), sa.ForeignKey("aps_input.aps_demand.id"), nullable=True, index=True),
        sa.Column("reason_type", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("message", sa.String(500), nullable=True),
        sa.Column("llm_insight", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Index("idx_plan_impacted_order_scenario", "scenario_id"),
        sa.Index("idx_plan_impacted_order_plan", "plan_id"),
        sa.Index("idx_plan_impacted_order_reason", "reason_type"),
        schema="aps_result",
    )

    op.create_table(
        "plan_utilization",
        sa.Column("utilization_id", sa.String(50), primary_key=True),
        sa.Column("scenario_id", sa.String(50), sa.ForeignKey("aps_result.plan_scenario.scenario_id"), nullable=False),
        sa.Column("workcenter_id", sa.Integer(), nullable=False),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("utilization_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("available_capacity", sa.Numeric(10, 2), nullable=False),
        sa.Column("used_capacity", sa.Numeric(10, 2), nullable=False),
        sa.UniqueConstraint("scenario_id", "workcenter_id", "plan_date", name="idx_plan_utilization_scenario_workcenter_date"),
        sa.Index("idx_plan_utilization_scenario", "scenario_id"),
        sa.Index("idx_plan_utilization_workcenter", "workcenter_id"),
        sa.Index("idx_plan_utilization_date", "plan_date"),
        schema="aps_result",
    )

    op.create_table(
        "workcenter_load",
        sa.Column("load_id", sa.String(50), primary_key=True),
        sa.Column("scenario_id", sa.String(50), sa.ForeignKey("aps_result.plan_scenario.scenario_id"), nullable=False),
        sa.Column("run_id", sa.String(50), nullable=True, index=True),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("workcenter_id", sa.Integer(), sa.ForeignKey("aps_input.aps_workcenter.id"), nullable=False),
        sa.Column("operation_id", sa.Integer(), sa.ForeignKey("aps_input.aps_routing_step.id"), nullable=True, index=True),
        sa.Column("proc_name", sa.String(200), nullable=True),
        sa.Column("used_minutes", sa.Numeric(12, 2), nullable=False),
        sa.Column("capacity_minutes", sa.Numeric(12, 2), nullable=False),
        sa.Column("load_percent", sa.Numeric(8, 2), nullable=False),
        sa.Column("overloaded", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Index("idx_workcenter_load_scenario_date", "scenario_id", "work_date"),
        sa.Index("idx_workcenter_load_workcenter", "workcenter_id"),
        sa.Index("idx_workcenter_load_operation", "operation_id"),
        schema="aps_result",
    )

    op.create_foreign_key(
        "llm_response_cache_scenario_id_fkey",
        "llm_response_cache", "plan_scenario",
        ["scenario_id"], ["scenario_id"],
        source_schema="aps_result", referent_schema="aps_result",
        ondelete="CASCADE",
    )

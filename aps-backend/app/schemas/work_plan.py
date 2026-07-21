"""Schemas for the Work Plan List (작업계획 리스트) endpoint."""

from datetime import date

from pydantic import Field

from app.schemas.master import CamelModel


class WorkPlanDailyRow(CamelModel):
    """One daily-plan entry inside `WorkPlanRow.daily_plans`.

    Sourced from `aps_result.aps_daily_plan` (backward-fill breakdown per day).
    `minutes = planned_qty × (item_routing_spec.work_time / 60)` for the row's routing
    step (work_time is stored as seconds); null when the routing lookup misses.
    """

    date: date = Field(..., description="aps_daily_plan.work_date")
    qty: float = Field(..., description="aps_daily_plan.planned_qty for the day")
    minutes: float | None = Field(
        None, description="planned_qty × work_time_seconds / 60 (minutes; null if work_time missing)"
    )


class WorkPlanRow(CamelModel):
    """One row of the Work Plan List.

    Driven by ``aps_input.work_order`` (see docs/workplan.md): a row is either a
    confirmed work order (``source_type='WO'``: work_order_no set, status
    CONFIRMED, sync_status SUCCESS, temp_id NULL) or a temporary plan
    (``source_type='MPS'``: work_order_no NULL, status PLANNED). Missing source
    data is returned as null (no fallback).

    Serialised as camelCase to match the FE `WorkPlan` contract
    (aps-frontend/src/types/planning.ts).
    """

    id: str = Field(..., description="Work order id, stringified — FE reference for adjust/action")
    source_type: str = Field(..., description="'WO' (confirmed work order) or 'MPS' (temporary plan)")
    work_order_no: str | None = Field(None, description="작업지시번호 — WO rows only (work_order.work_order_no)")
    tmp_plan_no: str | None = Field(None, description="(임시)작업계획번호 — MPS rows only (aps_mps_plan.plan_no)")
    order_no: str | None = Field(None, description="오더 — PO number (aps_mps_plan.po_no)")
    item_no: str | None = Field(None, description="품목 코드")
    item_name: str | None = Field(None, description="품목 명 (aps_item.item_name)")
    workcenter_no: str | None = Field(None, description="워크센터 코드")
    workcenter_name: str | None = Field(None, description="워크센터 명")
    proc_name: str | None = Field(None, description="공정 — process name (aps_item_routing_spec.proc_name)")
    planned_qty: float | None = Field(None, description="계획수량")
    plan_start: date | None = Field(None, description="계획시작")
    plan_end: date | None = Field(None, description="계획완료")
    delivery_date: date | None = Field(None, description="납기일자 (aps_mps_plan.delivery_date)")
    risk_types: list[str] = Field(
        default_factory=list,
        description="리스크유형 — subset of {'overload','material_short'} from aps_daily_plan.status (empty → ['normal'])",
    )
    shortage_qty: float = Field(
        0.0,
        description="Total material shortage qty aggregated over the plan's aps_daily_plan days (0 = no shortage)",
    )
    daily_plans: list[WorkPlanDailyRow] = Field(
        default_factory=list,
        description="Backward-fill daily breakdown from aps_daily_plan for this plan (sorted by date)",
    )

"""Schemas for the Work Plan List (작업계획 리스트) endpoint."""

from datetime import date

from pydantic import BaseModel, Field


class WorkPlanRow(BaseModel):
    """One row of the Work Plan List.

    Driven by ``aps_input.work_order`` (see docs/workplan.md): a row is either a
    confirmed work order (``source_type='WO'``: work_order_no set, status
    CONFIRMED, sync_status SUCCESS, temp_id NULL) or a temporary plan
    (``source_type='MPS'``: work_order_no NULL, status PLANNED). Missing source
    data is returned as null (no fallback).
    """

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

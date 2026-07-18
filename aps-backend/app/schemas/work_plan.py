"""Schemas for the Work Plan List (작업계획 리스트) endpoint."""

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class WorkPlanRow(BaseModel):
    """One row of the Work Plan List.

    A row is either an incomplete work order (``source_type='WO'``) or an
    uncreated MPS plan line shown as a temporary plan (``source_type='MPS'``).
    Columns follow spec P6 (see ``docs/specs/my_explain.md``).
    """

    source_type: str = Field(..., description="'WO' (incomplete work order) or 'MPS' (uncreated plan)")
    work_order_no: Optional[str] = Field(None, description="작업지시번호 — set for WO rows")
    tmp_plan_no: Optional[str] = Field(None, description="(임시)작업계획번호 — set for MPS rows")
    order_no: Optional[str] = Field(None, description="오더 — PO number (aps_mps_plan.po_no)")
    item_no: Optional[str] = Field(None, description="품목 코드")
    item_name: Optional[str] = Field(None, description="품목 명")
    workcenter_no: Optional[str] = Field(None, description="워크센터 — representative operation's WC")
    workcenter_name: Optional[str] = None
    proc_name: Optional[str] = Field(None, description="공정 — representative operation (lowest proc_sno)")
    planned_qty: Optional[float] = Field(None, description="계획수량 (aps_mps_plan.plan_qty)")
    plan_start: Optional[date] = Field(None, description="계획시작 — Backward from end date, else MPS plan_start_date")
    plan_end: Optional[date] = Field(None, description="계획완료 — 종료일자(plan_end_date) / 작업종료일자(prod_end_date)")
    delivery_date: Optional[date] = Field(None, description="납기일자 (aps_mps_plan.delivery_date)")
    risk_types: List[str] = Field(
        default_factory=list,
        description="리스크유형 — currently 'overload' / 'normal'; '자재부족' added later when stock exists",
    )

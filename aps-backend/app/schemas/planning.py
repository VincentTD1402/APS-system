"""Planning schemas for the FE MPS/Work-order views. camelCase serialization
matches the FE contract (orderNo, planQty, workStartDate, ...)."""
from __future__ import annotations

from datetime import date

from pydantic import Field

from app.schemas.master import CamelModel


class MpsOut(CamelModel):
    id: int
    order_no: str | None = Field(None, description="aps_mps_plan.plan_no")
    item_code: str | None = Field(None, description="Item's item_no")
    plan_qty: float | None = Field(None, description="aps_mps_plan.plan_qty")
    end_date: date | None = Field(None, description="delivery_date (customer due date)")
    work_start_date: date | None = Field(None, description="plan_start_date")
    work_end_date: date | None = Field(None, description="plan_end_date")
    status: str = Field("DRAFT", description="Mapped from status_cd: DRAFT | CONFIRMED | CANCELLED")


class WorkOrderOut(CamelModel):
    id: int
    wo_no: str | None = Field(None, description="work_order.work_order_no")
    mps_id: int | None = Field(None, description="work_order.mps_plan_id")
    item_code: str | None = Field(None, description="Item's item_no")
    wc_code: str | None = Field(None, description="Workcenter's workcenter_no")
    plan_qty: float | None = Field(None, description="work_order.qty")
    plan_start_date: date | None = Field(None, description="min(daily_plan.work_date) of the MPS line")
    plan_end_date: date | None = Field(None, description="max(daily_plan.work_date) of the MPS line")
    status: str = Field("PLANNED", description="work_order.status: PLANNED | SENT | CONFIRMED | FAILED")

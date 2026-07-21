"""Pydantic schemas for POST /aps/run and POST /aps/adjust.

Unlike every other schema file in this package (snake_case, matching the rest
of the backend), these return camelCase JSON — matching the FE TypeScript
contract in docs/specs/fe-be-gap-matrix-260721-1128.csv exactly, by decision
(see plans/... aps-api-8-12 plan). Every field still has a snake_case Python
name; `alias_generator=to_camel` + `populate_by_name=True` handle the mapping
both ways.
"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class DailyPlanEntryOut(CamelModel):
    date: date
    qty: float
    minutes: float


class ApsRunInfoOut(CamelModel):
    id: str
    started_at: datetime
    finished_at: datetime


class WorkPlanOut(CamelModel):
    id: str
    run_id: str
    source_type: str
    work_order_no: str | None = None
    tmp_plan_no: str | None = None
    order_no: str | None = None
    item_code: str
    item_name_ko: str
    wc_code: str
    process_name_ko: str
    plan_qty: float
    plan_start_date: date
    plan_end_date: date
    delivery_date: date | None = None
    risk_type: str
    shortage_qty: float
    adjusted: bool
    original_start: date | None = None
    original_end: date | None = None
    daily_plans: list[DailyPlanEntryOut]


class LoadCellOut(CamelModel):
    wc_code: str
    cell_date: date
    minutes_loaded: float
    minutes_capacity: float
    status: str


class KpiSnapshotOut(CamelModel):
    on_time_rate_pct: float
    material_shortage_count: int
    overload_wc_pct: float
    planning_risk_count: int


class ApsRunResult(CamelModel):
    run: ApsRunInfoOut
    work_plans: list[WorkPlanOut]
    load_cells: list[LoadCellOut]
    kpi: KpiSnapshotOut


class AdjustmentIn(CamelModel):
    plan_id: str
    new_start: date
    new_end: date


class ApsAdjustRequest(CamelModel):
    run_id: str | None = None
    adjustments: list[AdjustmentIn]

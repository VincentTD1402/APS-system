"""Workcenter/day rollup of aps_result.aps_daily_plan.

Shared by KPI3 (workcenter load), the daily-plan rebuild endpoint, and the
workcenter-status endpoint used by FE for color mapping.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date as date_cls
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyPlan, ItemRoutingSpec, WorkCenter
from app.schemas.kpi_summary import WorkcenterDailyStatus


def _required_minutes_by_workcenter_day(rows) -> dict:
    """Sum planned_qty × work_time (minutes) per (workcenter_id, work_date).

    `rows` is an iterable of tuples whose first 3 elements are (DailyPlan, WorkCenter, ItemRoutingSpec).
    """
    out: dict = defaultdict(float)
    for dp, _wc, ir, *_rest in rows:
        if ir.work_time:
            out[(dp.workcenter_id, dp.work_date)] += float(dp.planned_qty) * (float(ir.work_time) / 60.0)
    return out


def _workcenter_capacity_index(db: Session):
    from app.services.scheduling.daily_plan_builder import build_workcenter_capacity_index
    return build_workcenter_capacity_index(db)


def workcenter_daily_status_rollup(
    db: Session,
    workcenter_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[WorkcenterDailyStatus]:
    """Workcenter-level rollup of aps_daily_plan for one (workcenter, work_date).

    `status` is read from the persisted `DailyPlan.status` column (single source
    of truth, written by `daily_plan_builder.rebuild_daily_plan`). Defensive
    rollup rule: a slot rolls up to "overload" if ANY row in the group is
    "overload" — do not assume the builder always sets it uniformly per slot.

    Numeric fields (`used_minutes`, `capacity_minutes`, `load_percent`,
    `daily_out_qty`, `planned_qty_total`) are NOT persisted and stay computed
    live here, same as before.
    """
    stmt = (
        select(DailyPlan, WorkCenter, ItemRoutingSpec)
        .join(WorkCenter, DailyPlan.workcenter_id == WorkCenter.id)
        .join(ItemRoutingSpec, DailyPlan.item_routing_id == ItemRoutingSpec.id)
    )
    if workcenter_id is not None:
        stmt = stmt.where(DailyPlan.workcenter_id == workcenter_id)
    if start_date:
        stmt = stmt.where(DailyPlan.work_date >= date_cls.fromisoformat(start_date))
    if end_date:
        stmt = stmt.where(DailyPlan.work_date <= date_cls.fromisoformat(end_date))

    results = db.execute(stmt).all()

    required_minutes = _required_minutes_by_workcenter_day(
        [(dp, wc, ir, None, None) for dp, wc, ir in results]
    )
    qty_by_slot: dict = defaultdict(float)
    persisted_overload_by_slot: dict = defaultdict(bool)  # defensive OR rollup
    short_qty_by_slot: dict = defaultdict(float)          # Σ material_shortage_qty per slot
    for dp, _wc, _ir in results:
        slot = (dp.workcenter_id, dp.work_date)
        qty_by_slot[slot] += float(dp.planned_qty)
        if dp.status in ("overload", "urgent"):  # urgent = overload + material shortage
            persisted_overload_by_slot[slot] = True
        short_qty_by_slot[slot] += float(dp.material_shortage_qty or 0)
    capacity_index = _workcenter_capacity_index(db)
    meta_by_wc = {wc.id: wc for _dp, wc, _ir in results}

    out: List[WorkcenterDailyStatus] = []
    # Iterate qty_by_slot keys (not required_minutes) so a slot with rows but
    # zero required minutes (work_time is None) is still surfaced.
    for (wc_id, work_date) in sorted(
        qty_by_slot.keys(),
        key=lambda k: (meta_by_wc[k[0]].workcenter_no or "", k[1]),
    ):
        wc = meta_by_wc[wc_id]
        used_minutes = required_minutes.get((wc_id, work_date), 0.0)
        capacity = capacity_index.minutes_on(wc_id, work_date)
        qty_total = qty_by_slot[(wc_id, work_date)]
        load_percent = (
            round((used_minutes / capacity) * 100.0, 2) if capacity > 0
            else (999.99 if used_minutes > 0 else 0.0)
        )
        if capacity > 0 and used_minutes > 0:
            daily_out_qty = round(qty_total * capacity / used_minutes, 2)
        else:
            daily_out_qty = 0.0
        over = persisted_overload_by_slot[(wc_id, work_date)]
        short_qty = short_qty_by_slot[(wc_id, work_date)]
        short = short_qty > 0
        # 부하내역 4-state: normal(green) | overload(orange) | material-shortage(blue) | urgent(red=both)
        if over and short:
            status, statuses = "urgent", ["overload", "material-shortage"]
        elif over:
            status, statuses = "overload", ["overload"]
        elif short:
            status, statuses = "material-shortage", ["material-shortage"]
        else:
            status, statuses = "normal", ["normal"]
        out.append(WorkcenterDailyStatus(
            work_date=work_date,
            workcenter_id=wc_id,
            workcenter_no=wc.workcenter_no,
            workcenter_name=wc.workcenter_name,
            planned_qty_total=round(qty_total, 2),
            daily_out_qty=daily_out_qty,
            used_minutes=round(used_minutes, 2),
            capacity_minutes=round(capacity, 2),
            load_percent=load_percent,
            material_shortage_qty=round(short_qty, 4),
            status=status,
            statuses=statuses,
        ))
    return out

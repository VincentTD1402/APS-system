"""Assembly service for POST /aps/run and POST /aps/adjust.

Reshapes the existing daily-plan compute engine (daily_plan_builder,
shortage_builder) into the WorkPlan/LoadCell/KPI shape the FE needs (see
docs/specs/fe-be-gap-matrix-260721-1128.csv rows 8-9), instead of
re-implementing scheduling from scratch.

There is no persisted "work plan" table — a WorkPlan is one
(mps_plan_id, item_routing_id) group of aps_daily_plan rows (both columns are
NOT NULL, so the key is always well-defined). Its API id is the synthetic
string `encode_plan_id(mps_plan_id, item_routing_id)`.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_logger
from app.models import DailyPlan, Item, ItemRoutingSpec, MpsPlan, WorkCenter, WorkOrder
from app.services.material_shortage.shortage_builder import (
    apply_daily_material_shortage,
    rebuild_material_shortage,
)
from app.services.scheduling.daily_plan_builder import (
    _backward_fill_step,
    build_workcenter_capacity_index,
    rebuild_daily_plan,
)

logger = get_logger(__name__)

_PLAN_ID_SEP = ":"


class PlanIdError(ValueError):
    """Raised when a planId doesn't decode to a (mps_plan_id, item_routing_id) pair."""


def encode_plan_id(mps_plan_id: int, item_routing_id: int) -> str:
    return f"{mps_plan_id}{_PLAN_ID_SEP}{item_routing_id}"


def decode_plan_id(plan_id: str) -> tuple[int, int]:
    parts = plan_id.split(_PLAN_ID_SEP)
    if len(parts) != 2:
        raise PlanIdError(f"malformed planId: {plan_id!r}")
    try:
        return int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise PlanIdError(f"malformed planId: {plan_id!r}") from exc


@dataclass
class DailyPlanEntry:
    date: date
    qty: float
    minutes: float


@dataclass
class WorkPlan:
    id: str
    run_id: str
    source_type: str
    work_order_no: str | None
    tmp_plan_no: str | None
    order_no: str | None
    item_code: str
    item_name_ko: str
    wc_code: str
    process_name_ko: str
    plan_qty: float
    plan_start_date: date
    plan_end_date: date
    delivery_date: date | None
    risk_type: str
    shortage_qty: float
    adjusted: bool
    original_start: date | None
    original_end: date | None
    daily_plans: list[DailyPlanEntry] = field(default_factory=list)


@dataclass
class LoadCell:
    wc_code: str
    cell_date: date
    minutes_loaded: float
    minutes_capacity: float
    status: str


@dataclass
class KpiSnapshot:
    on_time_rate_pct: float
    material_shortage_count: int
    overload_wc_pct: float
    planning_risk_count: int


@dataclass
class ApsRunInfo:
    id: str
    started_at: datetime
    finished_at: datetime


@dataclass
class AssembledResult:
    run: ApsRunInfo
    work_plans: list[WorkPlan]
    load_cells: list[LoadCell]
    kpi: KpiSnapshot


def run_full_pipeline(session: Session) -> AssembledResult:
    """POST /aps/run: full G-System-driven recompute, then assemble."""
    started_at = datetime.now(timezone.utc)
    rebuild_daily_plan(session)
    apply_daily_material_shortage(session)
    rebuild_material_shortage(session)
    session.flush()
    return assemble(session, started_at=started_at)


def adjust_work_plans(session: Session, adjustments: list[tuple[str, date, date]]) -> AssembledResult:
    """POST /aps/adjust: re-backward-fill the given (planId, newStart, newEnd) groups.

    Does NOT call rebuild_daily_plan/rebuild_material_shortage — operates on
    top of the current DB state (the last /aps/run or /aps/adjust), only
    touching the groups named in `adjustments`.
    """
    started_at = datetime.now(timezone.utc)
    capacity_index = build_workcenter_capacity_index(session)
    routing_by_id = {r.id: r for r in session.execute(select(ItemRoutingSpec)).scalars().all()}

    for plan_id, new_start, new_end in adjustments:
        mps_plan_id, item_routing_id = decode_plan_id(plan_id)
        routing = routing_by_id.get(item_routing_id)
        if routing is None or routing.workcenter_id is None or not routing.work_time:
            logger.warning("adjust_work_plans: planId=%s has no usable routing — skipped", plan_id)
            continue
        work_time_minutes = float(routing.work_time) / 60.0
        wc_id = routing.workcenter_id

        rows = session.execute(
            select(DailyPlan).where(
                DailyPlan.mps_plan_id == mps_plan_id, DailyPlan.item_routing_id == item_routing_id
            )
        ).scalars().all()
        if not rows:
            logger.warning("adjust_work_plans: planId=%s has no daily_plan rows — skipped", plan_id)
            continue

        already_adjusted = any(r.adjusted for r in rows)
        total_qty = sum(float(r.planned_qty) for r in rows)
        if already_adjusted:
            # Snapshot already exists on the surviving rows — carry the
            # earliest one forward (all rows of one group share one original).
            orig_date = next((r.original_work_date for r in rows if r.original_work_date), None)
            orig_qty = next((r.original_planned_qty for r in rows if r.original_planned_qty is not None), None)
        else:
            orig_dates = sorted(r.work_date for r in rows)
            orig_date = orig_dates[0] if orig_dates else None
            orig_qty = total_qty

        for r in rows:
            session.delete(r)
        session.flush()

        def _daily_qty_on(day: date, _wc_id: int = wc_id, _wtm: float = work_time_minutes) -> float:
            return capacity_index.minutes_on(_wc_id, day) / _wtm

        allocations, _earliest = _backward_fill_step(
            qty=total_qty, window_end=new_end, daily_capacity_qty_on=_daily_qty_on, today=new_start,
        )
        for work_date, qty in allocations.items():
            if qty <= 0:
                continue
            session.add(DailyPlan(
                mps_plan_id=mps_plan_id,
                item_routing_id=item_routing_id,
                workcenter_id=wc_id,
                work_date=work_date,
                planned_qty=round(qty, 2),
                status="normal",
                adjusted=True,
                original_work_date=orig_date,
                original_planned_qty=orig_qty,
            ))
        session.flush()

    apply_daily_material_shortage(session)
    session.flush()
    return assemble(session, started_at=started_at)


def assemble(session: Session, started_at: datetime | None = None) -> AssembledResult:
    """Pure read + group — no writes. Shared tail of /aps/run and /aps/adjust."""
    started_at = started_at or datetime.now(timezone.utc)
    run_id = str(uuid.uuid4())

    rows = session.execute(
        select(DailyPlan, ItemRoutingSpec, WorkCenter, MpsPlan)
        .join(ItemRoutingSpec, DailyPlan.item_routing_id == ItemRoutingSpec.id)
        .join(WorkCenter, DailyPlan.workcenter_id == WorkCenter.id)
        .join(MpsPlan, DailyPlan.mps_plan_id == MpsPlan.id)
    ).all()

    item_ids = {mps.item_id for _dp, _ir, _wc, mps in rows if mps.item_id is not None}
    items_by_id: dict[int, Item] = {
        i.id: i for i in session.execute(select(Item).where(Item.id.in_(item_ids))).scalars().all()
    } if item_ids else {}

    mps_ids = {mps.id for _dp, _ir, _wc, mps in rows}
    routing_ids = {ir.id for _dp, ir, _wc, _mps in rows}
    work_orders = session.execute(
        select(WorkOrder).where(
            WorkOrder.mps_plan_id.in_(mps_ids), WorkOrder.item_routing_id.in_(routing_ids)
        )
    ).scalars().all() if mps_ids and routing_ids else []
    wo_by_group: dict[tuple[int, int], WorkOrder] = {
        (wo.mps_plan_id, wo.item_routing_id): wo for wo in work_orders
        if wo.mps_plan_id is not None and wo.item_routing_id is not None
    }

    groups: dict[tuple[int, int], list[tuple[DailyPlan, ItemRoutingSpec, WorkCenter, MpsPlan]]] = defaultdict(list)
    for dp, ir, wc, mps in rows:
        groups[(dp.mps_plan_id, dp.item_routing_id)].append((dp, ir, wc, mps))

    work_plans: list[WorkPlan] = []
    cell_map: dict[tuple[str, date], dict[str, float | bool]] = defaultdict(
        lambda: {"minutes_loaded": 0.0, "capacity": 0.0, "has_material_short": False}
    )
    wc_capacity_index = build_workcenter_capacity_index(session)

    for (mps_plan_id, item_routing_id), group_rows in groups.items():
        _dp0, ir, wc, mps = group_rows[0]
        work_time_minutes = float(ir.work_time) / 60.0 if ir.work_time else 0.0
        item = items_by_id.get(mps.item_id) if mps.item_id is not None else None
        wo = wo_by_group.get((mps_plan_id, item_routing_id))

        daily_entries: list[DailyPlanEntry] = []
        shortage_qty = 0.0
        has_overload = False
        has_material_short = False
        any_adjusted = False
        work_dates: list[date] = []
        original_dates: list[date] = []

        for dp, _ir, _wc, _mps in group_rows:
            minutes = float(dp.planned_qty) * work_time_minutes
            daily_entries.append(DailyPlanEntry(date=dp.work_date, qty=float(dp.planned_qty), minutes=minutes))
            shortage_qty += float(dp.material_shortage_qty or 0)
            if dp.status in ("overload", "urgent"):
                has_overload = True
            if float(dp.material_shortage_qty or 0) > 0:
                has_material_short = True
            if dp.adjusted:
                any_adjusted = True
            work_dates.append(dp.work_date)
            original_dates.append(dp.original_work_date or dp.work_date)

            cell_key = (wc.workcenter_no, dp.work_date)
            cell = cell_map[cell_key]
            cell["minutes_loaded"] += minutes
            cell["capacity"] = wc_capacity_index.minutes_on(wc.id, dp.work_date)
            if float(dp.material_shortage_qty or 0) > 0:
                cell["has_material_short"] = True

        if has_material_short and has_overload:
            risk_type = "MATERIAL_AND_OVERLOAD"
        elif has_material_short:
            risk_type = "MATERIAL_SHORT"
        elif has_overload:
            risk_type = "OVERLOAD"
        else:
            risk_type = "NORMAL"

        daily_entries.sort(key=lambda e: e.date)
        work_dates.sort()
        original_dates.sort()

        work_plans.append(WorkPlan(
            id=encode_plan_id(mps_plan_id, item_routing_id),
            run_id=run_id,
            source_type="FROM_WORK_ORDER" if wo is not None else "FROM_MPS",
            work_order_no=wo.work_order_no if wo is not None else None,
            tmp_plan_no=wo.temp_id if wo is not None else None,
            order_no=(wo.work_order_no if wo is not None else None) or mps.plan_no,
            item_code=item.item_no if item is not None else "",
            item_name_ko=(item.item_name if item is not None and item.item_name else (item.item_no if item is not None else "")),
            wc_code=wc.workcenter_no,
            process_name_ko=ir.proc_name or "",
            plan_qty=sum(e.qty for e in daily_entries),
            plan_start_date=work_dates[0],
            plan_end_date=work_dates[-1],
            delivery_date=mps.delivery_date,
            risk_type=risk_type,
            shortage_qty=round(shortage_qty, 4),
            adjusted=any_adjusted,
            original_start=original_dates[0] if any_adjusted else None,
            original_end=original_dates[-1] if any_adjusted else None,
            daily_plans=daily_entries,
        ))

    load_cells: list[LoadCell] = []
    overloaded_wc_codes: set[str] = set()
    for (wc_code, cell_date), val in cell_map.items():
        minutes_loaded = float(val["minutes_loaded"])
        capacity = float(val["capacity"])
        overload = capacity > 0 and minutes_loaded > capacity
        has_material_short = bool(val["has_material_short"])
        if overload and has_material_short:
            status = "OVERLOAD_AND_MATERIAL_SHORT"
        elif overload:
            status = "OVERLOAD"
        elif has_material_short:
            status = "MATERIAL_SHORT"
        else:
            status = "NORMAL"
        if overload:
            overloaded_wc_codes.add(wc_code)
        load_cells.append(LoadCell(
            wc_code=wc_code, cell_date=cell_date, minutes_loaded=round(minutes_loaded, 2),
            minutes_capacity=round(capacity, 2), status=status,
        ))

    total_plans = len(work_plans)
    on_time = sum(1 for p in work_plans if p.delivery_date is not None and p.plan_end_date <= p.delivery_date)
    material_count = sum(1 for p in work_plans if p.risk_type in ("MATERIAL_SHORT", "MATERIAL_AND_OVERLOAD"))
    risk_count = sum(1 for p in work_plans if p.risk_type != "NORMAL")
    total_wc = session.execute(select(WorkCenter.id)).scalars().all()
    total_wc_count = len(total_wc)

    kpi = KpiSnapshot(
        on_time_rate_pct=round((on_time / total_plans) * 100, 1) if total_plans else 100.0,
        material_shortage_count=material_count,
        overload_wc_pct=round((len(overloaded_wc_codes) / total_wc_count) * 100, 1) if total_wc_count else 0.0,
        planning_risk_count=risk_count,
    )

    finished_at = datetime.now(timezone.utc)
    return AssembledResult(
        run=ApsRunInfo(id=run_id, started_at=started_at, finished_at=finished_at),
        work_plans=work_plans,
        load_cells=load_cells,
        kpi=kpi,
    )

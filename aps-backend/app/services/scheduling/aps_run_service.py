"""Assembly service for POST /aps/run and POST /aps/adjust.

/aps/run is a pure READ — it does NOT recompute aps_daily_plan/
aps_material_shortage. That compute already exists as
POST /kpi-summary/daily-plan/rebuild (daily_plan_builder.rebuild_daily_plan +
shortage_builder.apply_daily_material_shortage/rebuild_material_shortage);
re-running it here would duplicate that work. Callers must rebuild first.

WorkPlan assembly is built on top of work_plan_list.build_work_plan_list,
which is already driven by aps_input.work_order (joined to aps_mps_plan) —
not re-derived from aps_daily_plan groups, so there's one source of truth
for "what is a work plan" shared with GET /work-plan/list. This module only
adds the run/loadCells/kpi envelope and the FE camelCase field names.

WorkPlan.id = str(work_order.id) — the real PK, not a synthetic key.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_logger
from app.models import DailyPlan, ItemRoutingSpec, WorkCenter, WorkOrder
from app.services.material_shortage.shortage_builder import apply_daily_material_shortage
from app.services.scheduling.daily_plan_builder import _backward_fill_step, build_workcenter_capacity_index
from app.services.scheduling.work_plan_list import build_work_plan_list

logger = get_logger(__name__)


class PlanIdError(ValueError):
    """Raised when a planId doesn't resolve to a work_order.id."""


def parse_plan_id(plan_id: str) -> int:
    try:
        return int(plan_id)
    except ValueError as exc:
        raise PlanIdError(f"malformed planId (expected work_order.id): {plan_id!r}") from exc


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
    tmp_plan_no: str
    order_no: str | None
    item_code: str
    item_name_ko: str
    wc_code: str
    process_name_ko: str
    plan_qty: float
    plan_start_date: date
    plan_end_date: date
    delivery_date: date
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


_SOURCE_TYPE_MAP = {"WO": "FROM_WORK_ORDER", "MPS": "FROM_MPS"}


def _build_load_cells(session: Session) -> tuple[list[LoadCell], set[str]]:
    """Group aps_daily_plan by (workcenter, day) — independent of work_order."""
    rows = session.execute(
        select(DailyPlan, ItemRoutingSpec, WorkCenter)
        .join(ItemRoutingSpec, DailyPlan.item_routing_id == ItemRoutingSpec.id)
        .join(WorkCenter, DailyPlan.workcenter_id == WorkCenter.id)
    ).all()
    capacity_index = build_workcenter_capacity_index(session)

    cell_map: dict[tuple[str, date], dict[str, float | bool]] = defaultdict(
        lambda: {"minutes_loaded": 0.0, "capacity": 0.0, "has_material_short": False}
    )
    for dp, ir, wc in rows:
        minutes = float(dp.planned_qty) * (float(ir.work_time) / 60.0) if ir.work_time else 0.0
        key = (wc.workcenter_no, dp.work_date)
        cell = cell_map[key]
        cell["minutes_loaded"] += minutes
        cell["capacity"] = capacity_index.minutes_on(wc.id, dp.work_date)
        if float(dp.material_shortage_qty or 0) > 0:
            cell["has_material_short"] = True

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
    return load_cells, overloaded_wc_codes


def _compute_kpi(
    session: Session, work_plans: list[WorkPlan], overloaded_wc_codes: set[str],
) -> KpiSnapshot:
    """KPI counts at MPS-line grain, not work_order-row grain.

    aps_input.work_order can carry several rows for the same mps_plan_id (one
    G-System MPS line can be split into multiple dispatched work orders — seen
    live, e.g. one line with 11 work_order rows). WorkPlan is one row per
    work_order (needed so each is independently actionable), so counting KPI
    directly over work_plans would count that one line up to 11 times. Group
    by mps_plan_id first — same unit KPI1/KPI4 use — so a line contributes
    once regardless of how many work orders back it.
    """
    wo_ids = [int(p.id) for p in work_plans]
    mps_plan_by_wo_id: dict[str, int | None] = {
        str(wo_id): mps_plan_id
        for wo_id, mps_plan_id in session.execute(
            select(WorkOrder.id, WorkOrder.mps_plan_id).where(WorkOrder.id.in_(wo_ids))
        ).all()
    } if wo_ids else {}

    groups: dict[int | str, list[WorkPlan]] = defaultdict(list)
    for p in work_plans:
        # Ad-hoc work orders (no mps_plan_id) have no line to dedupe against —
        # each stands alone.
        key = mps_plan_by_wo_id.get(p.id) or f"wo:{p.id}"
        groups[key].append(p)

    total_lines = len(groups)
    on_time_lines = 0
    material_lines = 0
    risk_lines = 0
    for members in groups.values():
        # All members of a line share the same risk_type/delivery_date (both
        # derive from the same aps_mps_plan/aps_daily_plan rows) — worst-case
        # plan_end across members decides on-time, since the line isn't done
        # until every one of its work orders is.
        worst_end = max(m.plan_end_date for m in members)
        delivery = members[0].delivery_date
        if worst_end <= delivery:
            on_time_lines += 1
        risk_type = members[0].risk_type
        if risk_type in ("MATERIAL_SHORT", "MATERIAL_AND_OVERLOAD"):
            material_lines += 1
        if risk_type != "NORMAL":
            risk_lines += 1

    total_wc_count = len(session.execute(select(WorkCenter.id)).scalars().all())
    return KpiSnapshot(
        on_time_rate_pct=round((on_time_lines / total_lines) * 100, 1) if total_lines else 100.0,
        material_shortage_count=material_lines,
        overload_wc_pct=round((len(overloaded_wc_codes) / total_wc_count) * 100, 1) if total_wc_count else 0.0,
        planning_risk_count=risk_lines,
    )


def assemble(session: Session) -> AssembledResult:
    """Pure read + assemble — no writes. Used by both /aps/run and /aps/adjust."""
    started_at = datetime.now(timezone.utc)
    run_id = str(uuid.uuid4())

    rows = build_work_plan_list(session)
    work_plans: list[WorkPlan] = []
    for row in rows:
        risk_short = "material_short" in row.risk_types
        risk_over = "overload" in row.risk_types
        if risk_short and risk_over:
            risk_type = "MATERIAL_AND_OVERLOAD"
        elif risk_short:
            risk_type = "MATERIAL_SHORT"
        elif risk_over:
            risk_type = "OVERLOAD"
        else:
            risk_type = "NORMAL"

        entries = [DailyPlanEntry(date=d.date, qty=d.qty, minutes=d.minutes) for d in row.daily_plans]
        plan_start = row.plan_start or (entries[0].date if entries else None)
        plan_end = row.plan_end or (entries[-1].date if entries else None)
        if plan_start is None or plan_end is None:
            logger.warning("assemble: work_order id=%s has no plan_start/plan_end — skipped", row.id)
            continue

        work_plans.append(WorkPlan(
            id=row.id,
            run_id=run_id,
            source_type=_SOURCE_TYPE_MAP.get(row.source_type, "FROM_MPS"),
            work_order_no=row.work_order_no,
            # FE's tmpPlanNo is non-null; work_plan_list only sets it for MPS rows
            # (aps_mps_plan.plan_no) — fall back to this row's own id for WO rows.
            tmp_plan_no=row.tmp_plan_no or row.id,
            order_no=row.order_no,
            item_code=row.item_no or "",
            item_name_ko=row.item_name or row.item_no or "",
            wc_code=row.workcenter_no or "",
            process_name_ko=row.proc_name or "",
            plan_qty=row.planned_qty or 0.0,
            plan_start_date=plan_start,
            plan_end_date=plan_end,
            # FE's deliveryDate is non-null — fall back to plan_end when the MPS
            # line genuinely has no delivery_date.
            delivery_date=row.delivery_date or plan_end,
            risk_type=risk_type,
            shortage_qty=row.shortage_qty,
            adjusted=row.adjusted,
            original_start=row.original_start,
            original_end=row.original_end,
            daily_plans=entries,
        ))

    load_cells, overloaded_wc_codes = _build_load_cells(session)
    kpi = _compute_kpi(session, work_plans, overloaded_wc_codes)

    finished_at = datetime.now(timezone.utc)
    return AssembledResult(
        run=ApsRunInfo(id=run_id, started_at=started_at, finished_at=finished_at),
        work_plans=work_plans,
        load_cells=load_cells,
        kpi=kpi,
    )


def _resolve_item_routing_id(session: Session, wo: WorkOrder) -> int:
    """A WorkOrder rarely carries item_routing_id (only PLANNED stubs we create do —
    real G-System-synced rows never set it). Fall back to the MPS line's routing
    step via aps_daily_plan. Multi-step MPS lines (>1 distinct item_routing_id)
    aren't supported by /aps/adjust yet — raise rather than guess wrong.
    """
    if wo.item_routing_id is not None:
        return wo.item_routing_id
    routing_ids = set(session.execute(
        select(DailyPlan.item_routing_id).where(DailyPlan.mps_plan_id == wo.mps_plan_id).distinct()
    ).scalars().all())
    if len(routing_ids) == 1:
        return routing_ids.pop()
    if not routing_ids:
        raise PlanIdError(f"work_order id={wo.id}: no aps_daily_plan rows to adjust (rebuild first)")
    raise PlanIdError(
        f"work_order id={wo.id}: MPS line has {len(routing_ids)} routing steps — "
        "/aps/adjust doesn't support multi-step MPS lines yet"
    )


def adjust_work_plans(session: Session, adjustments: list[tuple[str, date, date]]) -> AssembledResult:
    """POST /aps/adjust: re-backward-fill the given (planId, newStart, newEnd) plans.

    planId = work_order.id. Does NOT call rebuild_daily_plan/rebuild_material_shortage —
    operates on top of the current DB state, only touching the named plans.
    """
    capacity_index = build_workcenter_capacity_index(session)

    for plan_id, new_start, new_end in adjustments:
        wo_id = parse_plan_id(plan_id)
        wo = session.get(WorkOrder, wo_id)
        if wo is None or wo.mps_plan_id is None:
            logger.warning("adjust_work_plans: planId=%s not found — skipped", plan_id)
            continue
        item_routing_id = _resolve_item_routing_id(session, wo)
        routing = session.get(ItemRoutingSpec, item_routing_id)
        if routing is None or routing.workcenter_id is None or not routing.work_time:
            logger.warning("adjust_work_plans: planId=%s has no usable routing — skipped", plan_id)
            continue
        work_time_minutes = float(routing.work_time) / 60.0
        wc_id = routing.workcenter_id

        rows = session.execute(
            select(DailyPlan).where(
                DailyPlan.mps_plan_id == wo.mps_plan_id, DailyPlan.item_routing_id == item_routing_id
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
                mps_plan_id=wo.mps_plan_id,
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
    return assemble(session)

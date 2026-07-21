"""Assembly service for POST /aps/run and POST /aps/adjust.

/aps/run recomputes aps_daily_plan/aps_material_shortage itself (same
sequence as POST /kpi-summary/daily-plan/rebuild: rebuild_daily_plan →
apply_daily_material_shortage → rebuild_material_shortage) before assembling —
FE/KPI2/KPI3/KPI4 need those tables current on every run, and rebuild_daily_plan
already preserves hand-adjusted rows, so re-running it here is safe.
/aps/adjust does NOT re-run this — it only re-backward-fills the named plans
on top of current DB state (see adjust_work_plans).

WorkPlan assembly is built on top of work_plan_list.build_work_plan_list,
which is already driven by aps_input.work_order (joined to aps_mps_plan) —
not re-derived from aps_daily_plan groups, so there's one source of truth
for "what is a work plan" shared with GET /work-plan/list. This module only
adds the run/loadCells/kpi envelope and the FE camelCase field names.

WorkPlan.id = str(work_order.id) — the real PK, not a synthetic key.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_logger
from app.models import DailyPlan, ItemRoutingSpec, MaterialShortage, MpsPlan, WorkCenter, WorkOrder
from app.services.kpi_summary.daily_plan_rollup import workcenter_daily_status_rollup
from app.services.material_shortage.shortage_builder import (
    apply_daily_material_shortage,
    rebuild_material_shortage,
)
from app.services.scheduling.daily_plan_builder import (
    _backward_fill_step,
    build_workcenter_capacity_index,
    rebuild_daily_plan,
)
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
    tmp_plan_no: str | None
    order_no: str | None
    item_code: str
    item_name_ko: str
    wc_code: str
    wc_name: str | None
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
    wc_name: str | None
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


_ROLLUP_STATUS_MAP = {
    "normal": "NORMAL",
    "overload": "OVERLOAD",
    "material-shortage": "MATERIAL_SHORT",
    "urgent": "OVERLOAD_AND_MATERIAL_SHORT",
}


def _build_load_cells(session: Session) -> tuple[list[LoadCell], set[str]]:
    """Reuses workcenter_daily_status_rollup — the same persisted aps_daily_plan.status
    GET /kpi-summary/load (KPI3) reads — instead of recomputing overload live from
    planned_qty/work_time, so the Load Grid and overloadWcPct always agree with KPI3.
    """
    overloaded_wc_codes: set[str] = set()
    load_cells = []
    for r in workcenter_daily_status_rollup(session):
        load_cells.append(LoadCell(
            wc_code=r.workcenter_no, wc_name=r.workcenter_name, cell_date=r.work_date,
            minutes_loaded=r.used_minutes, minutes_capacity=r.capacity_minutes,
            status=_ROLLUP_STATUS_MAP.get(r.status, "NORMAL"),
        ))
        if r.status in ("overload", "urgent"):
            overloaded_wc_codes.add(r.workcenter_no)
    return load_cells, overloaded_wc_codes


def _compute_kpi(session: Session, work_plans: list[WorkPlan], overloaded_wc_codes: set[str]) -> KpiSnapshot:
    """Mirrors KPI1/KPI2/KPI3/KPI4's own formulas exactly, at MPS-line grain.

    aps_input.work_order can carry several rows for the same mps_plan_id (one
    G-System MPS line can be split into multiple dispatched work orders — seen
    live, e.g. one line with 11 work_order rows), so on-time is deduped by
    mps_plan_id first — each work_order resolves to its aps_mps_plan row and
    is judged the same way KPI1 judges it (plan_end_date > delivery_date),
    not by the work_order's own backward-filled/response dates.
    """
    wo_ids = [int(p.id) for p in work_plans]
    mps_plan_id_by_wo_id: dict[str, int | None] = {
        str(wo_id): mps_plan_id
        for wo_id, mps_plan_id in session.execute(
            select(WorkOrder.id, WorkOrder.mps_plan_id).where(WorkOrder.id.in_(wo_ids))
        ).all()
    } if wo_ids else {}
    mps_plan_ids = {v for v in mps_plan_id_by_wo_id.values() if v is not None}
    mps_by_id = {
        m.id: m for m in session.execute(select(MpsPlan).where(MpsPlan.id.in_(mps_plan_ids))).scalars().all()
    } if mps_plan_ids else {}

    lines_seen: set[int | str] = set()
    counted = 0
    delayed = 0
    for p in work_plans:
        key = mps_plan_id_by_wo_id.get(p.id) or f"wo:{p.id}"
        if key in lines_seen:
            continue
        lines_seen.add(key)
        mps = mps_by_id.get(key) if isinstance(key, int) else None
        # Same WHERE clause as KPI1: skip lines with no plan_end_date/delivery_date.
        if mps is None or mps.plan_end_date is None or mps.delivery_date is None:
            continue
        counted += 1
        if mps.plan_end_date > mps.delivery_date:
            delayed += 1
    on_time_rate = round(((counted - delayed) / counted) * 100, 1) if counted else 100.0

    # Same query as KPI2 (calculate_kpi2_shortage) — count, not scoped to work_plans.
    material_shortage_count = len(
        session.execute(select(MaterialShortage.id).where(MaterialShortage.shortage_qty > 0)).scalars().all()
    )

    total_wc_count = len(session.execute(select(WorkCenter.id)).scalars().all())
    overloaded_wc_count = len(overloaded_wc_codes)
    overload_wc_pct = round((overloaded_wc_count / total_wc_count) * 100, 1) if total_wc_count else 0.0

    # Same formula as KPI4 (r1 delayed + r2 shortage items + r3 overloaded wc).
    planning_risk_count = delayed + material_shortage_count + overloaded_wc_count

    return KpiSnapshot(
        on_time_rate_pct=on_time_rate,
        material_shortage_count=material_shortage_count,
        overload_wc_pct=overload_wc_pct,
        planning_risk_count=planning_risk_count,
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
            # work_plan_list only sets this for MPS rows (aps_mps_plan.plan_no) —
            # null for WO rows (they have no temp plan; workOrderNo already covers
            # their real identifier). Do not fabricate a value from row.id.
            tmp_plan_no=row.tmp_plan_no,
            order_no=row.order_no,
            item_code=row.item_no or "",
            item_name_ko=row.item_name or row.item_no or "",
            wc_code=row.workcenter_no or "",
            wc_name=row.workcenter_name,
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


def run_full_pipeline(session: Session) -> AssembledResult:
    """POST /aps/run: rebuild aps_daily_plan/aps_material_shortage, then assemble.

    Same rebuild sequence as POST /kpi-summary/daily-plan/rebuild — kept in
    sync here so /aps/run always reflects a fresh schedule without requiring
    the FE to call the rebuild endpoint separately first. Caller owns commit.
    """
    rebuild_daily_plan(session)
    apply_daily_material_shortage(session)
    rebuild_material_shortage(session)
    session.flush()
    return assemble(session)


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

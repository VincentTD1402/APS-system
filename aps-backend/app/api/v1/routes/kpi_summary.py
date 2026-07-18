from datetime import date as date_cls

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import and_, case, distinct, func, select
from sqlalchemy.orm import Session
from collections import defaultdict
from typing import List, Optional

from app.db.database import get_db
from app.models import (
    DailyPlan,
    Item,
    ItemRoutingSpec,
    MpsPlan,
    PlanImpactedOrder,
    PlanOperation,
    PlanOrder,
    WorkCenter,
    WorkcenterLoad,
)
from app.schemas.kpi_summary import (
    DailyPlanRebuildResponse,
    DailyPlanRow,
    DelayedOrderDetail,
    KPI1DeliveryResponse,
    KPI2ShortageResponse,
    KPI3LoadResponse,
    MaterialShortageSummary,
    PlanImpactedOrderRow,
    WorkcenterDailyStatus,
    WorkcenterLoadByWorkcenter,
    WorkcenterLoadLineItem,
    WorkcenterLoadEntry
)
from app.services.kpi_summary import KPISummaryService


router = APIRouter()

def _baseline_from_sim_scenario_id(scenario_id: str) -> str | None:
    if "_sim_" not in scenario_id:
        return None
    return scenario_id.split("_sim_", 1)[0]


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


def _workcenter_daily_status_rollup(
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


# ============================================================================
# KPI 1 – Delivery Compliance Rate
# ============================================================================

@router.get(
    "/{scenario_id}/delivery",
    response_model=KPI1DeliveryResponse,
    summary="KPI 1 – Delivery Compliance Rate",
    description="Calculate delivery compliance rate for a scenario. R1 risk triggered if rate < 100%.",
)
def get_delivery_kpi(
    scenario_id: str = Path(..., max_length=100),
    db: Session = Depends(get_db),
) -> KPI1DeliveryResponse:
    """Get KPI 1 – Delivery Compliance Rate.

    Compares planned_ship_date against delivery_date for all orders in the scenario.
    Returns compliance rate and details of delayed orders.
    """
    service = KPISummaryService(db, scenario_id)
    return service.calculate_kpi1_delivery()


# ============================================================================
# KPI 2 – Material Shortage
# ============================================================================

@router.get(
    "/{scenario_id}/shortage",
    response_model=KPI2ShortageResponse,
    summary="KPI 2 – Material Shortage",
    description="Get material shortage information for a scenario. R2 risk triggered if any shortage > 0.",
)
def get_shortage_kpi(
    scenario_id: str = Path(..., max_length=100),
    db: Session = Depends(get_db),
) -> KPI2ShortageResponse:
    """Get KPI 2 – Material Shortage.

    Returns items with shortage quantities and shortage percentages.
    """
    service = KPISummaryService(db, scenario_id)
    return service.calculate_kpi2_shortage()


# ============================================================================
# KPI 3 – Workcenter Load
# ============================================================================

@router.get(
    "/{scenario_id}/load",
    response_model=KPI3LoadResponse,
    summary="KPI 3 – Workcenter Load",
    description="Get workcenter load information for a scenario. R3 risk triggered if any load > 100%.",
)
def get_load_kpi(
    scenario_id: str = Path(..., max_length=100),
    db: Session = Depends(get_db),
) -> KPI3LoadResponse:
    """Get KPI 3 – Workcenter Load.

    Returns load percentages for each workcenter per day.
    Overloaded slots (>100%) are flagged.
    """
    service = KPISummaryService(db, scenario_id)
    return service.calculate_kpi3_load()


# ============================================================================
# Daily Plan (backward-fill, feeds KPI3) — computed on demand, not auto-synced
# ============================================================================

@router.post(
    "/daily-plan/rebuild",
    response_model=DailyPlanRebuildResponse,
    summary="Rebuild daily plan (backward-fill)",
    description="Recompute aps_result.aps_daily_plan from aps_mps_plan x aps_item_routing_spec.",
)
def rebuild_daily_plan_endpoint(db: Session = Depends(get_db)) -> DailyPlanRebuildResponse:
    from app.services.material_shortage import apply_daily_material_shortage
    from app.services.scheduling.daily_plan_builder import rebuild_daily_plan

    rows = rebuild_daily_plan(db)
    # Backward material-shortage pass — flags aps_daily_plan.material_shortage_qty
    # per (mps, day) from stock running balance. Must run after the daily plan is built.
    apply_daily_material_shortage(db)
    db.commit()
    daily_status = _workcenter_daily_status_rollup(db)  # re-read persisted rows
    return DailyPlanRebuildResponse(rows_inserted=rows, daily_status=daily_status)


@router.get(
    "/daily-plan",
    response_model=List[DailyPlanRow],
    summary="List daily plan rows",
    description="Rows from aps_result.aps_daily_plan (call POST .../rebuild first to (re)compute).",
)
def list_daily_plan(
    workcenter_id: Optional[int] = Query(None, description="Filter by workcenter ID"),
    start_date: Optional[str] = Query(None, description="Filter work_date >= (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filter work_date <= (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> List[DailyPlanRow]:
    stmt = (
        select(DailyPlan, WorkCenter, ItemRoutingSpec, MpsPlan, Item)
        .join(WorkCenter, DailyPlan.workcenter_id == WorkCenter.id)
        .join(ItemRoutingSpec, DailyPlan.item_routing_id == ItemRoutingSpec.id)
        .join(MpsPlan, DailyPlan.mps_plan_id == MpsPlan.id)
        .outerjoin(Item, MpsPlan.item_id == Item.id)
        .order_by(DailyPlan.work_date, WorkCenter.workcenter_no)
    )
    if workcenter_id is not None:
        stmt = stmt.where(DailyPlan.workcenter_id == workcenter_id)
    if start_date:
        stmt = stmt.where(DailyPlan.work_date >= date_cls.fromisoformat(start_date))
    if end_date:
        stmt = stmt.where(DailyPlan.work_date <= date_cls.fromisoformat(end_date))

    results = db.execute(stmt).all()

    def _statuses(dp) -> List[str]:
        # status: normal | overload | material-shortage | urgent (both)
        if dp.status == "urgent":
            return ["overload", "material-shortage"]
        if dp.status in ("overload", "material-shortage"):
            return [dp.status]
        return ["normal"]

    return [
        DailyPlanRow(
            work_date=dp.work_date,
            workcenter_id=dp.workcenter_id,
            workcenter_no=wc.workcenter_no,
            workcenter_name=wc.workcenter_name,
            planned_qty=float(dp.planned_qty),
            proc_sno=ir.proc_sno,
            proc_name=ir.proc_name,
            plan_no=mp.plan_no,
            item_no=it.item_no if it else None,
            status=dp.status,
            material_shortage_qty=float(dp.material_shortage_qty or 0),
            statuses=_statuses(dp),
        )
        for dp, wc, ir, mp, it in results
    ]


@router.get(
    "/daily-plan/material-shortage-summary",
    response_model=MaterialShortageSummary,
    summary="Total material shortage (daily plan)",
    description="Sum of aps_daily_plan.material_shortage_qty (+ short row/order counts). Filterable by date.",
)
def material_shortage_summary(
    start_date: Optional[str] = Query(None, description="Filter work_date >= (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filter work_date <= (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> MaterialShortageSummary:
    short_flag = case((DailyPlan.material_shortage_qty > 0, 1), else_=0)
    stmt = select(
        func.coalesce(func.sum(DailyPlan.material_shortage_qty), 0),
        func.coalesce(func.sum(short_flag), 0),
        func.count(distinct(case((DailyPlan.material_shortage_qty > 0, DailyPlan.mps_plan_id)))),
    )
    if start_date:
        stmt = stmt.where(DailyPlan.work_date >= date_cls.fromisoformat(start_date))
    if end_date:
        stmt = stmt.where(DailyPlan.work_date <= date_cls.fromisoformat(end_date))

    total, rows, orders = db.execute(stmt).one()
    return MaterialShortageSummary(
        total_shortage_qty=round(float(total or 0), 4),
        short_rows=int(rows or 0),
        short_orders=int(orders or 0),
    )


@router.get(
    "/daily-plan/workcenter-status",
    response_model=List[WorkcenterDailyStatus],
    summary="Workcenter/day load status (for FE color mapping)",
    description=(
        "Workcenter-level rollup of aps_daily_plan — one row per (workcenter, work_date), "
        "no item breakdown. status='overload' (예: 주황/orange) or 'normal' (초록/green). "
        "Call POST .../daily-plan/rebuild first to (re)compute."
    ),
)
def get_workcenter_daily_status(
    workcenter_id: Optional[int] = Query(None, description="Filter by workcenter ID"),
    start_date: Optional[str] = Query(None, description="Filter work_date >= (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filter work_date <= (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> List[WorkcenterDailyStatus]:
    return _workcenter_daily_status_rollup(db, workcenter_id, start_date, end_date)



# ============================================================================
# Workcenter Schedule (Gantt Chart Data)
# ============================================================================

@router.get(
    "/{scenario_id}/workcenter-schedule",
    response_model=List[WorkcenterLoadEntry],
    summary="Workcenter Schedule",
    description="Get workcenter schedule data for Gantt chart visualization.",
)
def get_workcenter_schedule(
    scenario_id: str = Path(..., max_length=100),
    start_date: Optional[str] = Query(
        None, description="Filter by start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(
        None, description="Filter by end date (YYYY-MM-DD)"),
    workcenter_id: Optional[int] = Query(
        None, description="Filter by workcenter ID"),
    db: Session = Depends(get_db),
) -> List[WorkcenterLoadEntry]:
    """Get workcenter schedule data for Gantt chart.

    Returns load entries with color coding:
      - 10% - 80%: Green (normal)
      - 80% - 100%: Yellow/Orange (high)
      - >100%: Red (overloaded)
    """
    service = KPISummaryService(db, scenario_id)
    load_kpi = service.calculate_kpi3_load()

    entries = load_kpi.entries

    # Apply filters if provided
    if start_date:
        from datetime import date as date_type
        start = date_type.fromisoformat(start_date)
        entries = [e for e in entries if e.plan_date >= start]

    if end_date:
        from datetime import date as date_type
        end = date_type.fromisoformat(end_date)
        entries = [e for e in entries if e.plan_date <= end]

    if workcenter_id is not None:
        entries = [e for e in entries if e.workcenter_id == workcenter_id]

    return entries


@router.get(
    "/{scenario_id}/workcenter-load-db",
    response_model=List[WorkcenterLoadByWorkcenter],
    summary="Workcenter load (DB, grouped)",
    description="`workcenter_load` rows grouped by workcenter: each item has name + wc_id + nested load snapshots.",
)
def list_workcenter_load_db(
    scenario_id: str = Path(..., max_length=100),
    workcenter_id: Optional[int] = Query(None, description="Filter by workcenter ID"),
    start_date: Optional[str] = Query(None, description="Filter work_date >= (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filter work_date <= (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> List[WorkcenterLoadByWorkcenter]:
    stmt = (
        select(WorkcenterLoad, WorkCenter.workcenter_name, WorkCenter.workcenter_no)
        .outerjoin(WorkCenter, WorkcenterLoad.workcenter_id == WorkCenter.id)
        .where(WorkcenterLoad.scenario_id == scenario_id)
        .order_by(WorkcenterLoad.workcenter_id, WorkcenterLoad.work_date, WorkcenterLoad.load_id)
    )
    if workcenter_id is not None:
        stmt = stmt.where(WorkcenterLoad.workcenter_id == workcenter_id)
    if start_date:
        stmt = stmt.where(WorkcenterLoad.work_date >= date_cls.fromisoformat(start_date))
    if end_date:
        stmt = stmt.where(WorkcenterLoad.work_date <= date_cls.fromisoformat(end_date))

    meta_by_wc: dict[int, tuple[Optional[str], Optional[str]]] = {}
    lines_by_wc: dict[int, List[WorkcenterLoadLineItem]] = defaultdict(list)

    for wl, wc_name, wc_no in db.execute(stmt):
        wid = wl.workcenter_id
        if wid not in meta_by_wc:
            meta_by_wc[wid] = (wc_name, wc_no)
        lines_by_wc[wid].append(
            WorkcenterLoadLineItem(
                load_id=wl.load_id,
                scenario_id=wl.scenario_id,
                run_id=wl.run_id,
                work_date=wl.work_date,
                operation_id=wl.operation_id,
                proc_name=wl.proc_name,
                used_minutes=float(wl.used_minutes),
                capacity_minutes=float(wl.capacity_minutes),
                load_percent=float(wl.load_percent),
                overloaded=wl.overloaded,
                status=wl.status,
                created_at=wl.created_at,
            )
        )

    # Include idle workcenters from master so the FE heatmap renders a row even
    # when the WC has no plan_operations / workcenter_load entries.
    master_stmt = select(WorkCenter.id, WorkCenter.workcenter_name, WorkCenter.workcenter_no)
    if workcenter_id is not None:
        master_stmt = master_stmt.where(WorkCenter.id == workcenter_id)
    for wid, wc_name, wc_no in db.execute(master_stmt):
        if wid not in meta_by_wc:
            meta_by_wc[wid] = (wc_name, wc_no)

    return [
        WorkcenterLoadByWorkcenter(
            workcenter_name=meta_by_wc[wid][0],
            wc_id=wid,
            workcenter_no=meta_by_wc[wid][1],
            loads=lines_by_wc[wid],
        )
        for wid in sorted(meta_by_wc.keys())
    ]


@router.get(
    "/{scenario_id}/plan-impacted-orders",
    response_model=List[PlanImpactedOrderRow],
    summary="Plan impacted orders (DB)",
    description="Rows from `aps_result.plan_impacted_order` for the scenario.",
)
def list_plan_impacted_orders(
    scenario_id: str = Path(..., max_length=100),
    plan_id: Optional[str] = Query(None, max_length=100, description="Filter by plan_id"),
    reason_type: Optional[str] = Query(None, max_length=20, description="Filter by reason_type (e.g. R1, R2, R3)"),
    db: Session = Depends(get_db),
) -> List[PlanImpactedOrderRow]:
    # Map impacted plan_id -> responsible workcenters.
    # NOTE: workcenter_load.operation_id is NULL in current data, so relation must use
    # scenario/run/workcenter keys rather than operation_id.
    wc_stmt = (
        select(PlanImpactedOrder.plan_id, WorkCenter.id, WorkCenter.workcenter_name)
        .select_from(PlanImpactedOrder)
        .join(
            PlanOperation,
            and_(
                PlanOperation.plan_id == PlanImpactedOrder.plan_id,
                PlanOperation.scenario_id == PlanImpactedOrder.scenario_id,
            ),
        )
        .outerjoin(
            WorkcenterLoad,
            and_(
                WorkcenterLoad.scenario_id == PlanImpactedOrder.scenario_id,
                WorkcenterLoad.workcenter_id == PlanOperation.workcenter_id,
                WorkcenterLoad.run_id == PlanImpactedOrder.run_id,
            ),
        )
        .outerjoin(WorkCenter, WorkCenter.id == PlanOperation.workcenter_id)
        .where(PlanImpactedOrder.scenario_id == scenario_id)
        .distinct()
    )
    if plan_id is not None:
        wc_stmt = wc_stmt.where(PlanImpactedOrder.plan_id == plan_id)

    wc_ids_by_plan: dict[str, List[int]] = defaultdict(list)
    wc_names_by_plan: dict[str, List[str]] = defaultdict(list)
    for pid, wc_id, wc_name in db.execute(wc_stmt).all():
        if wc_id is not None and wc_id not in wc_ids_by_plan[pid]:
            wc_ids_by_plan[pid].append(wc_id)
        if wc_name and wc_name not in wc_names_by_plan[pid]:
            wc_names_by_plan[pid].append(wc_name)

    stmt = (
        select(PlanImpactedOrder, PlanOrder)
        .outerjoin(
            PlanOrder,
            and_(
                PlanImpactedOrder.plan_id == PlanOrder.plan_id,
                PlanImpactedOrder.scenario_id == PlanOrder.scenario_id,
            ),
        )
        .where(PlanImpactedOrder.scenario_id == scenario_id)
        .order_by(PlanImpactedOrder.created_at, PlanImpactedOrder.impacted_id)
    )
    if plan_id is not None:
        stmt = stmt.where(PlanImpactedOrder.plan_id == plan_id)
    if reason_type is not None:
        stmt = stmt.where(PlanImpactedOrder.reason_type == reason_type)
    out: List[PlanImpactedOrderRow] = []
    for impacted, order in db.execute(stmt).all():
        if order is None:
            baseline_sid = _baseline_from_sim_scenario_id(impacted.scenario_id)
            if baseline_sid:
                order = db.execute(
                    select(PlanOrder).where(
                        PlanOrder.plan_id == impacted.plan_id,
                        PlanOrder.scenario_id == baseline_sid,
                    )
                ).scalar_one_or_none()
        order_priority = float(order.priority_score) if order and order.priority_score is not None else None
        out.append(
            PlanImpactedOrderRow(
                impacted_id=impacted.impacted_id,
                scenario_id=impacted.scenario_id,
                plan_id=impacted.plan_id,
                run_id=impacted.run_id,
                demand_id=impacted.demand_id,
                reason_type=impacted.reason_type,
                planned_start_date=order.planned_start_date if order else None,
                planned_ship_date=order.planned_ship_date if order else None,
                planned_finish_date=order.planned_finish_date if order else None,
                late_days=order.late_days if order else None,
                # Source of truth for endpoint output: aps_result.plan_order.priority_score
                priority_score=order_priority,
                workcenter_ids=wc_ids_by_plan.get(impacted.plan_id, []),
                workcenter_names=wc_names_by_plan.get(impacted.plan_id, []),
                message=impacted.message,
                created_at=impacted.created_at,
            )
        )
    # Rank by priority_score desc, then late_days desc (larger delay first), then newest first.
    out.sort(
        key=lambda x: (
            x.priority_score is None,
            -(x.priority_score if x.priority_score is not None else 0.0),
            -(x.late_days if x.late_days is not None else 0),
            -x.created_at.timestamp(),
        )
    )
    return out


# ============================================================================
# Impacted Orders
# ============================================================================

@router.get(
    "/{scenario_id}/impacted-orders",
    response_model=List[DelayedOrderDetail],
    summary="Impacted Orders",
    description="Get orders impacted by risks (delays, shortages, overloads).",
)
def get_impacted_orders(
    scenario_id: str = Path(..., max_length=100),
    risk_type: Optional[str] = Query(
        None, description="Filter by risk type (R1, R2, R3)"),
    db: Session = Depends(get_db),
) -> List[DelayedOrderDetail]:
    """Get impacted orders for a scenario.

    Returns orders affected by risks with delay details.
    """
    service = KPISummaryService(db, scenario_id)
    delivery_kpi = service.calculate_kpi1_delivery()

    details = delivery_kpi.delayed_order_details

    if risk_type:
        # TO DO
        pass

    return details
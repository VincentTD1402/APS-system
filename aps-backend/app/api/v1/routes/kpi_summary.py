from datetime import date as date_cls

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.database import get_db
from app.models import (
    DailyPlan,
    Item,
    ItemRoutingSpec,
    MpsPlan,
    WorkCenter,
)
from app.schemas.kpi_summary import (
    DailyPlanRebuildResponse,
    DailyPlanRow,
    KPI1DeliveryResponse,
    KPI2ShortageResponse,
    KPI3LoadResponse,
    KPI4RiskCountResponse,
    WorkcenterDailyStatus,
)
from app.services.kpi_summary import KPISummaryService
from app.services.kpi_summary.daily_plan_rollup import workcenter_daily_status_rollup


router = APIRouter()


# ============================================================================
# KPI 1 – Delivery Compliance Rate
# ============================================================================

@router.get(
    "/delivery",
    response_model=KPI1DeliveryResponse,
    summary="KPI 1 – Delivery Compliance Rate",
    description="Calculate delivery compliance rate. R1 risk triggered if rate < 100%.",
)
def get_delivery_kpi(
    db: Session = Depends(get_db),
) -> KPI1DeliveryResponse:
    """Get KPI 1 – Delivery Compliance Rate.

    Compares planned_ship_date against delivery_date for all orders.
    Not scenario-scoped: aps_mps_plan has no scenario_id.
    """
    service = KPISummaryService(db, scenario_id="")
    return service.calculate_kpi1_delivery()


# ============================================================================
# KPI 2 – Material Shortage
# ============================================================================

@router.get(
    "/shortage",
    response_model=KPI2ShortageResponse,
    summary="KPI 2 – Material Shortage",
    description=(
        "Get material shortage information (aps_result.aps_material_shortage). "
        "Call POST /kpi-summary/daily-plan/rebuild first to (re)compute. "
        "kpi_value = number of items with shortage. R2 risk triggered if kpi_value > 0."
    ),
)
def get_shortage_kpi(
    db: Session = Depends(get_db),
) -> KPI2ShortageResponse:
    """Get KPI 2 – Material Shortage.

    kpi_value = count of items with shortage (matches FE card, e.g. "6건").
    Returns per-component required/available/shortage quantities.
    Not scenario-scoped: aps_material_shortage is a single BOM-vs-stock snapshot.
    """
    service = KPISummaryService(db, scenario_id="")
    return service.calculate_kpi2_shortage()


# ============================================================================
# KPI 3 – Workcenter Load
# ============================================================================

@router.get(
    "/load",
    response_model=KPI3LoadResponse,
    summary="KPI 3 – Workcenter Overload Rate",
    description=(
        "% of workcenters (aps_workcenter) with at least one overload/urgent day "
        "across the rebuilt aps_result.aps_daily_plan schedule. "
        "Call POST /kpi-summary/daily-plan/rebuild first to (re)compute. "
        "R3 risk triggered if kpi_value > 0."
    ),
)
def get_load_kpi(
    db: Session = Depends(get_db),
) -> KPI3LoadResponse:
    """Get KPI 3 – Workcenter Overload Rate.

    kpi_value = overloaded_wc_count / total_wc_count × 100 (e.g. "5%WC" on FE).
    Not scenario-scoped: aps_daily_plan is a single backward-fill snapshot.
    """
    service = KPISummaryService(db, scenario_id="")
    return service.calculate_kpi3_load()


# ============================================================================
# KPI 4 – Total Risk Count
# ============================================================================

@router.get(
    "/risk-count",
    response_model=KPI4RiskCountResponse,
    summary="KPI 4 – Total Risk Count",
    description=(
        "kpi_value = KPI1 delayed_orders + KPI2 items_with_shortage + KPI3 overloaded_wc_count "
        "(matches FE '계획 수립 예상 리스크' card, e.g. '20건'). "
        "Call POST /kpi-summary/daily-plan/rebuild first so KPI2/KPI3 data is fresh."
    ),
)
def get_risk_count_kpi(
    db: Session = Depends(get_db),
) -> KPI4RiskCountResponse:
    """Get KPI 4 – Total Risk Count (sum of R1 + R2 + R3)."""
    service = KPISummaryService(db, scenario_id="")
    return service.calculate_kpi4_risk_count()


# ============================================================================
# Daily Plan (backward-fill, feeds KPI3) — computed on demand, not auto-synced
# ============================================================================

@router.post(
    "/daily-plan/rebuild",
    response_model=DailyPlanRebuildResponse,
    summary="Rebuild daily plan (backward-fill)",
    description=(
        "Recompute aps_result.aps_daily_plan from aps_mps_plan x aps_item_routing_spec "
        "(feeds KPI3), and aps_result.aps_material_shortage from aps_bom x aps_stock "
        "(feeds KPI2) — one call refreshes both."
    ),
)
def rebuild_daily_plan_endpoint(db: Session = Depends(get_db)) -> DailyPlanRebuildResponse:
    from app.services.material_shortage import apply_daily_material_shortage, rebuild_material_shortage
    from app.services.scheduling.daily_plan_builder import rebuild_daily_plan

    rows = rebuild_daily_plan(db)
    # Backward material-shortage pass — flags aps_daily_plan.material_shortage_qty
    # per (mps, day) from stock running balance. Must run after the daily plan is built.
    apply_daily_material_shortage(db)
    # Per-component required/available/shortage (feeds KPI2) — independent of the
    # daily plan above, but rebuilt together so one call keeps both KPIs fresh.
    rebuild_material_shortage(db)
    db.commit()
    daily_status = workcenter_daily_status_rollup(db)  # re-read persisted rows
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
    return workcenter_daily_status_rollup(db, workcenter_id, start_date, end_date)

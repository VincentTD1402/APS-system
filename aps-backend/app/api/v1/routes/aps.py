"""POST /aps/run and POST /aps/adjust — the scheduling core (fe-be-gap-matrix rows 8-9).

Both are pure reads/mutations over the current DB state — neither calls
daily_plan_builder.rebuild_daily_plan or shortage_builder.rebuild_material_shortage.
That compute already exists as POST /kpi-summary/daily-plan/rebuild; call it
first (or after a G-System sync) so aps_daily_plan/aps_material_shortage are
current. Re-running it here would just duplicate that work.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_logger
from app.db.database import get_db
from app.schemas.aps import (
    ApsAdjustRequest,
    ApsRunInfoOut,
    ApsRunResult,
    DailyPlanEntryOut,
    KpiSnapshotOut,
    LoadCellOut,
    WorkPlanOut,
)
from app.services.scheduling.aps_run_service import (
    AssembledResult,
    PlanIdError,
    adjust_work_plans,
    assemble,
)

logger = get_logger(__name__)

router = APIRouter()


def _to_response(result: AssembledResult) -> ApsRunResult:
    return ApsRunResult(
        run=ApsRunInfoOut(id=result.run.id, started_at=result.run.started_at, finished_at=result.run.finished_at),
        work_plans=[
            WorkPlanOut(
                id=wp.id, run_id=wp.run_id, source_type=wp.source_type, work_order_no=wp.work_order_no,
                tmp_plan_no=wp.tmp_plan_no, order_no=wp.order_no, item_code=wp.item_code,
                item_name_ko=wp.item_name_ko, wc_code=wp.wc_code, process_name_ko=wp.process_name_ko,
                plan_qty=wp.plan_qty, plan_start_date=wp.plan_start_date, plan_end_date=wp.plan_end_date,
                delivery_date=wp.delivery_date, risk_type=wp.risk_type, shortage_qty=wp.shortage_qty,
                adjusted=wp.adjusted, original_start=wp.original_start, original_end=wp.original_end,
                daily_plans=[DailyPlanEntryOut(date=d.date, qty=d.qty, minutes=d.minutes) for d in wp.daily_plans],
            )
            for wp in result.work_plans
        ],
        load_cells=[
            LoadCellOut(
                wc_code=lc.wc_code, cell_date=lc.cell_date, minutes_loaded=lc.minutes_loaded,
                minutes_capacity=lc.minutes_capacity, status=lc.status,
            )
            for lc in result.load_cells
        ],
        kpi=KpiSnapshotOut(
            on_time_rate_pct=result.kpi.on_time_rate_pct,
            material_shortage_count=result.kpi.material_shortage_count,
            overload_wc_pct=result.kpi.overload_wc_pct,
            planning_risk_count=result.kpi.planning_risk_count,
        ),
    )


@router.post(
    "/run",
    response_model=ApsRunResult,
    summary="Assemble the WorkPlan/LoadCell/KPI result from the current schedule",
    description=(
        "Read-only — assembles aps_input.work_order + aps_daily_plan (already computed by "
        "POST /kpi-summary/daily-plan/rebuild) into the full WorkPlan/LoadCell/KPI result "
        "for the FE Work Plan view. Call the rebuild endpoint first if the schedule is stale."
    ),
)
def run_aps(db: Session = Depends(get_db)) -> ApsRunResult:
    try:
        result = assemble(db)
    except Exception as exc:
        logger.exception("POST /aps/run failed")
        raise HTTPException(status_code=500, detail=str(exc))
    return _to_response(result)


@router.post(
    "/adjust",
    response_model=ApsRunResult,
    summary="Apply drag/drop date adjustments and re-assemble the result",
    description=(
        "Re-backward-fills each named WorkPlan into its new [newStart, newEnd] window, "
        "flags the affected aps_daily_plan rows adjusted=true, then re-assembles the full "
        "WorkPlan/LoadCell/KPI result. Does not re-run the G-System-driven full rebuild."
    ),
)
def adjust_aps(request: ApsAdjustRequest, db: Session = Depends(get_db)) -> ApsRunResult:
    adjustments = [(a.plan_id, a.new_start, a.new_end) for a in request.adjustments]
    try:
        result = adjust_work_plans(db, adjustments)
        db.commit()
    except PlanIdError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        db.rollback()
        logger.exception("POST /aps/adjust failed")
        raise HTTPException(status_code=500, detail=str(exc))
    return _to_response(result)

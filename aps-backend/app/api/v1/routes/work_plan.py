"""Work Plan List (작업계획 리스트) — read-only endpoint.

Returns the production work-plan list from aps_input.work_order: confirmed work
orders (기작업지시 미완료) + temporary plans (MPS기준 작업계획 임시산출).
Sourcing rules: docs/workplan.md.
"""

from datetime import date as date_cls

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.work_plan import WorkPlanRow
from app.services.scheduling.work_plan_list import build_work_plan_list

router = APIRouter()


@router.get(
    "/list",
    response_model=list[WorkPlanRow],
    summary="Work Plan List (작업계획 리스트)",
    description=(
        "작업계획 리스트 조회 — confirmed work orders + temporary MPS plans, driven by "
        "aps_input.work_order. 리스크유형 (overload / material_short) is read from "
        "aps_daily_plan; call POST /kpi-summary/daily-plan/rebuild first to (re)compute it. "
        "Load Grid drill-down: pass `work_date` (with `workcenter_no`) to keep only rows whose "
        "plan loads that (workcenter, date) cell in aps_daily_plan — in this mode `workcenter_no` "
        "is the cell's workcenter, not the row's representative one. "
        "Paginated: `limit`/`offset` applied after filter + risk-first sort; total (pre-slice) "
        "row count is returned in the `X-Total-Count` response header."
    ),
)
def list_work_plans(
    response: Response,
    workcenter_no: str | None = Query(
        None, description="Work center no (representative filter; or the Load Grid cell WC when work_date is set)"
    ),
    item_no: str | None = Query(None, description="Filter by item no"),
    risk_type: str | None = Query(
        None, description="Keep rows whose risk_types contains this (e.g. 'overload', 'material_short')"
    ),
    plan_no: str | None = Query(None, description="Match tmp_plan_no / work_order_no / order_no"),
    date_from: str | None = Query(None, description="Keep rows with plan_end >= this (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="Keep rows with plan_start <= this (YYYY-MM-DD)"),
    work_date: str | None = Query(
        None,
        description="Load Grid cell drill-down (YYYY-MM-DD): keep rows loading aps_daily_plan on this day, at workcenter_no if given",
    ),
    limit: int = Query(50, ge=1, le=500, description="Max rows to return (page size)"),
    offset: int = Query(0, ge=0, description="Rows to skip before the page"),
    db: Session = Depends(get_db),
) -> list[WorkPlanRow]:
    rows = build_work_plan_list(
        db,
        workcenter_no=workcenter_no,
        item_no=item_no,
        risk_type=risk_type,
        plan_no=plan_no,
        date_from=date_cls.fromisoformat(date_from) if date_from else None,
        date_to=date_cls.fromisoformat(date_to) if date_to else None,
        work_date=date_cls.fromisoformat(work_date) if work_date else None,
    )
    # Total matches (before pagination) so the FE can build page controls.
    response.headers["X-Total-Count"] = str(len(rows))
    return rows[offset : offset + limit]

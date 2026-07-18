"""Work Plan List (작업계획 리스트) — read-only endpoint.

Returns the production work-plan list combining incomplete work orders and
uncreated MPS plan lines (temporary APS plans). See spec P6.
"""

from datetime import date as date_cls
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.work_plan import WorkPlanRow
from app.services.scheduling.work_plan_list import build_work_plan_list

router = APIRouter()


@router.get(
    "/list",
    response_model=List[WorkPlanRow],
    summary="Work Plan List (작업계획 리스트)",
    description=(
        "작업계획 리스트 조회 — incomplete work orders (기작업지시 미완료) + uncreated MPS "
        "plans (MPS기준 작업계획 임시산출). 공정/워크센터/overload are enriched from "
        "aps_daily_plan; call POST /kpi-summary/daily-plan/rebuild first to (re)compute it."
    ),
)
def list_work_plans(
    workcenter_no: Optional[str] = Query(None, description="Filter by work center no"),
    item_no: Optional[str] = Query(None, description="Filter by item no"),
    risk_type: Optional[str] = Query(None, description="Keep rows whose risk_types contains this (e.g. 'overload')"),
    plan_no: Optional[str] = Query(None, description="Match tmp_plan_no / work_order_no / order_no"),
    date_from: Optional[str] = Query(None, description="Keep rows with plan_end >= this (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Keep rows with plan_start <= this (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> List[WorkPlanRow]:
    return build_work_plan_list(
        db,
        workcenter_no=workcenter_no,
        item_no=item_no,
        risk_type=risk_type,
        plan_no=plan_no,
        date_from=date_cls.fromisoformat(date_from) if date_from else None,
        date_to=date_cls.fromisoformat(date_to) if date_to else None,
    )

"""POST /erp/purchase-requests and POST /erp/work-orders (fe-be-gap-matrix rows 10-11).

Both only insert a local outbox-shaped row (status PENDING/PLANNED) — per the
CSV's own note, the actual G-System push is a separate future background job,
out of scope here. FE only needs the toast-success response shape.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_logger
from app.db.database import get_db
from app.models.input.mps_plan import MpsPlan
from app.models.input.item_routing import ItemRoutingSpec
from app.models.input.work_order import WorkOrder
from app.models.output.purchase_request import PurchaseRequest
from app.schemas.erp import ErpOutboxRow, PurchaseRequestCreateIn, WorkOrderDispatchIn
from app.services.gsystem.db_syncer import gen_temp_id
from app.services.scheduling.aps_run_service import PlanIdError, decode_plan_id

logger = get_logger(__name__)

router = APIRouter()


def _resolve_mps_plan(db: Session, plan_id: str) -> tuple[MpsPlan, ItemRoutingSpec]:
    try:
        mps_plan_id, item_routing_id = decode_plan_id(plan_id)
    except PlanIdError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    mps = db.get(MpsPlan, mps_plan_id)
    routing = db.get(ItemRoutingSpec, item_routing_id)
    if mps is None or routing is None:
        raise HTTPException(status_code=404, detail=f"planId={plan_id} not found")
    return mps, routing


@router.post(
    "/purchase-requests",
    response_model=ErpOutboxRow,
    summary="Create a local purchase-request outbox row for a shortage WorkPlan",
    description=(
        "Inserts aps_result.purchase_request with status=PENDING. Does not push to "
        "G-System synchronously — that's a separate future background job."
    ),
)
def create_purchase_request(body: PurchaseRequestCreateIn, db: Session = Depends(get_db)) -> ErpOutboxRow:
    mps, _routing = _resolve_mps_plan(db, body.plan_id)
    if mps.item_id is None:
        raise HTTPException(status_code=422, detail=f"planId={body.plan_id} has no resolved item")

    need_date: date | None = mps.delivery_date or mps.plan_end_date
    row = PurchaseRequest(
        scenario_id="",
        item_id=mps.item_id,
        shortage_qty=body.qty,
        need_date=need_date,
        source_type="APS_RUN",
        status="PENDING",
        response_json={"planId": body.plan_id, "note": body.note} if body.note else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return ErpOutboxRow(
        id=row.id, run_id=None, action="CREATE_PURCHASE_REQUEST",
        payload={"planId": body.plan_id, "qty": body.qty, "note": body.note},
        status=row.status, created_at=row.created_at, pushed_at=None, error=None,
    )


@router.post(
    "/work-orders",
    response_model=ErpOutboxRow,
    summary="Dispatch a WorkPlan as a local PLANNED work_order outbox row",
    description=(
        "Upserts aps_input.work_order (reuses an existing PLANNED stub for the same "
        "MPS plan/routing step if one exists). Does not push to G-System synchronously."
    ),
)
def create_work_order(body: WorkOrderDispatchIn, db: Session = Depends(get_db)) -> ErpOutboxRow:
    mps, routing = _resolve_mps_plan(db, body.plan_id)

    wo = db.execute(
        select(WorkOrder).where(
            WorkOrder.mps_plan_id == mps.id, WorkOrder.item_routing_id == routing.id
        )
    ).scalar_one_or_none()
    payload = {"planId": body.plan_id}
    if wo is None:
        wo = WorkOrder(
            temp_id=gen_temp_id(db, mps.plan_start_date or mps.plan_date),
            mps_plan_id=mps.id,
            item_routing_id=routing.id,
            item_id=mps.item_id,
            workcenter_id=routing.workcenter_id,
            qty=mps.plan_qty,
            status="PLANNED",
            payload_json=payload,
        )
        db.add(wo)
    else:
        wo.payload_json = payload

    db.commit()
    db.refresh(wo)

    return ErpOutboxRow(
        id=wo.id, run_id=None, action="CREATE_WORK_ORDER", payload=payload,
        status=wo.status, created_at=wo.created_at, pushed_at=wo.sent_at, error=None,
    )

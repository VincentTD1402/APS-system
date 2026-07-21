"""POST /erp/purchase-requests and POST /erp/work-orders (fe-be-gap-matrix rows 10-11).

planId = work_order.id (see app.services.scheduling.aps_run_service — every
WorkPlan returned by /aps/run is backed by exactly one aps_input.work_order
row, confirmed or PLANNED stub), so both handlers resolve it with a plain
db.get(WorkOrder, ...) — no derivation needed.

Neither endpoint pushes to G-System synchronously — that's a separate future
background job, out of scope here. FE only needs the toast-success response.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_logger
from app.db.database import get_db
from app.models.input.mps_plan import MpsPlan
from app.models.input.work_order import WorkOrder
from app.models.output.purchase_request import PurchaseRequest
from app.schemas.erp import ErpOutboxRow, PurchaseRequestCreateIn, WorkOrderDispatchIn
from app.services.scheduling.aps_run_service import PlanIdError, parse_plan_id

logger = get_logger(__name__)

router = APIRouter()


# FE's ErpOutboxStatus = 'PENDING' | 'PUSHED' | 'FAILED' — map the underlying
# domain-specific status columns onto it rather than exposing them raw.
def _purchase_request_outbox_status(row: PurchaseRequest) -> str:
    if row.sync_status == "SUCCESS":
        return "PUSHED"
    if row.sync_status in ("FAILED", "ERROR"):
        return "FAILED"
    return "PENDING"


def _work_order_outbox_status(row: WorkOrder) -> str:
    if row.status == "CONFIRMED":
        return "PUSHED"
    if row.status == "FAILED":
        return "FAILED"
    return "PENDING"  # PLANNED | SENT


def _resolve_work_order(db: Session, plan_id: str) -> WorkOrder:
    try:
        wo_id = parse_plan_id(plan_id)
    except PlanIdError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    wo = db.get(WorkOrder, wo_id)
    if wo is None:
        raise HTTPException(status_code=404, detail=f"planId={plan_id} not found")
    return wo


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
    wo = _resolve_work_order(db, body.plan_id)
    if wo.item_id is None:
        raise HTTPException(status_code=422, detail=f"planId={body.plan_id} has no resolved item")

    mps = db.get(MpsPlan, wo.mps_plan_id) if wo.mps_plan_id is not None else None
    need_date = (mps.delivery_date or mps.plan_end_date) if mps is not None else None
    row = PurchaseRequest(
        scenario_id="",
        item_id=wo.item_id,
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
        id=str(row.id), run_id=None, action="CREATE_PURCHASE_REQUEST",
        payload={"planId": body.plan_id, "qty": body.qty, "note": body.note},
        status=_purchase_request_outbox_status(row), created_at=row.created_at,
        pushed_at=row.sent_at, error=None,
    )


@router.post(
    "/work-orders",
    response_model=ErpOutboxRow,
    summary="Dispatch a WorkPlan's work_order for G-System push",
    description=(
        "planId always names an existing aps_input.work_order row (real or PLANNED "
        "stub) — updates its payload_json. Does not push to G-System synchronously."
    ),
)
def create_work_order(body: WorkOrderDispatchIn, db: Session = Depends(get_db)) -> ErpOutboxRow:
    wo = _resolve_work_order(db, body.plan_id)
    payload = {"planId": body.plan_id}
    wo.payload_json = payload

    db.commit()
    db.refresh(wo)

    return ErpOutboxRow(
        id=str(wo.id), run_id=None, action="CREATE_WORK_ORDER", payload=payload,
        status=_work_order_outbox_status(wo), created_at=wo.created_at,
        pushed_at=wo.sent_at, error=None,
    )

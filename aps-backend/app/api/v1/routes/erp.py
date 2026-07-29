"""POST /erp/purchase-requests and POST /erp/work-orders (fe-be-gap-matrix rows 10-11).

planId = work_order.id (see app.services.scheduling.aps_run_service — every
WorkPlan returned by /aps/run is backed by exactly one aps_input.work_order
row, confirmed or PLANNED stub), so both handlers resolve it with a plain
db.get(WorkOrder, ...) — no derivation needed.

POST /purchase-requests pushes to G-System synchronously (POST /pu/puOrderReq/aps/save).
POST /work-orders does not — that's still a separate future background job.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_logger, settings
from app.db.database import get_db
from app.models.input.item import Item
from app.models.input.item_routing import ItemRoutingSpec
from app.models.input.mps_plan import MpsPlan
from app.models.input.work_order import WorkOrder
from app.models.input.workcenter import WorkCenter
from app.models.output.daily_plan import DailyPlan
from app.models.output.purchase_request import PurchaseRequest
from app.schemas.erp import ErpOutboxRow, PurchaseRequestCreateIn, PurchaseRequestLineIn, WorkOrderDispatchIn
from app.services.gsystem.api_client import GSystemClient, GSystemConfig
from app.services.gsystem.db_syncer import _parse_date
from app.services.scheduling.aps_run_service import PlanIdError, _resolve_item_routing_id, parse_plan_id

logger = get_logger(__name__)

router = APIRouter()

# Fixed "APS service account" / "internal customer" identity — G-System's DB
# rejects blank deptId/empId/userId/custId (FK/NOT NULL on those references).
# No real auth/session exists yet to fill these per-user, so every purchase
# request created from APS is attributed to this one fixed identity.
_APS_DEPT_ID = "36"
_APS_DEPT_NM = "전사"
_APS_EMP_ID = "209"
_APS_FULL_NM = "Minh"
_APS_USER_ID = "209"
_APS_CURR_CD = "10171002"
_APS_CUST_ID = 254
_APS_CUST_NM = "Internal Production Order"


def _build_purchase_order_detail_line(item: Item, qty: float, row_index: int, note: str | None, need_date: date | None) -> dict[str, Any]:
    """Build one puOrderReq.detail[] entry for a raw-material item.

    Price/vat/amt fields are left at 0 — not tracked anywhere in APS locally.
    """
    today = date.today().isoformat()
    return {
        "_status": "A",
        "rowIndex": row_index,
        "sel": False,
        "assetTypeCd": item.asset_type_cd or "",
        "curAmt": 0,
        "curPrice": 0,
        "curTotAmt": 0,
        "curVat": 0,
        "currCd": _APS_CURR_CD,
        "custId": _APS_CUST_ID,
        "custNm": _APS_CUST_NM,
        "delvReqDate": need_date.isoformat() if need_date else today,
        "diRemark": note or "",
        "itemId": item.gsystem_id,
        "itemNo": item.item_no,
        "itemNm": item.item_name,
        "krwAmt": 0,
        "krwPrice": 0,
        "krwTotAmt": 0,
        "krwVat": 0,
        "lotYn": bool(item.lot_yn),
        "material": item.material or "",
        "pareaId": settings.GSYSTEM_DEFAULT_PAREA_ID,
        "purchasePriceVatYn": bool(item.purchase_price_vat_yn),
        "qty": qty,
        "spec": item.spec or "",
        "stkUnitCd": item.unit_cd or "",
        "stockUnitCd": item.unit_cd or "",
        "unitCovOption": [],
    }


def _build_purchase_order_payload(details: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the G-System POST /pu/puOrderReq/aps/save body — one master, N detail lines."""
    today = date.today().isoformat()
    return {
        "master": {
            "ownerNm": "",
            "reqNo": "",
            "expKind": "",
            "currCd": _APS_CURR_CD,
            "exRate": 1,
            "deptId": _APS_DEPT_ID,
            "deptNm": _APS_DEPT_NM,
            "empId": _APS_EMP_ID,
            "fullNm": _APS_FULL_NM,
            "orderDate": today,
            "pareaId": settings.GSYSTEM_DEFAULT_PAREA_ID,
            "remark": "purchase request from APS system",
            "reqDate": today,
            "userId": _APS_USER_ID,
        },
        "detail": details,
    }


def _submit_to_gsystem(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """POST the purchase order to G-System. Returns (sync_status, response_json).

    Never raises — a push failure must not block saving the local outbox row;
    the caller reports it via sync_status/response_json instead.
    """
    cfg = GSystemConfig(
        base_url=settings.GSYSTEM_BASE_URL,
        api_key=settings.GSYSTEM_API_KEY,
        timeout=settings.GSYSTEM_TIMEOUT,
        retries=settings.GSYSTEM_RETRIES,
    )
    try:
        with GSystemClient(cfg) as client:
            response = client.submit_purchase_order(payload)
    except Exception as exc:
        logger.exception("purchase order push to G-System failed")
        return "FAILED", {"error": str(exc)}
    if response.get("statusCode") == "000":
        return "SUCCESS", response
    return "FAILED", response


def _build_work_order_dispatch_payload(
    wo: WorkOrder, item: Item, wc: WorkCenter | None, routing: ItemRoutingSpec | None, mps: MpsPlan | None
) -> dict[str, Any]:
    """Build the G-System POST /pd/WorkOrderProc/aps/save body — a single-element list.

    stockYn/inspectionYn/procNm/inspecKind come from the work order's own
    routing step (aps_item_routing_spec), the same row procId/procNm are read
    from — not from aps_item, which has no such columns.
    """
    return [
        {
            "routingId": "",
            "stkUnitCd": item.unit_cd or "",
            "goodItemId": str(item.gsystem_id) if item.gsystem_id is not None else "",
            "workOrderSerl": wo.work_order_serl,
            "procId": routing.gsystem_proc_id if routing else None,
            "assetTypeCd": item.asset_type_cd or "",
            "inspecKind": routing.inspec_type if routing else "",
            "prodId": (
                str(wo.gsystem_work_order_id) if wo.gsystem_work_order_id is not None
                else (str(mps.gsystem_id) if mps is not None else "")
            ),
            "itemNo": item.item_no,
            "itemNm": item.item_name,
            "oscustNm": wc.workcenter_name if wc else "",
            "custSeq": None,
            "workshopId": wc.gsystem_id if wc else None,
            "workshopNm": wc.workcenter_name if wc else "",
            "orderQty": float(wo.qty) if wo.qty is not None else 0,
            "stockYn": bool(routing.stock_yn) if routing else False,
            "inspectionYn": bool(routing.inspection_yn) if routing else False,
            "procNm": routing.proc_name if routing else "",
            "prodNo": (mps.plan_no if mps and mps.plan_no else None) or wo.temp_id or "",
            "planNo": mps.plan_no if mps else None,
            "planDate": mps.plan_date.isoformat() if mps and mps.plan_date else None,
            "workDate": wo.work_date.isoformat() if wo.work_date else None,
            "workOrderDate": wo.work_order_date.isoformat() if wo.work_order_date else None,
            "workOrderNo": wo.work_order_no or wo.temp_id,
            "pareaId": "1",
            "empId": _APS_EMP_ID,
            "deptId": _APS_DEPT_ID,
            "_status": "A",
            "corpId": 1,
            "USER_SEQ": 0,
            "sourcePlans": [
                {
                    "planId": mps.gsystem_id,
                    "planNo": mps.plan_no,
                    "planDate": mps.plan_date.isoformat() if mps.plan_date else None,
                    "orderQty": float(mps.order_qty) if mps.order_qty is not None else None,
                    "itemId": mps.gsystem_item_id,
                }
            ] if mps is not None else [],
        }
    ]


def _submit_work_order_to_gsystem(payload: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    """POST the work order dispatch to G-System (different host from GSYSTEM_BASE_URL).

    Never raises — a push failure must not block saving local state; the
    caller reports it via sync_status/response_json instead.
    """
    cfg = GSystemConfig(
        base_url=settings.GSYSTEM_WORKORDER_BASE_URL,
        api_key=settings.GSYSTEM_API_KEY,
        timeout=settings.GSYSTEM_TIMEOUT,
        retries=settings.GSYSTEM_RETRIES,
    )
    try:
        with GSystemClient(cfg) as client:
            response = client.submit_work_order_dispatch(payload)
    except Exception as exc:
        logger.exception("work order dispatch push to G-System failed")
        return "FAILED", {"error": str(exc)}
    status_code = response.get("statusCode") if isinstance(response, dict) else None
    if status_code == "000":
        return "SUCCESS", response
    return "FAILED", response if isinstance(response, dict) else {"raw": response}


def _apply_work_order_dispatch_result(wo: WorkOrder, response: dict[str, Any]) -> None:
    """After a successful dispatch, promote wo straight to CONFIRMED using the
    G-System response's own result object — same fields sync_work_orders()
    reads off the GET /pd/workorder feed (id, workOrderNo, workOrderSerl,
    workDate), just applied immediately instead of waiting for the next
    periodic sync. Without this, wo.status stayed "SENT" (neither
    _is_confirmed nor _is_planned in work_plan_list.py), so the row dropped
    out of the Work Plan List and the FE kept showing the stale tmp_plan_no
    — verified live: work_order id=3 had sync_status=SUCCESS with a real
    workOrderNo in response_json.result[0], but work_order_no/status/temp_id
    were never updated from it.

    Also overwrites wo.response_json with this flat result record (was the
    raw envelope {"result": [...], "statusCode": ..., ...}) — work_plan_list.py's
    confirmed branch reads resp.get("procNm")/itemNo/endDate expecting the
    flat shape sync_work_orders() stores (rec, not the envelope); leaving the
    envelope in place silently blanks 공정/품목/계획완료 for rows confirmed via
    direct dispatch instead of the periodic sync.
    """
    result = (response.get("result") or [{}])[0] if isinstance(response, dict) else {}
    if result.get("id") is not None:
        try:
            wo.gsystem_work_order_id = int(result["id"])
        except (TypeError, ValueError):
            pass
    wo.work_order_no = result.get("workOrderNo") or wo.work_order_no or wo.temp_id
    if result.get("workOrderSerl") is not None:
        try:
            wo.work_order_serl = int(result["workOrderSerl"])
        except (TypeError, ValueError):
            pass
    if result.get("workDate"):
        wo.work_date = _parse_date(result["workDate"])
    wo.temp_id = None
    wo.status = "CONFIRMED"
    wo.response_json = result


def _push_mps_plan_dates_for_dispatch(db: Session, wo: WorkOrder, item_routing_id: int, mps: MpsPlan) -> None:
    """After a successful work order dispatch, push this MPS line's current
    schedule (min/max aps_daily_plan.work_date for this routing step) back to
    G-System (/pd/prodPlanMpsMng/aps/updateDates) — only dispatch confirms the
    plan is real, so that's when G-System's MPS record should move.

    On a successful push, also writes mps.prod_end_date/status_cd locally
    instead of waiting for the next periodic G-System resync (sync_mps_plan) —
    daily_plan_builder._anchor_end_date() only trusts prod_end_date when
    status_cd=="created", and without this the very next RUN right after
    dispatch would still anchor on the old plan_end_date. G-System has no
    local prod_start_date counterpart to update (backward-fill only needs one
    end anchor; the start date is a computed output, not an input).

    Outcome is recorded on wo.mps_dates_sync_status/mps_dates_response_json/
    mps_dates_sent_at (caller commits). Never raises — a push failure must not
    block the local dispatch result.
    """
    if mps.gsystem_id is None:
        return
    work_dates = db.execute(
        select(DailyPlan.work_date).where(
            DailyPlan.mps_plan_id == wo.mps_plan_id, DailyPlan.item_routing_id == item_routing_id
        )
    ).scalars().all()
    if not work_dates:
        return
    prod_end_date = max(work_dates)
    payload = [{
        "id": mps.gsystem_id,
        "prodStartDate": min(work_dates).isoformat(),
        "prodEndDate": prod_end_date.isoformat(),
    }]
    cfg = GSystemConfig(
        base_url=settings.GSYSTEM_WORKORDER_BASE_URL,
        api_key=settings.GSYSTEM_API_KEY,
        timeout=settings.GSYSTEM_TIMEOUT,
        retries=settings.GSYSTEM_RETRIES,
    )
    wo.mps_dates_sent_at = datetime.now(timezone.utc)
    try:
        with GSystemClient(cfg) as client:
            response = client.submit_mps_plan_dates_update(payload)
    except Exception as exc:
        logger.exception("mps plan dates update push to G-System failed: payload=%s", payload)
        wo.mps_dates_sync_status = "FAILED"
        wo.mps_dates_response_json = {"error": str(exc)}
        return
    status_code = response.get("statusCode") if isinstance(response, dict) else None
    wo.mps_dates_sync_status = "SUCCESS" if status_code == "000" else "FAILED"
    wo.mps_dates_response_json = response if isinstance(response, dict) else {"raw": response}
    if wo.mps_dates_sync_status == "SUCCESS":
        mps.prod_end_date = prod_end_date
        mps.status_cd = "created"


# FE's ErpOutboxStatus = 'PENDING' | 'PUSHED' | 'FAILED' — map the underlying
# domain-specific status columns onto it rather than exposing them raw.
def _purchase_request_outbox_status(row: PurchaseRequest) -> str:
    if row.sync_status == "SUCCESS":
        return "PUSHED"
    if row.sync_status in ("FAILED", "ERROR"):
        return "FAILED"
    return "PENDING"


def _work_order_outbox_status(row: WorkOrder) -> str:
    if row.status == "CONFIRMED" or row.sync_status == "SUCCESS":
        return "PUSHED"
    if row.status == "FAILED" or row.sync_status in ("FAILED", "ERROR"):
        return "FAILED"
    return "PENDING"  # PLANNED | SENT, not yet pushed


def _resolve_work_order(db: Session, plan_id: str) -> WorkOrder:
    try:
        wo_id = parse_plan_id(plan_id)
    except PlanIdError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    wo = db.get(WorkOrder, wo_id)
    if wo is None:
        raise HTTPException(status_code=404, detail=f"planId={plan_id} not found")
    return wo


def _resolve_line_items(db: Session, lines: list[PurchaseRequestLineIn], plan_id: str) -> list[tuple[PurchaseRequestLineIn, Item]]:
    """Resolve each line's item_no (a BOM raw-material component) to its aps_item row."""
    if not lines:
        raise HTTPException(status_code=422, detail=f"planId={plan_id} has no purchase lines")
    resolved: list[tuple[PurchaseRequestLineIn, Item]] = []
    for line in lines:
        item = db.execute(select(Item).where(Item.item_no == line.item_no)).scalar_one_or_none()
        if item is None:
            raise HTTPException(status_code=422, detail=f"itemNo={line.item_no!r} not found")
        resolved.append((line, item))
    return resolved


@router.post(
    "/purchase-requests",
    response_model=ErpOutboxRow,
    summary="Create a purchase request (one or more raw-material lines) and push it to G-System",
    description=(
        "Each line names a raw-material aps_item (item_no) needed by the plan's "
        "BOM — not the plan's own product/semi-product item. Inserts one "
        "aps_result.purchase_request row per line, then synchronously pushes all "
        "lines as one G-System POST /pu/puOrderReq/aps/save call. sync_status/"
        "response_json record the push outcome; local rows are saved either way."
    ),
)
def create_purchase_request(body: PurchaseRequestCreateIn, db: Session = Depends(get_db)) -> ErpOutboxRow:
    wo = _resolve_work_order(db, body.plan_id)
    resolved_lines = _resolve_line_items(db, body.lines, body.plan_id)

    mps = db.get(MpsPlan, wo.mps_plan_id) if wo.mps_plan_id is not None else None
    need_date = (mps.delivery_date or mps.plan_end_date) if mps is not None else None

    details = [
        _build_purchase_order_detail_line(item, line.qty, idx, body.note, need_date)
        for idx, (line, item) in enumerate(resolved_lines)
    ]
    payload = _build_purchase_order_payload(details)
    sync_status, response = _submit_to_gsystem(payload)

    rows: list[PurchaseRequest] = []
    for line, item in resolved_lines:
        row = PurchaseRequest(
            scenario_id="",
            item_id=item.id,
            shortage_qty=line.qty,
            need_date=need_date,
            source_type="APS_RUN",
            status="PENDING",
            sync_status=sync_status,
            response_json={"planId": body.plan_id, "note": body.note, "gsystemResponse": response},
        )
        db.add(row)
        rows.append(row)
    db.commit()
    for row in rows:
        db.refresh(row)

    return ErpOutboxRow(
        id=",".join(str(row.id) for row in rows), run_id=None, action="CREATE_PURCHASE_REQUEST",
        payload={"planId": body.plan_id, "note": body.note, "lines": [line.model_dump(by_alias=True) for line, _ in resolved_lines]},
        status=_purchase_request_outbox_status(rows[0]), created_at=rows[0].created_at,
        pushed_at=rows[0].sent_at, error=response.get("message") if sync_status == "FAILED" else None,
    )


@router.post(
    "/work-orders",
    response_model=ErpOutboxRow,
    summary="Dispatch a work order (\"chỉ thị sản xuất\") and push it to G-System",
    description=(
        "planId names an existing aps_input.work_order row (real or PLANNED stub). "
        "Builds the POST /pd/WorkOrderProc/aps/save body from work_order/item/"
        "workcenter/item_routing_spec/mps_plan and pushes synchronously to a "
        "separate G-System host (GSYSTEM_WORKORDER_BASE_URL). sync_status/"
        "response_json record the push outcome; local row is saved either way."
    ),
)
def create_work_order(body: WorkOrderDispatchIn, db: Session = Depends(get_db)) -> ErpOutboxRow:
    wo = _resolve_work_order(db, body.plan_id)
    if wo.item_id is None:
        raise HTTPException(status_code=422, detail=f"planId={body.plan_id} has no resolved item")
    item = db.get(Item, wo.item_id)
    if item is None:
        raise HTTPException(status_code=422, detail=f"planId={body.plan_id} item_id={wo.item_id} not found")

    # Real G-System-synced work_order rows never carry item_routing_id — fall
    # back to the MPS line's routing step via aps_daily_plan (same resolver
    # POST /aps/adjust uses), same reasoning: only PLANNED stubs set it directly.
    try:
        item_routing_id = _resolve_item_routing_id(db, wo)
    except PlanIdError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    routing = db.get(ItemRoutingSpec, item_routing_id)
    wc = db.get(WorkCenter, wo.workcenter_id) if wo.workcenter_id is not None else (
        db.get(WorkCenter, routing.workcenter_id) if routing is not None and routing.workcenter_id is not None else None
    )
    # A confirmed work_order row's Work Plan List workcenter column reads
    # wo.workcenter_id directly (no routing fallback there, unlike PLANNED
    # rows) — persist the resolved workcenter now so it doesn't go blank the
    # moment this row flips from PLANNED/MPS to CONFIRMED/WO below.
    if wo.workcenter_id is None and wc is not None:
        wo.workcenter_id = wc.id
    mps = db.get(MpsPlan, wo.mps_plan_id) if wo.mps_plan_id is not None else None

    payload = _build_work_order_dispatch_payload(wo, item, wc, routing, mps)
    sync_status, response = _submit_work_order_to_gsystem(payload)

    wo.payload_json = payload[0]
    wo.response_json = response
    wo.sync_status = sync_status
    wo.sent_at = datetime.now(timezone.utc)

    if sync_status == "SUCCESS":
        _apply_work_order_dispatch_result(wo, response)
    else:
        wo.status = "FAILED"

    if sync_status == "SUCCESS" and mps is not None:
        _push_mps_plan_dates_for_dispatch(db, wo, item_routing_id, mps)

    db.commit()
    db.refresh(wo)

    return ErpOutboxRow(
        id=str(wo.id), run_id=None, action="CREATE_WORK_ORDER", payload=payload[0],
        status=_work_order_outbox_status(wo), created_at=wo.created_at,
        pushed_at=wo.sent_at,
        error=response.get("message") if isinstance(response, dict) and sync_status == "FAILED" else None,
    )

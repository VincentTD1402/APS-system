"""Workorder API endpoint to forward APS workorders to G-System.

Behavior:
- Accepts a JSON array of workorder objects (or single object) in the request body.
- Ensures `bizId`/`corpId` defaults to (7,1) if missing.
- Generates `workOrderNo` as `WO-YYYYMMDD-<timestamp>` when not provided.
- If `itemId` is provided, attempts to resolve local `aps_item.gsystem_id` or local id; if missing
  and `itemId` is available, falls back to sending `itemId`/`itemNm`.
- Forwards the prepared payload to G-System `/api/pd/workorder/aps/save` endpoint and returns response.
"""

from __future__ import annotations

from datetime import datetime
import random
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session

from app.config import get_logger, settings
from app.db.database import get_db
from app.models.input.stock import Stock
from app.models.input.item_process import ItemProcessStep
from app.models.input.item import Item
from app.models.input.workcenter import WorkCenter
from app.models.output.plan_order import PlanOrder, PlanOperation
from app.models.output.work_order import WorkOrder
from app.models.input.demand import Demand
from app.services.gsystem.api_client import GSystemConfig, GSystemClient
from sqlalchemy import or_, select


def _workcenter_match_keys(value: Any) -> set[str]:
    if value is None:
        return set()
    text = str(value).strip()
    if not text:
        return set()
    compact = "".join(ch for ch in text.lower() if ch.isalnum())
    digits = "".join(ch for ch in text if ch.isdigit())
    keys = {text, text.lower(), compact}
    if digits:
        keys.add(digits)
        keys.add(digits.lstrip("0") or "0")
    return keys


def _extract_workcenter_filters(payload: Any) -> set[str]:
    if not isinstance(payload, dict):
        return set()

    values: set[str] = set()

    def add(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                add(item)
            return
        text = str(value).strip()
        if text:
            values.update(_workcenter_match_keys(text))

    for key in (
        "work_centers",
        "responsible_work_centers",
        "responsible_workcenter_ids",
        "workcenter_ids",
        "workcenter_id",
        "workcenter_no",
    ):
        add(payload.get(key))
    return values


def _operation_matches_workcenters(op: PlanOperation, workcenter_filters: set[str]) -> bool:
    if not workcenter_filters:
        return True

    wc = op.workcenter
    candidates = set()
    candidates.update(_workcenter_match_keys(op.workcenter_id))
    if wc is not None:
        for value in (
            getattr(wc, "id", None),
            getattr(wc, "gsystem_id", None),
            getattr(wc, "workcenter_no", None),
            getattr(wc, "workcenter_name", None),
        ):
            if value is not None and str(value).strip():
                candidates.update(_workcenter_match_keys(value))
    return bool(candidates & workcenter_filters)


def _payload_from_plan_operation(db: Session, op: PlanOperation, existing_nums: set[int] | None = None) -> tuple[dict, bool]:
    row, created = _get_or_create_workorder_for_operation(db, op, existing_nums=existing_nums)
    po = op.order
    demand = po.demand if po else None
    item = demand.item if demand else None

    record: dict[str, Any] = {
        "planDate": row.get("planDate"),
        "planNo": row.get("planNo") or op.plan_id,
        "orderQty": row.get("orderQty") or row.get("planQty") or 0,
        "itemId": row.get("itemId"),
        "procId": row.get("procId"),
        "workDate": row.get("workDate") or row.get("planDate"),
        "workOrderDate": row.get("workOrderDate") or row.get("workDate") or row.get("planDate"),
        "workOrderNo": row["workOrderNo"],
        "workOrderSerl": row.get("workOrderSerl") or 1,
        "status": row.get("status") or "A",
        "bizId": settings.WORKORDER_DEFAULT_BIZ_ID,
        "corpId": settings.WORKORDER_DEFAULT_CORP_ID,
        "deptId": settings.WORKORDER_DEFAULT_DEPT_ID,
        "cntuProcYn": settings.WORKORDER_DEFAULT_CNTU_PROC_YN,
        "stockYn": settings.WORKORDER_DEFAULT_STOCK_YN,
        "workcenterId": row.get("workcenterId"),
        "workcenterNo": row.get("workcenterNo"),
        "workcenterName": row.get("workcenterName"),
        "responsibleWorkcenterId": row.get("responsibleWorkcenterId") or row.get("workcenterId"),
        "responsibleWorkcenterNo": row.get("responsibleWorkcenterNo") or row.get("workcenterNo"),
    }

    if item is not None:
        item_process = (
            db.query(ItemProcessStep)
            .filter(ItemProcessStep.item_id == item.id)
            .order_by(ItemProcessStep.proc_sno.asc(), ItemProcessStep.id.asc())
            .first()
        )
        if item_process is not None and getattr(item_process, "stock_yn", None) is not None:
            record["stockYn"] = "true" if bool(item_process.stock_yn) else "false"

        stock = (
            db.query(Stock)
            .filter(Stock.gsystem_item_id.in_([str(item.gsystem_id), item.item_no] if item.gsystem_id is not None else [item.item_no]))
            .order_by(Stock.mod_dt.desc().nullslast(), Stock.reg_dt.desc().nullslast())
            .first()
        )
        if stock is not None and getattr(stock, "unit_cd", None):
            record["stkUnitCd"] = stock.unit_cd

    if demand is not None and getattr(demand, "status_cd", None):
        record["statusCd"] = ""

    return record, created


def _build_payload_from_scenario(
    db: Session,
    scenario_id: str,
    existing_nums: set[int] | None = None,
    workcenter_filters: set[str] | None = None,
) -> list[dict]:
    """Construct persisted workorder records from scheduled operations for a scenario."""
    ops = (
        db.query(PlanOperation)
        .join(PlanOrder, PlanOrder.plan_id == PlanOperation.plan_id)
        .filter(PlanOperation.scenario_id == scenario_id)
        .order_by(PlanOperation.planned_start_dt.asc(), PlanOperation.sequence.asc(), PlanOperation.plan_op_id.asc())
        .all()
    )
    if not ops:
        raise RuntimeError(f"No PlanOperation rows found for scenario_id={scenario_id}")

    def build_for_operations(selected_ops: list[PlanOperation]) -> list[dict]:
        nonlocal created_any
        rows: list[dict] = []
        for selected_op in selected_ops:
            record, created = _payload_from_plan_operation(db, selected_op, existing_nums=existing_nums)
            if created:
                db.flush()
                created_any = True
            rows.append(record)
        return rows

    created_any = False
    filters = workcenter_filters or set()
    matched_ops = [op for op in ops if _operation_matches_workcenters(op, filters)]
    out_list = build_for_operations(matched_ops)

    if filters and not out_list:
        logger.warning(
            "workorder/save: no PlanOperation matched workcenter filters=%s for scenario_id=%s; falling back to all operations",
            sorted(filters),
            scenario_id,
        )
        out_list = build_for_operations(ops)

    if not out_list:
        raise RuntimeError(f"No usable workorder rows could be constructed for scenario_id={scenario_id}")
    if created_any:
        db.flush()
    return out_list


def _build_preview_from_scenario(
    db: Session,
    scenario_id: str,
    existing_nums: set[int] | None = None,
    workcenter_filters: set[str] | None = None,
) -> list[dict]:
    """Construct workorder preview rows without persisting or sending them."""
    ops = (
        db.query(PlanOperation)
        .join(PlanOrder, PlanOrder.plan_id == PlanOperation.plan_id)
        .filter(PlanOperation.scenario_id == scenario_id)
        .order_by(PlanOperation.planned_start_dt.asc(), PlanOperation.sequence.asc(), PlanOperation.plan_op_id.asc())
        .all()
    )
    if not ops:
        raise RuntimeError(f"No PlanOperation rows found for scenario_id={scenario_id}")

    filters = workcenter_filters or set()
    matched_ops = [op for op in ops if _operation_matches_workcenters(op, filters)]
    selected_ops = matched_ops or ops
    if filters and not matched_ops:
        logger.warning(
            "workorder/preview: no PlanOperation matched workcenter filters=%s for scenario_id=%s; falling back to all operations",
            sorted(filters),
            scenario_id,
        )

    rows = [_workorder_row_from_operation(db, op, existing_nums=existing_nums) for op in selected_ops]
    if not rows:
        raise RuntimeError(f"No usable workorder rows could be constructed for scenario_id={scenario_id}")
    return rows

logger = get_logger(__name__)

router = APIRouter()


def _date_str(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "date") and not isinstance(value, str):
        return value.date().isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _build_workorder_no(work_date: str | None, plan_op_id: str) -> str:
    date_part = (work_date or datetime.now().date().isoformat()).replace("-", "")
    digits = "".join(ch for ch in str(plan_op_id) if ch.isdigit())[-7:].rjust(7, "0")
    return f"WO-{date_part}-{digits}"


def _workorder_row_from_operation(
    db: Session,
    op: PlanOperation,
    existing_nums: set[int] | None = None,
) -> dict[str, Any]:
    po = op.order
    demand = po.demand if po else None
    item = demand.item if demand else None
    wc = op.workcenter
    operation = op.routing_step
    stock = None
    if item is not None:
        stock = (
            db.query(Stock)
            .filter(Stock.gsystem_item_id.in_([str(item.gsystem_id), item.item_no] if item.gsystem_id is not None else [item.item_no]))
            .order_by(Stock.mod_dt.desc().nullslast(), Stock.reg_dt.desc().nullslast())
            .first()
        )
    plan_start_date = _date_str(getattr(po, "planned_start_date", None))
    plan_date = _date_str(getattr(demand, "plan_date", None)) or plan_start_date
    work_date = _date_str(op.planned_start_dt)
    work_order_date = plan_start_date or work_date
    workcenter_value = getattr(wc, "gsystem_id", None) or getattr(wc, "id", None)
    return {
        "planDate": plan_date,
        "planNo": getattr(demand, "plan_no", None) or op.plan_id,
        "workOrderNo": _gen_workorder_no(work_order_date, existing=existing_nums),
        "workOrderSerl": getattr(op, "sequence", None) or 1,
        "workStatus": getattr(po, "plan_status", None) or "",
        "dailyOrderYn": False,
        "procurementType": "",
        "equipment": "",
        "manager": "",
        "departmentName": "",
        "itemId": getattr(item, "gsystem_id", None) or getattr(item, "id", None),
        "itemNo": getattr(item, "item_no", None) or "",
        "masterPartNo": getattr(item, "master_part_no", None) or getattr(item, "master_part_number", None) or "",
        "itemName": getattr(item, "item_name", None) or "",
        "specification": getattr(item, "spec", None) or "",
        "unit": getattr(stock, "unit_cd", None) or "",
        "planQty": float(getattr(demand, "plan_qty", 0) or 0),
        "dailyOrderQty": 0,
        "finishDate": _date_str(getattr(po, "planned_finish_date", None)) or _date_str(op.planned_end_dt),
        "processName": getattr(operation, "proc_name", None) or op.op_code,
        "procId": getattr(operation, "gsystem_process_id", None) or op.routing_id,
        "workQty": float(getattr(demand, "plan_qty", 0) or 0),
        "progressQty": 0,
        "goodQty": 0,
        "defectQty": 0,
        "workDate": work_date,
        "workOrderDate": work_order_date or datetime.now().date().isoformat(),
        "productionStatus": "",
        "majorCategory": "",
        "middleCategory": "",
        "minorCategory": "",
        "inventoryManager": False,
        "continuousProcessYn": False,
        "continuousProcessOrder": "",
        "workCenter": getattr(wc, "workcenter_name", None) or getattr(wc, "workcenter_no", None) or str(op.workcenter_id),
        "workcenterId": workcenter_value,
        "workcenterNo": getattr(wc, "workcenter_no", None) or "",
        "workcenterName": getattr(wc, "workcenter_name", None) or "",
        "scenarioId": op.scenario_id,
        "planOpId": op.plan_op_id,
        "orderQty": float(getattr(demand, "plan_qty", 0) or 0),
        "status": "A",
        "bizId": settings.WORKORDER_DEFAULT_BIZ_ID,
        "corpId": settings.WORKORDER_DEFAULT_CORP_ID,
        "deptId": settings.WORKORDER_DEFAULT_DEPT_ID,
        "responsibleWorkcenterId": workcenter_value,
        "responsibleWorkcenterNo": getattr(wc, "workcenter_no", None) or "",
    }


def _parse_date(value: Any) -> Any:
    if not value:
        return None
    if hasattr(value, "date") and not isinstance(value, str):
        return value.date()
    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError:
        return None


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _get_or_create_workorder_for_operation(
    db: Session,
    op: PlanOperation,
    existing_nums: set[int] | None = None,
) -> tuple[dict[str, Any], bool]:
    existing = (
        db.query(WorkOrder)
        .filter(
            WorkOrder.scenario_id == op.scenario_id,
            WorkOrder.plan_op_id == op.plan_op_id,
        )
        .first()
    )
    if existing is not None:
        return _workorder_row_from_persisted(db, existing), False

    row = _workorder_row_from_operation(db, op, existing_nums=existing_nums)
    record = WorkOrder(
        scenario_id=op.scenario_id,
        plan_op_id=op.plan_op_id,
        plan_id=op.plan_id,
        plan_no=row.get("planNo"),
        work_order_no=row["workOrderNo"],
        work_order_serl=int(row.get("workOrderSerl") or 1),
        work_order_date=_parse_date(row.get("workOrderDate")),
        work_date=_parse_date(row.get("workDate")),
        item_id=int(row["itemId"]) if row.get("itemId") is not None else None,
        item_no=row.get("itemNo") or None,
        workcenter_id=int(row["workcenterId"]) if row.get("workcenterId") is not None else None,
        payload_json=row,
    )
    db.add(record)
    return row, True


def _workorder_row_from_persisted(db: Session, work_order: WorkOrder) -> dict[str, Any]:
    op = db.get(PlanOperation, work_order.plan_op_id)
    if op is None:
        row = dict(work_order.payload_json)
    else:
        row = _workorder_row_from_operation(db, op, existing_nums=set())
        row.update(dict(work_order.payload_json or {}))

    row["workOrderNo"] = work_order.work_order_no
    row["workOrderSerl"] = work_order.work_order_serl
    row["workOrderDate"] = _date_str(work_order.work_order_date) or row.get("workOrderDate")
    row["workDate"] = _date_str(work_order.work_date) or row.get("workDate")
    row["scenarioId"] = work_order.scenario_id
    row["planOpId"] = work_order.plan_op_id
    return row


def _resolve_plan_operation_for_workorder_payload(
    db: Session,
    scenario_id: str,
    rec: dict[str, Any],
) -> PlanOperation | None:
    raw_plan_op_id = str(rec.get("planOpId") or rec.get("plan_op_id") or "").strip()
    if raw_plan_op_id:
        op = (
            db.query(PlanOperation)
            .filter(PlanOperation.scenario_id == scenario_id, PlanOperation.plan_op_id == raw_plan_op_id)
            .first()
        )
        if op is not None:
            return op

    plan_no = str(rec.get("planNo") or "").strip()
    if not plan_no:
        return None

    candidates = (
        db.query(PlanOperation)
        .join(PlanOrder, PlanOrder.plan_id == PlanOperation.plan_id)
        .outerjoin(Demand, Demand.id == PlanOrder.demand_id)
        .filter(
            PlanOperation.scenario_id == scenario_id,
            or_(PlanOrder.plan_id == plan_no, Demand.plan_no == plan_no),
        )
        .order_by(PlanOperation.sequence.asc(), PlanOperation.planned_start_dt.asc(), PlanOperation.plan_op_id.asc())
        .all()
    )
    if not candidates:
        return None

    wanted_sequence = _int_or_none(rec.get("workOrderSerl"))
    wanted_work_date = _parse_date(rec.get("workDate"))
    wanted_process = str(rec.get("processName") or "").strip()

    def score(op: PlanOperation) -> int:
        points = 0
        if wanted_sequence is not None and op.sequence == wanted_sequence:
            points += 4
        if wanted_work_date is not None and getattr(op.planned_start_dt, "date", lambda: None)() == wanted_work_date:
            points += 2
        op_process = str(getattr(op.routing_step, "proc_name", None) or op.op_code or "").strip()
        if wanted_process and op_process == wanted_process:
            points += 1
        return points

    return max(candidates, key=score)


def _upsert_workorder_from_payload(db: Session, scenario_id: str | None, rec: dict[str, Any]) -> None:
    sid = str(scenario_id or rec.get("scenarioId") or rec.get("scenario_id") or "").strip()
    if not sid:
        return

    op = _resolve_plan_operation_for_workorder_payload(db, sid, rec)
    if op is None:
        logger.warning(
            "workorder/save: skip local work_order upsert; cannot resolve PlanOperation for scenario_id=%s planOpId=%s planNo=%s",
            sid,
            rec.get("planOpId") or rec.get("plan_op_id"),
            rec.get("planNo"),
        )
        return

    existing = (
        db.query(WorkOrder)
        .filter(WorkOrder.scenario_id == sid, WorkOrder.plan_op_id == op.plan_op_id)
        .first()
    )
    item_id = _int_or_none(rec.get("itemId"))
    workcenter_id = _int_or_none(rec.get("responsibleWorkcenterId") or rec.get("workcenterId"))
    local_payload = {**rec, "scenarioId": sid, "planOpId": op.plan_op_id}
    if existing is None:
        db.add(
            WorkOrder(
                scenario_id=sid,
                plan_op_id=op.plan_op_id,
                plan_id=op.plan_id,
                plan_no=rec.get("planNo"),
                work_order_no=str(rec.get("workOrderNo") or _gen_workorder_no(rec.get("workOrderDate") or rec.get("planDate"))),
                work_order_serl=int(rec.get("workOrderSerl") or 1),
                work_order_date=_parse_date(rec.get("workOrderDate")),
                work_date=_parse_date(rec.get("workDate")),
                item_id=item_id,
                item_no=rec.get("itemNo") or rec.get("itemNm"),
                workcenter_id=workcenter_id,
                payload_json=local_payload,
            )
        )
        return

    existing.plan_no = rec.get("planNo") or existing.plan_no
    existing.work_order_no = str(rec.get("workOrderNo") or existing.work_order_no)
    existing.work_order_serl = int(rec.get("workOrderSerl") or existing.work_order_serl or 1)
    existing.work_order_date = _parse_date(rec.get("workOrderDate"))
    existing.work_date = _parse_date(rec.get("workDate"))
    existing.item_id = item_id
    existing.item_no = rec.get("itemNo") or rec.get("itemNm") or existing.item_no
    existing.workcenter_id = workcenter_id
    existing.payload_json = local_payload


@router.post("/preview")
async def preview_workorder(
    req: Request,
    db: Session = Depends(get_db),
    scenario_id: str | None = Query(None, description="Scenario id to preview"),
) -> Any:
    used_workorder_nums: set[int] = set()
    try:
        payload = await req.json()
    except Exception:
        payload = {}

    sid = scenario_id or (payload.get("scenario_id") if isinstance(payload, dict) else None)
    if not sid or not str(sid).strip():
        raise HTTPException(status_code=400, detail="scenario_id is required")

    workcenter_filters = _extract_workcenter_filters(payload)
    try:
        items = _build_preview_from_scenario(
            db,
            str(sid).strip(),
            existing_nums=used_workorder_nums,
            workcenter_filters=workcenter_filters,
        )
    except Exception as exc:
        logger.exception("workorder: failed to preview payload from scenario %s", sid)
        raise HTTPException(status_code=500, detail=f"Failed to preview workorder payload: {exc}")

    return {
        "scenario_id": str(sid).strip(),
        "count": len(items),
        "items": items,
    }


@router.get("/list")
def list_workorders(
    db: Session = Depends(get_db),
    scenario_id: str | None = Query(None),
    plan_no: str | None = Query(None),
    work_order_no: str | None = Query(None),
    item_no: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
) -> dict[str, Any]:
    if not scenario_id:
        return {"items": []}

    q = db.query(WorkOrder).filter(WorkOrder.scenario_id == scenario_id)
    if plan_no:
        q = q.filter(or_(WorkOrder.plan_no.ilike(f"%{plan_no}%"), WorkOrder.plan_id.ilike(f"%{plan_no}%")))
    if work_order_no:
        q = q.filter(WorkOrder.work_order_no.ilike(f"%{work_order_no}%"))
    if item_no:
        q = q.filter(WorkOrder.item_no.ilike(f"%{item_no}%"))
    if start_date:
        q = q.filter(WorkOrder.work_date >= datetime.fromisoformat(start_date).date())
    if end_date:
        q = q.filter(WorkOrder.work_date <= datetime.fromisoformat(end_date).date())

    rows = [
        _workorder_row_from_persisted(db, row)
        for row in q.order_by(WorkOrder.work_date.asc(), WorkOrder.id.asc()).limit(500).all()
    ]
    return {"items": rows}


def _gen_workorder_no(work_order_date: str | None = None, existing: set[int] | None = None) -> str:
    """Generate WO-YYYYMMDD-<n> where n is random 1..99999999 and not in `existing`.

    `work_order_date` expects ISO date string 'YYYY-MM-DD' or None (uses today).
    """
    if existing is None:
        existing = set()
    # derive date part
    if work_order_date:
        try:
            d = datetime.fromisoformat(work_order_date)
            date_part = d.strftime("%Y%m%d")
        except Exception:
            # fallback if not strict ISO
            date_part = work_order_date.replace('-', '')
    else:
        date_part = datetime.now().strftime("%Y%m%d")

    # pick random non-colliding integer
    for _ in range(10):
        n = random.randint(1, 99999999)
        if n not in existing:
            existing.add(n)
            return f"WO-{date_part}-{n}"
    # fallback loop (unlikely)
    n = 1
    while n in existing:
        n += 1
    existing.add(n)
    return f"WO-{date_part}-{n}"


@router.post("/save")
async def send_workorder(
    req: Request,
    db: Session = Depends(get_db),
    scenario_id: str | None = Query(None, description="Scenario id to scope lookups"),
) -> Any:
    """Receive workorder(s), normalize, and forward to G-System.

    Accepts either a single object or an array. Returns G-System JSON response.
    """
    # track generated workOrderNo integers to avoid collisions in this request
    used_workorder_nums: set[int] = set()
    workcenter_filters: set[str] = set()
    try:
        payload = await req.json()
        workcenter_filters = _extract_workcenter_filters(payload)
    except Exception as exc:
        logger.debug("workorder: failed to parse JSON body", exc_info=True)
        # If parsing failed but scenario_id provided, build payload from DB records
        if scenario_id:
            try:
                payload = _build_payload_from_scenario(
                    db,
                    scenario_id,
                    existing_nums=used_workorder_nums,
                    workcenter_filters=workcenter_filters,
                )
            except Exception as e:
                logger.exception("workorder: failed to build payload from scenario %s", scenario_id)
                raise HTTPException(status_code=500, detail=f"Failed to build payload from scenario: {e}")
        else:
            raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}")

    if isinstance(payload, dict) and not payload.get("planDate") and scenario_id:
        try:
            payload = _build_payload_from_scenario(
                db,
                scenario_id,
                existing_nums=used_workorder_nums,
                workcenter_filters=workcenter_filters,
            )
        except Exception as e:
            logger.exception("workorder: failed to build payload from scenario %s", scenario_id)
            raise HTTPException(status_code=500, detail=f"Failed to build payload from scenario: {e}")

    # Normalize to list
    if isinstance(payload, dict):
        records = [payload]
    else:
        records = list(payload)

    prepared: list[dict] = []
    local_records: list[dict] = []
    for rec in records:
        if not isinstance(rec, dict):
            raise HTTPException(status_code=400, detail="Each workorder must be an object")

        # Required basics
        plan_date = rec.get("planDate")
        plan_no = rec.get("planNo")
        order_qty = rec.get("orderQty") or rec.get("qty")
        if not plan_date or not plan_no or order_qty is None:
            raise HTTPException(status_code=400, detail="Missing required fields: planDate, planNo, orderQty")

        # Resolve item mapping using DB (prefer direct match; fallback to scenario-scoped PlanOrder -> Demand)
        item_gsid = rec.get("itemId")
        item_no = rec.get("itemId")
        item_nm = rec.get("itemNm")

        item_rec = None
        try:
            if item_gsid is not None:
                item_rec = db.query(Item).filter(Item.gsystem_id == int(item_gsid)).first()
                if item_rec is None:
                    # try by local id
                    item_rec = db.get(Item, int(item_gsid))
            # If still not found and scenario_id provided, try to resolve via PlanOrder -> Demand
            if item_rec is None and scenario_id and plan_no:
                po = db.get(PlanOrder, plan_no)
                if po and po.scenario_id == scenario_id and po.demand_id:
                    d = db.get(Demand, po.demand_id)
                    if d:
                        item_rec = db.get(Item, d.item_id)
            if item_rec is None and item_no:
                item_rec = db.query(Item).filter(Item.item_no == str(item_no)).first()
        except Exception:
            item_rec = None

        # defaults from settings / env
        biz_id = int(rec.get("bizId", settings.WORKORDER_DEFAULT_BIZ_ID))
        corp_id = int(rec.get("corpId", settings.WORKORDER_DEFAULT_CORP_ID))

        work_order_no = rec.get("workOrderNo") or _gen_workorder_no(rec.get("workOrderDate") or plan_date, existing=used_workorder_nums)
        work_order_serl = int(rec.get("workOrderSerl", 1))

        out: dict = {
            "planDate": plan_date,
            "planNo": plan_no,
            "orderQty": float(order_qty),
            "status": rec.get("status", "A"),
            "workDate": rec.get("workDate") or plan_date,
            "workOrderDate": rec.get("workOrderDate") or plan_date,
            "workOrderNo": work_order_no,
            "workOrderSerl": work_order_serl,
            "bizId": biz_id,
            "corpId": corp_id,
        }

        # include process/units/statusCd if present
        for fld in ("itemId", "procId", "statusCd", "stkUnitCd", "stockYn", "cntuProcYn"):
            if rec.get(fld) is not None:
                out[fld] = rec.get(fld)

        # Ensure env defaults are present when not provided
        if out.get("cntuProcYn") is None:
            out["cntuProcYn"] = settings.WORKORDER_DEFAULT_CNTU_PROC_YN
        if out.get("stockYn") is None:
            out["stockYn"] = settings.WORKORDER_DEFAULT_STOCK_YN
        if out.get("deptId") is None:
            out["deptId"] = settings.WORKORDER_DEFAULT_DEPT_ID

        # Optional fields for compatibility with upstream if provided through env/body
        if rec.get("cntuProcOrd") is not None:
            out["cntuProcOrd"] = rec.get("cntuProcOrd")
        elif settings.WORKORDER_DEFAULT_CNTU_PROC_ORD:
            out["cntuProcOrd"] = settings.WORKORDER_DEFAULT_CNTU_PROC_ORD
        if rec.get("delvType") is not None:
            out["delvType"] = rec.get("delvType")
        elif settings.WORKORDER_DEFAULT_DELV_TYPE:
            out["delvType"] = settings.WORKORDER_DEFAULT_DELV_TYPE

        # Item mapping: prefer G-System id; keep itemId/itemNm only as fallback for older data.
        if item_rec is not None and getattr(item_rec, "gsystem_id", None) is not None:
            out["itemId"] = int(item_rec.gsystem_id)
        elif item_rec is not None:
            out["itemId"] = item_rec.id
            out["itemNm"] = item_rec.item_name or item_rec.item_no
        elif item_no:
            out["itemId"] = item_no
            out["itemNm"] = item_nm or item_no
        else:
            raise HTTPException(status_code=400, detail="Item not found and no itemId provided")

        # pass-through optional fields
        for fld in (
            "deptId", "empId", "custNm", "custSeq", "deptNm", "fullNm", "workshopNm",
            "workcenterId", "workcenterNo", "workcenterName",
            "responsibleWorkcenterId", "responsibleWorkcenterNo", "responsibleWorkcenterName",
        ):
            if rec.get(fld) is not None:
                out[fld] = rec.get(fld)

        prepared.append(out)
        local_records.append({**rec, **out})

    # Submit to G-System one record at a time.
    cfg = GSystemConfig(
        base_url=settings.GSYSTEM_BASE_URL.rstrip("/"),
        api_key=settings.GSYSTEM_API_KEY,
        timeout=settings.GSYSTEM_TIMEOUT,
        retries=settings.GSYSTEM_RETRIES,
        all_data=settings.GSYSTEM_ALL_DATA,
    )

    results: list[dict[str, Any]] = []
    try:
        with GSystemClient(cfg) as client:
            for rec, local_rec in zip(prepared, local_records):
                logger.info("Sending single workorder to G-System: workOrderNo=%s planNo=%s", rec.get("workOrderNo"), rec.get("planNo"))
                r = client._http.post("/pd/workorder/aps/save", json=[rec])
                r.raise_for_status()
                resp = r.json()
                results.append({"request": rec, "response": resp})
                _upsert_workorder_from_payload(db, scenario_id, local_rec)
    except Exception as exc:
        logger.exception("Failed to send workorder(s) to G-System")
        db.rollback()
        raise HTTPException(status_code=502, detail=str(exc))

    db.commit()
    if len(results) == 1:
        return results[0]["response"]
    return {
        "sent_count": len(results),
        "results": results,
    }


@router.post("/delete")
async def delete_workorder(req: Request, db: Session = Depends(get_db)) -> Any:
    try:
        payload = await req.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}")

    records = payload if isinstance(payload, list) else payload.get("items", [payload]) if isinstance(payload, dict) else []
    prepared = []
    for rec in records:
        if not isinstance(rec, dict):
            raise HTTPException(status_code=400, detail="Each delete item must be an object")
        work_order_no = rec.get("workOrderNo") or rec.get("work_order_no")
        if not work_order_no:
            raise HTTPException(status_code=400, detail="workOrderNo is required")
        prepared.append({
            "workOrderNo": work_order_no,
            "workOrderSerl": int(rec.get("workOrderSerl") or rec.get("work_order_serl") or 1),
            "bizId": int(rec.get("bizId", settings.WORKORDER_DEFAULT_BIZ_ID)),
            "corpId": int(rec.get("corpId", settings.WORKORDER_DEFAULT_CORP_ID)),
        })

    cfg = GSystemConfig(
        base_url=settings.GSYSTEM_BASE_URL.rstrip("/"),
        api_key=settings.GSYSTEM_API_KEY,
        timeout=settings.GSYSTEM_TIMEOUT,
        retries=settings.GSYSTEM_RETRIES,
        all_data=settings.GSYSTEM_ALL_DATA,
    )

    try:
        with GSystemClient(cfg) as client:
            r = client._http.post("/pd/workorder/aps/delete", json=prepared)
            r.raise_for_status()
            response = r.json()
            for rec in prepared:
                db.query(WorkOrder).filter(
                    WorkOrder.work_order_no == rec["workOrderNo"],
                    WorkOrder.work_order_serl == rec["workOrderSerl"],
                ).delete(synchronize_session=False)
            db.commit()
            return response
    except Exception as exc:
        logger.exception("Failed to delete workorder(s) in G-System")
        db.rollback()
        raise HTTPException(status_code=502, detail=str(exc))

"""G-System API response → APS Local DB syncer.

Protocol (applied to every entity):
  1. Sort records by "id" ASC  (G-System sequential order)
  2. Dispatch by ifStatus:  "A" → INSERT, "U" → UPDATE, "D" → DELETE
  3. Caller must commit(); this module only flushes.

Usage:
    data = client.fetch_all()
    with SessionLocal() as session:
        sync_all(session, data)
        session.commit()
"""

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_logger
from app.models import (
    BOM, Demand, Equipment, Item, ItemProcessStep, ItemRoutingSpec,
    MpsPlan, RoutingStep, Routing, RoutingItem, WorkCenter,
)
from app.models.input.calendar import CalendarEntry
from app.models.input.customer import Customer, CUSTOMER_TYPE_IMPACT
from app.models.input.stock import Stock

logger = get_logger(__name__)

_ASSET_TYPE_MAP: dict[str, str] = {
    "제품":    "Product",
    "반제품":  "SemiProduct",
    "원자재":  "RawMaterial",
    "외주구매품": "RawMaterial",  # outsourced purchased component
    "부품":    "RawMaterial",    # part/component
}
_VALID_ASSET_TYPES = {"Product", "SemiProduct", "RawMaterial"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _minutes_to_hours(minutes: int | float | None) -> float:
    """Convert G-System workTime/setupTime (integer minutes) → decimal hours.

    Example: 1015 min → 16.9167h.  Returns 0.0 for null/zero.
    """
    if not minutes:
        return 0.0
    return round(float(minutes) / 60, 4)


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        logger.warning("Cannot parse date %r — stored as None", value)
        return None


def _parse_datetime(value: Any) -> datetime | None:
    """Parse a G-System datetime value → naive datetime, or None.

    Handles both API formats seen in practice:
      - "2025-03-21 10:41:48"          (naive, space separator — regDt/modDt)
      - "2026-07-17T01:28:37.853+00:00" (ISO 8601 with tz offset — ifRecvDt)
    Tz-aware values are normalized to naive UTC (target columns are
    TIMESTAMP WITHOUT TIME ZONE, matching existing reg_dt/mod_dt convention).
    """
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        logger.warning("Cannot parse datetime %r — stored as None", value)
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _sorted(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort pending records by 'id' ASC (G-System processing order)."""
    return sorted(records, key=lambda r: r.get("id", 0))


# ── Entity syncers ────────────────────────────────────────────────────────────

def sync_items(session: Session, records: list[dict[str, Any]]) -> dict[int, Item]:
    """Upsert/delete items; return {itemId → Item} index for FK lookups."""
    index: dict[int, Item] = {}
    for rec in _sorted(records):
        item_no = rec.get("itemNo")
        item_gsys_id = rec.get("itemId")  # G-System business integer ID
        if not item_no:
            logger.warning("sync_items: missing itemNo — skipped %s", rec.get("id"))
            continue
        # Prefer lookup by gsystem_id (stable PK); fall back to item_no for legacy rows.
        # A rename on G-System side can emit two pending records with the same itemId
        # but different itemNo — matching by item_no alone would create a duplicate row.
        item = (
            session.execute(select(Item).where(Item.gsystem_id == int(item_gsys_id))).scalar_one_or_none()
            if item_gsys_id is not None
            else None
        )
        if item is None:
            item = session.execute(select(Item).where(Item.item_no == str(item_no))).scalar_one_or_none()
        if rec.get("ifStatus") == "D":
            if item:
                session.delete(item)
                session.flush()
            # Drop from index — a later record for this itemId must not resolve
            # to the now-deleted instance (e.g. duplicate pending rows).
            if item_gsys_id is not None:
                index.pop(int(item_gsys_id), None)
            continue
        if item is None:
            item = Item(item_no=str(item_no))
            session.add(item)
        else:
            item.item_no = str(item_no)  # picks up renames when matched via gsystem_id
        item.item_name = rec.get("itemNm")
        item.spec = rec.get("spec")
        raw_type = str(rec.get("assetTypeCdNm", ""))
        mapped = _ASSET_TYPE_MAP.get(raw_type, raw_type)
        item.asset_type = mapped if mapped in _VALID_ASSET_TYPES else "RawMaterial"
        if item_gsys_id is not None:
            item.gsystem_id = int(item_gsys_id)
        session.flush()
        if item_gsys_id is not None:
            index[int(item_gsys_id)] = item
    logger.info("sync_items: %d records, %d indexed", len(records), len(index))
    return index


def sync_workcenters(session: Session, records: list[dict[str, Any]]) -> dict[int, WorkCenter]:
    """Upsert/delete workcenters; return {workshopId → WorkCenter} index."""
    index: dict[int, WorkCenter] = {}
    for rec in _sorted(records):
        gsys_id = rec.get("workshopId")  # G-System business integer ID
        wc_no = rec.get("workshopCd")
        if not wc_no:
            if gsys_id is None:
                logger.warning("sync_workcenters: missing workshopCd and workshopId — skipped %s", rec.get("id"))
                continue
            # G-System hasn't set workshopCd yet — synthesize a stable code from
            # workshopId so the workcenter (and anything referencing it, e.g.
            # aps_item_routing_spec.workcenter_id) still resolves instead of being dropped.
            wc_no = f"WS{gsys_id}"
            logger.warning(
                "sync_workcenters: missing workshopCd for workshopId=%s — using fallback code %s",
                gsys_id, wc_no,
            )
        # Prefer lookup by gsystem_id (stable PK); fall back to workcenter_no for legacy rows
        wc = (
            session.execute(select(WorkCenter).where(WorkCenter.gsystem_id == int(gsys_id))).scalar_one_or_none()
            if gsys_id is not None
            else session.execute(select(WorkCenter).where(WorkCenter.workcenter_no == str(wc_no))).scalar_one_or_none()
        )
        if rec.get("ifStatus") == "D":
            if wc:
                session.delete(wc)
                session.flush()
            # Drop from index — a later record for this workshopId must not
            # resolve to the now-deleted instance (e.g. duplicate pending rows).
            if gsys_id is not None:
                index.pop(int(gsys_id), None)
            continue
        if wc is None:
            wc = WorkCenter(workcenter_no=str(wc_no))
            session.add(wc)
        wc.workcenter_no = str(wc_no)
        wc.gsystem_id = int(gsys_id) if gsys_id is not None else None
        wc.workcenter_name = rec.get("workshopNm")
        # Default operating capacity: 480 min/day (equipment cycle_factor scales it)
        if wc.std_capa is None:
            wc.std_capa = 480
        session.flush()
        if gsys_id is not None:
            index[int(gsys_id)] = wc
    logger.info("sync_workcenters: %d records, %d indexed", len(records), len(index))
    return index


def _to_float(value: Any) -> float | None:
    """Parse a numeric-ish G-System value → float, or None."""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    """Parse a numeric-ish G-System value → int, or None."""
    f = _to_float(value)
    return int(f) if f is not None else None


def sync_equipment_by_workshop(
    session: Session, workcenter: WorkCenter, records: list[dict[str, Any]]
) -> int:
    """Upsert equipment for one workcenter; return rows synced.

    Keyed by G-System record `id` (unique per validity version) → Equipment.gsystem_id.
    Deletes existing equipment for this workcenter that no longer appear in `records`
    so stale/expired versions are pruned. Key field: cycle_factor.
    """
    seen_ids: set[int] = set()
    count = 0
    for rec in _sorted(records):
        rec_id = rec.get("id")
        if rec_id is None:
            logger.warning("sync_equipment: missing id — skipped workshopId=%s", rec.get("workshopId"))
            continue
        gsys_id = int(rec_id)
        seen_ids.add(gsys_id)
        eq = session.execute(
            select(Equipment).where(Equipment.gsystem_id == gsys_id)
        ).scalar_one_or_none()
        if eq is None:
            eq = Equipment(gsystem_id=gsys_id)
            session.add(eq)
        eq.equipment_id = _to_int(rec.get("equipmentId"))
        eq.equipment_name = rec.get("equipmentNm")
        eq.workcenter_id = workcenter.id
        eq.gsystem_workshop_id = _to_int(rec.get("workshopId"))
        eq.cycle_factor = _to_float(rec.get("cycleFactor"))
        eq.normal_capacity_min = _to_int(rec.get("normalCapacityMin"))
        eq.max_capacity_min = _to_int(rec.get("maxCapacityMin"))
        eq.ot_capacity_min = _to_int(rec.get("otCapacityMin"))
        eq.holiday_capacity_min = _to_int(rec.get("holidayCapacityMin"))
        eq.min_lot_qty = _to_float(rec.get("minLotQty"))
        eq.max_lot_qty = _to_float(rec.get("maxLotQty"))
        eq.concurrent_lot_qty = _to_int(rec.get("concurrentLotQty"))
        eq.oee_rate = _to_float(rec.get("oeeRate"))
        eq.efficiency_rate = _to_float(rec.get("efficiencyRate"))
        eq.quality_factor = _to_float(rec.get("qualityFactor"))
        eq.availability_rate = _to_float(rec.get("availabilityRate"))
        eq.assign_rate = _to_float(rec.get("assignRate"))
        eq.priority_order = _to_int(rec.get("priorityOrder"))
        eq.required_skill_level = rec.get("requiredSkillLevel")
        eq.split_allowed = rec.get("splitAllowed")
        eq.valid_from = rec.get("validFrom")
        eq.valid_to = rec.get("validTo")
        session.flush()
        count += 1

    # Prune equipment rows for this workcenter no longer returned by G-System
    stale = session.execute(
        select(Equipment).where(Equipment.workcenter_id == workcenter.id)
    ).scalars().all()
    for eq in stale:
        if eq.gsystem_id not in seen_ids:
            session.delete(eq)
    return count


def sync_mps_plan(session: Session, records: list[dict[str, Any]]) -> int:
    """Upsert MPS plan lines (GET /pd/prodPlanMpsMng); return rows synced.

    Keyed by G-System record `id`. item_id/routing_id FKs resolved by gsystem_id —
    left null when the referenced item/routing isn't in APS yet (both are optional
    on MpsPlan so orphaned MPS lines still get stored for visibility).
    """
    if not records:
        return 0

    item_ids = {int(r["itemId"]) for r in records if r.get("itemId") is not None}
    routing_ids = {int(r["routingId"]) for r in records if r.get("routingId") is not None}
    item_by_gsys: dict[int, Item] = {
        i.gsystem_id: i
        for i in session.execute(select(Item).where(Item.gsystem_id.in_(item_ids))).scalars().all()
        if i.gsystem_id is not None
    } if item_ids else {}
    routing_by_gsys: dict[int, Routing] = {
        r.gsystem_id: r
        for r in session.execute(select(Routing).where(Routing.gsystem_id.in_(routing_ids))).scalars().all()
        if r.gsystem_id is not None
    } if routing_ids else {}

    count = 0
    for rec in _sorted(records):
        rec_id = rec.get("id")
        if rec_id is None:
            logger.warning("sync_mps_plan: missing id — skipped planNo=%s", rec.get("planNo"))
            continue
        gsys_id = int(rec_id)
        plan = session.execute(select(MpsPlan).where(MpsPlan.gsystem_id == gsys_id)).scalar_one_or_none()
        if plan is None:
            plan = MpsPlan(gsystem_id=gsys_id)
            session.add(plan)

        plan.plan_no = rec.get("planNo")
        plan.dmd_no = rec.get("dmdNo")
        gsys_item_id = _to_int(rec.get("itemId"))
        plan.gsystem_item_id = gsys_item_id
        plan.item_rev = _to_int(rec.get("itemRev"))
        plan.item_id = item_by_gsys[gsys_item_id].id if gsys_item_id in item_by_gsys else None
        gsys_routing_id = _to_int(rec.get("routingId"))
        plan.gsystem_routing_id = gsys_routing_id
        plan.routing_id = routing_by_gsys[gsys_routing_id].id if gsys_routing_id in routing_by_gsys else None
        plan.parea_id = _to_int(rec.get("pareaId"))
        plan.plan_qty = _to_float(rec.get("planQty"))
        plan.order_qty = _to_float(rec.get("orderQty"))
        plan.plan_date = _parse_date(rec.get("planDate"))
        plan.plan_start_date = _parse_date(rec.get("planStartDate"))
        plan.plan_end_date = _parse_date(rec.get("planEndDate"))
        plan.delivery_date = _parse_date(rec.get("delvDate"))
        plan.prod_end_date = _parse_date(rec.get("prodEndDate"))
        plan.status_cd = rec.get("statusCd")
        plan.plan_gbn = rec.get("planGbn")
        plan.bom_yn = rec.get("bomYn")
        plan.mrp_calc_yn = rec.get("mrpCalcYn")
        plan.from_work_plan_yn = rec.get("fromWorkPlanYn")
        plan.wbs_id = rec.get("wbsId")
        plan.wbs_dtl = rec.get("wbsDtl")
        plan.project_no = rec.get("projectNo")
        plan.project_nm = rec.get("projectNm")
        plan.po_no = rec.get("poNo")
        session.flush()
        count += 1
    logger.info("sync_mps_plan: %d records synced", count)
    return count


def sync_item_routing(
    session: Session, item: Item, records: list[dict[str, Any]]
) -> int:
    """Upsert 품목별라우팅입력 rows for one item; return rows synced.

    Keyed by G-System record `id` (one row per proc step / procSno).
    jph (EA/HR) is derived from workTime (seconds/EA): jph = 3600 / workTime.
    """
    if not records:
        return 0

    routing_ids = {int(r["routingId"]) for r in records if r.get("routingId") is not None}
    routing_by_gsys: dict[int, Routing] = {
        r.gsystem_id: r
        for r in session.execute(select(Routing).where(Routing.gsystem_id.in_(routing_ids))).scalars().all()
        if r.gsystem_id is not None
    } if routing_ids else {}

    wc_ids = {int(r["oscustId"]) for r in records if r.get("oscustId") is not None}
    wc_by_gsys: dict[int, WorkCenter] = {
        w.gsystem_id: w
        for w in session.execute(select(WorkCenter).where(WorkCenter.gsystem_id.in_(wc_ids))).scalars().all()
        if w.gsystem_id is not None
    } if wc_ids else {}

    count = 0
    for rec in _sorted(records):
        rec_id = rec.get("id")
        if rec_id is None:
            logger.warning("sync_item_routing: missing id — skipped item_id=%s", item.id)
            continue
        gsys_id = int(rec_id)
        ir = session.execute(select(ItemRoutingSpec).where(ItemRoutingSpec.gsystem_id == gsys_id)).scalar_one_or_none()
        if ir is None:
            ir = ItemRoutingSpec(gsystem_id=gsys_id)
            session.add(ir)

        ir.item_id = item.id
        gsys_routing_id = _to_int(rec.get("routingId"))
        ir.gsystem_routing_id = gsys_routing_id
        ir.routing_id = routing_by_gsys[gsys_routing_id].id if gsys_routing_id in routing_by_gsys else None
        # G-System names this field "oscustId" (not "workcenterId") in the
        # itemRoutingMng response — verified against live API response.
        gsys_wc_id = _to_int(rec.get("oscustId"))
        ir.gsystem_workcenter_id = gsys_wc_id
        ir.workcenter_id = wc_by_gsys[gsys_wc_id].id if gsys_wc_id in wc_by_gsys else None
        ir.routing_no = rec.get("routingNo")
        ir.routing_name = rec.get("routingNm")
        ir.gsystem_proc_id = _to_int(rec.get("procId"))
        ir.proc_sno = _to_int(rec.get("procSno"))
        ir.proc_name = rec.get("procNm")
        ir.making_gb = rec.get("makingGb")
        ir.lead_time = _to_float(rec.get("leadTime"))
        work_time = _to_float(rec.get("workTime"))
        ir.work_time = work_time
        ir.jph = round(3600.0 / work_time, 2) if work_time else None
        ir.inspec_type = rec.get("inspecType")
        ir.inspection_yn = rec.get("inspectionYn")
        ir.work_ins_yn = rec.get("workInsYn")
        ir.sample_qty = _to_float(rec.get("sampleQty"))
        ir.stock_yn = rec.get("stockYn")
        session.flush()
        count += 1
    logger.info("sync_item_routing: item_id=%s %d records synced", item.id, count)
    return count


def sync_processes(records: list[dict[str, Any]]) -> dict[int, str]:
    """Build in-memory {processId → procNm} index. No DB writes — process master is index-only."""
    index: dict[int, str] = {}
    for rec in records:
        pid = rec.get("processId")
        name = rec.get("procNm")
        if pid is not None:
            index[int(pid)] = str(name or "")
    logger.info("sync_processes: %d in proc_index", len(index))
    return index


def sync_routings(session: Session, records: list[dict[str, Any]]) -> dict[int, Routing]:
    """Upsert/delete routings; return {routingId → Routing} index."""
    index: dict[int, Routing] = {}
    for rec in _sorted(records):
        gsys_id = rec.get("routingId")  # G-System business integer ID
        if gsys_id is None:
            logger.warning("sync_routings: missing routingId — skipped %s", rec.get("id"))
            continue
        routing = session.execute(select(Routing).where(Routing.gsystem_id == int(gsys_id))).scalar_one_or_none()
        if rec.get("ifStatus") == "D":
            if routing:
                session.delete(routing)
                session.flush()
            # Drop from index too — a later record for this routingId must not
            # resolve to the now-deleted instance (e.g. duplicate pending rows).
            index.pop(int(gsys_id), None)
            continue
        if routing is None:
            routing = Routing(gsystem_id=int(gsys_id))
            session.add(routing)
        routing.routing_no = rec.get("routingNo")
        routing.routing_name = rec.get("routingNm")
        routing.routing_type_cd = rec.get("routingTypeCd")
        routing.std_capa = float(rec.get("stdCapa") or 0)
        session.flush()
        index[int(gsys_id)] = routing
    logger.info("sync_routings: %d records, %d indexed", len(records), len(index))
    return index


def sync_routing_items(
    session: Session,
    records: list[dict[str, Any]],
    item_index: dict[int, Item],
    routing_index: dict[int, Routing],
) -> None:
    """Sync routing ↔ item links from routing_item endpoint records."""
    count = 0
    for rec in _sorted(records):
        r_id = rec.get("routingId")
        i_id = rec.get("itemId")
        if r_id is None or i_id is None:
            continue
        routing = routing_index.get(int(r_id))
        item = item_index.get(int(i_id))
        if routing is None or item is None:
            continue
        if rec.get("ifStatus") == "D":
            link = session.execute(select(RoutingItem).where(RoutingItem.routing_id == routing.id, RoutingItem.item_id == item.id)).scalar_one_or_none()
            if link:
                session.delete(link)
            continue
        exists = session.execute(select(RoutingItem).where(RoutingItem.routing_id == routing.id, RoutingItem.item_id == item.id)).scalar_one_or_none()
        if not exists:
            session.add(RoutingItem(routing=routing, item=item))
            count += 1
    logger.info("sync_routing_items: %d new links", count)


def sync_routing_processes(
    session: Session,
    records: list[dict[str, Any]],
    routing_index: dict[int, Routing],
    wc_index: dict[int, WorkCenter],
    proc_index: dict[int, str],
) -> None:
    """Upsert/delete operations from routing_process endpoint.

    workTime / setupTime are integer minutes — converted via _minutes_to_hours.
    proc_name resolved from proc_index keyed by processId.
    """
    count = 0
    for rec in _sorted(records):
        r_id = rec.get("routingId")
        seq = rec.get("processSeq")
        if r_id is None or seq is None:
            continue
        routing = routing_index.get(int(r_id))
        if routing is None:
            continue
        op = session.execute(select(RoutingStep).where(RoutingStep.routing_id == routing.id, RoutingStep.process_seq == int(seq))).scalar_one_or_none()
        if rec.get("ifStatus") == "D":
            if op:
                session.delete(op)
            continue
        if op is None:
            op = RoutingStep(routing=routing, process_seq=int(seq))
            session.add(op)
        proc_id = rec.get("processId")
        wc_id = rec.get("workcenterId")
        op.gsystem_process_id = int(proc_id) if proc_id is not None else None
        op.proc_name = proc_index.get(int(proc_id), "") if proc_id is not None else None
        op.workcenter = wc_index.get(int(wc_id)) if wc_id is not None else None
        op.work_time_hours = _minutes_to_hours(rec.get("workTime"))
        op.setup_time_hours = _minutes_to_hours(rec.get("setupTime"))
        session.flush()
        count += 1
    logger.info("sync_routing_processes: %d operations upserted", count)


def sync_bom(
    session: Session,
    records: list[dict[str, Any]],
    item_index: dict[int, Item],
) -> None:
    """Upsert/delete merged BOM rows (one row per parent/component pair).

    G-System fields: upitemId (lowercase i), downitemId, qty1, qty2, bomSort,
    plus the full informational field set (id, bomId, upitemNo, downitemNo,
    bomLevel, sdate, edate, delvType, delvTypeNm, revNo, ifRecvYn, ifRecvDt,
    regDt, regUserId, modDt, modUserId, corpId, bizId, ifStatus).
    """
    count = 0
    for rec in _sorted(records):
        parent_id = rec.get("upitemId")    # lowercase 'i'
        child_id = rec.get("downitemId")   # lowercase 'i'
        if parent_id is None or child_id is None:
            continue
        parent = item_index.get(int(parent_id))
        child = item_index.get(int(child_id))
        if parent is None or child is None:
            logger.debug("sync_bom: parent=%s child=%s not found", parent_id, child_id)
            continue
        row = session.execute(
            select(BOM).where(BOM.parent_item_id == parent.id, BOM.component_item_id == child.id)
        ).scalar_one_or_none()
        if rec.get("ifStatus") == "D":
            if row:
                session.delete(row)
                session.flush()
            continue
        if row is None:
            row = BOM(parent_item=parent, component_item=child)
            session.add(row)
        qty2 = rec.get("qty2")
        row.qty1 = float(rec.get("qty1") or 1)
        row.qty2 = float(qty2) if qty2 is not None else None
        row.bom_seq = rec.get("bomSort")
        row.gsystem_if_id = rec.get("id")
        row.gsystem_bom_id = rec.get("bomId")
        row.parent_item_no = rec.get("upitemNo")
        row.component_item_no = rec.get("downitemNo")
        row.bom_level = rec.get("bomLevel")
        row.start_date = rec.get("sdate")
        row.end_date = rec.get("edate")
        row.delivery_type = rec.get("delvType")
        row.delivery_type_name = rec.get("delvTypeNm")
        row.rev_no = rec.get("revNo")
        row.if_recv_yn = rec.get("ifRecvYn")
        row.if_recv_dt = _parse_datetime(rec.get("ifRecvDt"))
        row.reg_dt = _parse_datetime(rec.get("regDt"))
        row.reg_user_id = rec.get("regUserId")
        row.mod_dt = _parse_datetime(rec.get("modDt"))
        row.mod_user_id = rec.get("modUserId")
        row.corp_id = rec.get("corpId")
        row.biz_id = rec.get("bizId")
        row.if_status = rec.get("ifStatus")
        session.flush()
        count += 1
    logger.info("sync_bom: %d rows upserted", count)


def sync_demands(
    session: Session,
    records: list[dict[str, Any]],
    item_index: dict[int, Item],
    customer_index: dict[str, Customer] | None = None,
) -> None:
    """Upsert/delete production demand records.

    G-System field delvDate (not deliveryDate).
    customer_index: {customerNo → Customer} — if provided, links demand.customer_id for impact scoring.
    """
    count = 0
    for rec in _sorted(records):
        plan_no = rec.get("planNo")
        if not plan_no:
            continue
        demand = session.execute(select(Demand).where(Demand.plan_no == str(plan_no))).scalar_one_or_none()
        if rec.get("ifStatus") == "D":
            if demand:
                session.delete(demand)
            continue
        item_id = rec.get("itemId")
        item = item_index.get(int(item_id)) if item_id is not None else None
        if item is None:
            logger.warning("sync_demands: planNo=%s item %s not found", plan_no, item_id)
            continue
        if demand is None:
            demand = Demand(plan_no=str(plan_no), item=item, data_source="gsystem")
            session.add(demand)
        demand.item = item
        demand.data_source = "gsystem"
        demand.plan_qty = float(rec.get("planQty") or 0)
        demand.plan_date = _parse_date(rec.get("planDate"))
        demand.delivery_date = _parse_date(rec.get("delvDate"))   # delvDate (not deliveryDate)
        demand.status_cd = rec.get("statusCd")
        # Link customer for impact scoring — customerNo field from G-System prod_plan
        if customer_index is not None:
            customer_no = rec.get("customerNo")
            demand.customer = customer_index.get(str(customer_no)) if customer_no else None
        session.flush()
        count += 1
    logger.info("sync_demands: %d records upserted", count)


def sync_item_processes(
    session: Session,
    records: list[dict[str, Any]],
    item_index: dict[int, Item],
) -> None:
    """Upsert/delete item process records from pending endpoint.

    Upsert key: (routing_id=None, item_id, proc_sno) — pending records have no routing context.
    """
    count = 0
    for rec in _sorted(records):
        item_id = rec.get("itemId")
        proc_sno = rec.get("procSno")
        if item_id is None or proc_sno is None:
            continue
        item = item_index.get(int(item_id))
        if item is None:
            logger.debug("sync_item_processes: item %s not found", item_id)
            continue
        # Pending records have no routing context — match on (routing_id=null, item_id, proc_sno)
        ip = session.execute(
            select(ItemProcessStep).where(
                ItemProcessStep.routing_id.is_(None), ItemProcessStep.item_id == item.id, ItemProcessStep.proc_sno == int(proc_sno)
            )
        ).scalar_one_or_none()
        if rec.get("ifStatus") == "D":
            if ip:
                session.delete(ip)
            continue
        if ip is None:
            ip = ItemProcessStep(item=item, proc_sno=int(proc_sno), routing_id=None)
            session.add(ip)
        ip.gsystem_proc_id = int(rec["procId"]) if rec.get("procId") is not None else None
        ip.making_gb = rec.get("makingGb")
        ip.inspection_yn = rec.get("inspectionYn")
        ip.work_ins_yn = rec.get("workInsYn")
        ip.stock_yn = rec.get("stockYn")
        ip.rev_no = rec.get("revNo")
        # workTime (minutes) is present in some pending records — convert to hours
        if rec.get("workTime") is not None:
            ip.work_time_hours = _minutes_to_hours(rec.get("workTime"))
        session.flush()
        count += 1
    logger.info("sync_item_processes: %d records upserted", count)


def sync_item_processes_by_routing(
    session: Session,
    routing: "Routing",
    records: list[dict[str, Any]],
    item_index: dict[int, Item],
) -> int:
    """Upsert item process steps fetched from itemProcessListByRouting.

    Upsert key: (routing_id, item_id, proc_sno).
    Populates work_time_hours (minutes → hours) — not available from pending endpoint.
    Returns count of upserted rows.
    """
    count = 0
    for rec in records:
        item_gsys_id = rec.get("itemId")
        proc_sno = rec.get("procSno")
        if item_gsys_id is None or proc_sno is None:
            continue
        item = item_index.get(int(item_gsys_id))
        if item is None:
            logger.debug("sync_item_processes_by_routing: item %s not found in index", item_gsys_id)
            continue
        ip = session.execute(
            select(ItemProcessStep).where(
                ItemProcessStep.routing_id == routing.id, ItemProcessStep.item_id == item.id, ItemProcessStep.proc_sno == int(proc_sno)
            )
        ).scalar_one_or_none()
        if ip is None:
            ip = ItemProcessStep(routing=routing, item=item, proc_sno=int(proc_sno))
            session.add(ip)
        ip.gsystem_proc_id = int(rec["procId"]) if rec.get("procId") is not None else None
        ip.making_gb = rec.get("makingGb")
        ip.rev_no = rec.get("revNo")
        ip.work_time_hours = _minutes_to_hours(rec.get("workTime"))
        session.flush()
        count += 1
    return count


# G-System customerGb / customerGbCd → APS customer_type mapping.
# Assumed codes based on G-System convention — adjust if actual values differ.
_CUSTOMER_TYPE_MAP: dict[str, str] = {
    "internal":  "internal",
    "small":     "small",
    "normal":    "normal",
    "important": "important",
    "vip":       "vip",
    # Korean equivalents (common G-System codeset)
    "내부":   "internal",
    "소규모": "small",
    "일반":   "normal",
    "중요":   "important",
    "vip":    "vip",
}


def sync_customers(session: Session, records: list[dict[str, Any]]) -> dict[str, Customer]:
    """Upsert/delete customers; return {custId(str) → Customer} index.

    G-System fields: custId (int PK), custNm (name), custType (code e.g. '10451001').
    custType codes are not yet mapped to APS types — all default to 'normal' until
    G-System confirms the code → type mapping.
    """
    index: dict[str, Customer] = {}
    count = 0
    for rec in _sorted(records):
        cust_id = rec.get("custId")
        if cust_id is None:
            logger.warning("sync_customers: missing custId — skipped")
            continue
        customer_no = str(cust_id)
        customer = session.execute(select(Customer).where(Customer.customer_no == customer_no)).scalar_one_or_none()
        if rec.get("ifStatus") == "D":
            if customer:
                session.delete(customer)
            continue
        if customer is None:
            customer = Customer(customer_no=customer_no)
            session.add(customer)

        # custType is a G-System code — map via _CUSTOMER_TYPE_MAP or default to normal
        raw_type = str(rec.get("custType") or "").lower()
        customer_type = _CUSTOMER_TYPE_MAP.get(raw_type, "normal")
        customer.customer_name = str(rec.get("custNm") or rec.get("custFullNm") or customer_no)
        customer.customer_type = customer_type
        customer.impact_score  = CUSTOMER_TYPE_IMPACT[customer_type]
        session.flush()
        index[customer_no] = customer
        count += 1
    logger.info("sync_customers: %d records upserted", count)
    return index


def sync_calendar(session: Session, records: list[dict[str, Any]]) -> int:
    """Upsert/delete calendar entries from G-System API response.

    Expected API fields: workDate (YYYYMMDD), dayOfWeek, workGb, holidayYn, workTime (hours).
    """
    count = 0
    for rec in records:
        work_date_str = rec.get("workDate")
        if not work_date_str:
            logger.warning("sync_calendar: missing workDate — skipped")
            continue
        try:
            s = str(work_date_str)
            # Support both YYYYMMDD and YYYY-MM-DD formats
            fmt = "%Y-%m-%d" if "-" in s else "%Y%m%d"
            work_date = datetime.strptime(s, fmt).date()
        except ValueError:
            logger.warning("sync_calendar: cannot parse workDate %r — skipped", work_date_str)
            continue

        entry = session.get(CalendarEntry, work_date)
        if rec.get("ifStatus") == "D":
            if entry:
                session.delete(entry)
            continue
        if entry is None:
            entry = CalendarEntry(work_date=work_date)
            session.add(entry)

        entry.day_of_week_cd = rec.get("dayOfWeek")
        entry.work_gb_cd     = rec.get("workGb")
        entry.is_holiday     = str(rec.get("holidayYn", "N")).upper() == "Y"
        entry.work_hours     = float(rec.get("workTime") or 0)
        session.flush()  # flush per-row so duplicate workDate lookups hit identity map
        count += 1

    logger.info("sync_calendar: %d entries upserted", count)
    return count


def sync_stock(session: Session, records: list[dict[str, Any]]) -> int:
    """Upsert/delete stock rows from G-System API response.

    Expected API fields match lg_stock column names (snake_case).
    Key scheduling field: able_qty.
    """
    _STOCK_FIELDS = (
        "corp_id", "parea_id", "biz_id", "stk_ym", "stk_type",
        "wh_cd", "location_id", "item_id", "unit_cd", "lotno",
        "prev_qty", "prev_price", "prev_amt",
        "in_qty", "out_qty", "able_qty",
        "buy_qty", "buy_amt", "make_qty", "make_amt",
        "etc_in_qty", "etc_in_amt", "mv_in_qty", "mv_in_amt",
        "invoice_qty", "invoice_amt", "mat_qty", "mat_amt",
        "mv_out_qty", "mv_out_amt", "etc_out_qty", "etc_out_amt",
        "reg_user_id", "reg_dt", "reg_ip",
        "mod_user_id", "mod_dt", "mod_ip",
    )
    count = 0
    for rec in records:
        stock_id = rec.get("id")
        if stock_id is None:
            logger.warning("sync_stock: missing id — skipped")
            continue

        entry = session.get(Stock, int(stock_id))
        if rec.get("ifStatus") == "D":
            if entry:
                session.delete(entry)
            continue
        if entry is None:
            entry = Stock(id=int(stock_id))
            session.add(entry)

        for field in _STOCK_FIELDS:
            val = rec.get(field)
            setattr(entry, field, val)
        count += 1

    session.flush()
    logger.info("sync_stock: %d rows upserted", count)
    return count


# ── Entry point ───────────────────────────────────────────────────────────────

def sync_all(session: Session, data: dict[str, list[dict[str, Any]]]) -> None:
    """Sync all entities from G-System data into Local DB.

    Expects keys produced by GSystemClient.fetch_all():
      items, workcenters, processes, routings, routing_items,
      routing_processes, bom, prod_plans, item_processes

    Dependency-safe order per phase-04 sync plan.
    Caller owns commit/rollback.
    """
    item_index     = sync_items(session, data.get("items", []))
    wc_index       = sync_workcenters(session, data.get("workcenters", []))
    proc_index     = sync_processes(data.get("processes", []))
    routing_index  = sync_routings(session, data.get("routings", []))
    customer_index = sync_customers(session, data.get("customers", []))
    sync_routing_items(session, data.get("routing_items", []), item_index, routing_index)
    sync_routing_processes(session, data.get("routing_processes", []), routing_index, wc_index, proc_index)
    sync_bom(session, data.get("bom", []), item_index)
    sync_demands(session, data.get("prod_plans", []), item_index, customer_index)
    sync_item_processes(session, data.get("item_processes", []), item_index)
    sync_calendar(session, data.get("calendar", []))
    sync_stock(session, data.get("stock", []))
    logger.info("sync_all complete")

"""Seed APS local DB with mock data for dev/testing.

Uses upsert throughout — safe to run multiple times on a DB that already has
data from G-System sync (will not duplicate or conflict).

Calendar is skipped if the table already has rows (real calendar from G-System
DB sync takes precedence).

Usage:
    uv run python app/scripts/seed_mock_data.py
    python app/scripts/seed_mock_data.py          # inside Docker
    python app/scripts/seed_mock_data.py --reset  # drop + recreate all tables first
"""

import sys
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.db.database import SessionLocal, init_db
from app.models import (
    BOM,
    CalendarEntry,
    Customer,
    Demand,
    Item,
    ItemProcessStep,
    RoutingStep,
    Routing,
    RoutingItem,
    Stock,
    WorkCenter,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hhmm_to_hours(hhmm: str) -> float:
    """Convert mock HHMM string → decimal hours. "0800" → 8.0, "0830" → 8.5.

    Note: real G-System uses integer minutes — see db_syncer._minutes_to_hours.
    """
    if not hhmm or hhmm == "0000":
        return 0.0
    return round(int(hhmm[:2]) + int(hhmm[2:]) / 60, 4)


def _upsert_wc(session, **kwargs) -> WorkCenter:
    wc = session.query(WorkCenter).filter_by(gsystem_id=kwargs["gsystem_id"]).first()
    if wc is None:
        wc = WorkCenter(**kwargs)
        session.add(wc)
    else:
        for k, v in kwargs.items():
            setattr(wc, k, v)
    session.flush()
    return wc


def _upsert_item(session, **kwargs) -> Item:
    item = session.query(Item).filter_by(item_no=kwargs["item_no"]).first()
    if item is None:
        item = Item(**kwargs)
        session.add(item)
    else:
        for k, v in kwargs.items():
            setattr(item, k, v)
    session.flush()
    return item


def _upsert_routing(session, **kwargs) -> Routing:
    routing = session.query(Routing).filter_by(gsystem_id=kwargs["gsystem_id"]).first()
    if routing is None:
        routing = Routing(**kwargs)
        session.add(routing)
    else:
        for k, v in kwargs.items():
            setattr(routing, k, v)
    session.flush()
    return routing


# ── Seed functions ────────────────────────────────────────────────────────────

def _seed_workcenters(session) -> dict[int, WorkCenter]:
    rows = [
        dict(gsystem_id=14, workcenter_no="WC-014", workcenter_name="조립 1공정", workshop_cd="ASSY", std_capa=8.0),
        dict(gsystem_id=15, workcenter_no="WC-015", workcenter_name="조립 2공정", workshop_cd="ASSY", std_capa=8.0),
        dict(gsystem_id=20, workcenter_no="WC-020", workcenter_name="가공 공정",  workshop_cd="MACH", std_capa=10.0),
    ]
    return {r["gsystem_id"]: _upsert_wc(session, **r) for r in rows}


def _seed_items(session) -> dict[str, Item]:
    rows = [
        dict(item_no="CFB-4",       item_name='MAIL BACK FERRULE 4"',        asset_type="Product"),
        dict(item_no="CFB-6",       item_name='MAIL BACK FERRULE 6"',        asset_type="Product"),
        dict(item_no="CFF-4",       item_name='MAIL FRONT FERRULE 4"',       asset_type="Product"),
        dict(item_no="CFF-6",       item_name='MAIL FRONT FERRULE 6"',       asset_type="Product"),
        dict(item_no="CMC4-4N",     item_name='MAIL CONNECT 4" BODY',        asset_type="Product"),
        dict(item_no="CMC6-6N",     item_name='MAIL CONNECT 6" BODY',        asset_type="Product"),
        dict(item_no="CN-4",        item_name='MAIL CONNECT 4" NUT',         asset_type="Product"),
        dict(item_no="CN-6",        item_name='MAIL CONNECT 6" NUT',         asset_type="Product"),
        dict(item_no="CM081-300A0", item_name="CUSHION FRAME H/T LH",        asset_type="SemiProduct"),
        dict(item_no="CM082-300AR", item_name="CUSHION FRAME NON H/T RHD-LH",asset_type="SemiProduct"),
        dict(item_no="RAW-STEEL-4", item_name='STEEL TUBE 4" RAW',           asset_type="RawMaterial"),
        dict(item_no="RAW-STEEL-6", item_name='STEEL TUBE 6" RAW',           asset_type="RawMaterial"),
    ]
    return {r["item_no"]: _upsert_item(session, **r) for r in rows}


def _seed_routings(session) -> dict[int, Routing]:
    rows = [
        dict(gsystem_id=99,  routing_no=None,     routing_name="4인치 BODY", routing_type_cd="14681001"),
        dict(gsystem_id=100, routing_no=None,     routing_name="4인치 NUT",  routing_type_cd="14681001"),
        dict(gsystem_id=101, routing_no=None,     routing_name="6인치",      routing_type_cd="14681001"),
        dict(gsystem_id=91,  routing_no=None,     routing_name="test",       routing_type_cd="14681002"),
        dict(gsystem_id=80,  routing_no="AB-001", routing_name="생산1과",    routing_type_cd="14681001"),
    ]
    return {r["gsystem_id"]: _upsert_routing(session, **r) for r in rows}


def _seed_routing_items(session, routings: dict[int, Routing], items: dict[str, Item]) -> int:
    links = [
        (99,  "CMC4-4N"),
        (100, "CFB-4"), (100, "CFF-4"), (100, "CN-4"),
        (101, "CFB-6"), (101, "CFF-6"), (101, "CMC6-6N"), (101, "CN-6"),
        (91,  "CM081-300A0"), (91,  "CM082-300AR"),
    ]
    count = 0
    for gsys_id, item_no in links:
        routing = routings.get(gsys_id)
        item = items.get(item_no)
        if routing is None or item is None:
            continue
        exists = session.query(RoutingItem).filter_by(routing_id=routing.id, item_id=item.id).first()
        if not exists:
            session.add(RoutingItem(routing=routing, item=item))
            count += 1
    session.flush()
    return count


def _seed_operations(session, routings: dict[int, Routing], wcs: dict[int, WorkCenter]) -> int:
    rows = [
        dict(gsystem_id=99,  seq=1, proc_id=252, wc=14, work="1015", setup="0000"),
        dict(gsystem_id=99,  seq=2, proc_id=253, wc=14, work="1215", setup="1015"),
        dict(gsystem_id=99,  seq=3, proc_id=254, wc=14, work="1315", setup="2015"),
        dict(gsystem_id=100, seq=1, proc_id=260, wc=14, work="0800", setup="0030"),
        dict(gsystem_id=100, seq=2, proc_id=261, wc=15, work="0600", setup="0015"),
        dict(gsystem_id=101, seq=1, proc_id=270, wc=20, work="1000", setup="0045"),
        dict(gsystem_id=101, seq=2, proc_id=271, wc=14, work="0800", setup="0030"),
        # Routing 91 is linked to semi-products CM081/CM082; must have operations
        # to keep neo4j_graph scheduling from failing on those demand lots.
        dict(gsystem_id=91,  seq=1, proc_id=280, wc=15, work="0730", setup="0020"),
        dict(gsystem_id=91,  seq=2, proc_id=281, wc=20, work="0645", setup="0015"),
    ]
    count = 0
    for r in rows:
        routing = routings.get(r["gsystem_id"])
        if routing is None:
            continue
        op = session.query(RoutingStep).filter_by(routing_id=routing.id, process_seq=r["seq"]).first()
        if op is None:
            op = RoutingStep(routing=routing, process_seq=r["seq"])
            session.add(op)
        op.gsystem_process_id = r["proc_id"]
        op.proc_name = f"공정 {r['proc_id']}"
        op.workcenter = wcs.get(r["wc"])
        op.work_time_hours = _hhmm_to_hours(r["work"])
        op.setup_time_hours = _hhmm_to_hours(r["setup"])
        count += 1
    session.flush()
    return count


def _seed_calendar(session) -> int:
    """Seed 90-day calendar. Skipped if table already has rows (G-System DB sync takes precedence)."""
    existing = session.query(CalendarEntry).count()
    if existing > 0:
        print(f"  calendar: skipped ({existing} rows already exist)")
        return 0

    _dow_codes = ["10291001", "10291002", "10291003", "10291004", "10291005", "10291006", "10291007"]
    start = date(2025, 1, 1)
    days = 730  # ~2 years, enough for scripts that schedule into 2026
    for i in range(days):
        d = start + timedelta(days=i)
        dow_idx = d.weekday()
        is_holiday = dow_idx >= 5
        session.add(CalendarEntry(
            work_date=d,
            day_of_week_cd=_dow_codes[dow_idx],
            work_gb_cd="10431003" if is_holiday else "10431002",
            is_holiday=is_holiday,
            work_hours=0.0 if is_holiday else 8.0,
        ))
    session.flush()
    return days


def _seed_bom(session, items: dict[str, Item]) -> int:
    links = [
        ("CFB-4", "RAW-STEEL-4", 1.0),
        ("CFF-4", "RAW-STEEL-4", 0.5),
        ("CFB-6", "RAW-STEEL-6", 1.0),
    ]
    count = 0
    for parent_no, child_no, qty in links:
        parent = items.get(parent_no)
        child = items.get(child_no)
        if parent is None or child is None:
            continue
        row = session.query(BOM).filter_by(parent_item_id=parent.id, component_item_id=child.id).first()
        if row is None:
            session.add(BOM(parent_item=parent, component_item=child, qty1=qty, qty2=qty, bom_seq=1))
            count += 1
    session.flush()
    return count


def _seed_item_processes(session, items: dict[str, Item]) -> int:
    """Seed item process steps — which process each item goes through."""
    # (item_no, proc_sno, gsystem_proc_id, making_gb, inspection, work_ins, stock)
    rows = [
        ("CMC4-4N",     1, 252, "10401002", False, True,  False),
        ("CMC4-4N",     2, 253, "10401002", True,  False, False),
        ("CFB-4",       1, 260, "10401002", False, True,  False),
        ("CFB-4",       2, 261, "10401002", True,  False, True),
        ("CFB-6",       1, 270, "10401002", False, True,  False),
        ("CFB-6",       2, 271, "10401002", True,  False, True),
        ("CM081-300A0", 1, 252, "10401001", False, False, False),
        ("CM082-300AR", 1, 252, "10401001", False, False, False),
    ]
    count = 0
    for item_no, sno, proc_id, making_gb, insp, work_ins, stock in rows:
        item = items.get(item_no)
        if item is None:
            continue
        ip = session.query(ItemProcessStep).filter_by(item_id=item.id, proc_sno=sno).first()
        if ip is None:
            ip = ItemProcessStep(item=item, proc_sno=sno)
            session.add(ip)
        ip.gsystem_proc_id = proc_id
        ip.making_gb = making_gb
        ip.inspection_yn = insp
        ip.work_ins_yn = work_ins
        ip.stock_yn = stock
        count += 1
    session.flush()
    return count


def _seed_customers(session) -> dict[str, Customer]:
    from app.models.input.customer import CUSTOMER_TYPE_IMPACT
    rows = [
        dict(customer_no="CUST-INT-001", customer_name="Internal Production Order",    customer_type="internal"),
        dict(customer_no="CUST-SM-001",  customer_name="Minh Phat Trading Co.",        customer_type="small"),
        dict(customer_no="CUST-NM-001",  customer_name="Viet Hung Industrial Supply",  customer_type="normal"),
        dict(customer_no="CUST-NM-002",  customer_name="Thanh Long Manufacturing",     customer_type="normal"),
        dict(customer_no="CUST-IMP-001", customer_name="Samsung Electronics VN",       customer_type="important"),
        dict(customer_no="CUST-VIP-001", customer_name="Hyundai Motor Vietnam",        customer_type="vip"),
    ]
    result: dict[str, Customer] = {}
    for r in rows:
        cust = session.query(Customer).filter_by(customer_no=r["customer_no"]).first()
        if cust is None:
            cust = Customer(
                customer_no=r["customer_no"],
                customer_name=r["customer_name"],
                customer_type=r["customer_type"],
                impact_score=CUSTOMER_TYPE_IMPACT[r["customer_type"]],
            )
            session.add(cust)
        else:
            cust.customer_name = r["customer_name"]
            cust.customer_type = r["customer_type"]
            cust.impact_score = CUSTOMER_TYPE_IMPACT[r["customer_type"]]
        result[r["customer_no"]] = cust
    session.flush()
    return result


def _seed_demands(session, items: dict[str, Item], customers: dict[str, Customer]) -> int:
    rows = [
        # Baseline + on-time
        dict(plan_no="PO-2025-001", item_no="CMC4-4N",  qty=100.0, plan="2025-03-01", delv="2025-03-31", cust="CUST-VIP-001"),
        # Early due date (high late-risk candidate)
        dict(plan_no="PO-2025-002", item_no="CFB-4",    qty=200.0, plan="2025-03-05", delv="2025-03-25", cust="CUST-IMP-001"),
        # 1-N cardinality: same item appears in multiple demand rows.
        dict(plan_no="PO-2025-006", item_no="CFB-4",    qty=120.0, plan="2025-03-22", delv="2025-04-05", cust="CUST-NM-001"),
        dict(plan_no="PO-2025-007", item_no="CFB-4",    qty=90.0,  plan="2025-04-01", delv="2025-04-20", cust="CUST-SM-001"),
        dict(plan_no="PO-2025-008", item_no="CFB-4",    qty=60.0,  plan="2025-04-05", delv="2025-04-28", cust="CUST-INT-001"),
        # Material-heavy candidate
        dict(plan_no="PO-2025-003", item_no="CN-4",     qty=150.0, plan="2025-03-10", delv="2025-04-10", cust="CUST-NM-001"),
        dict(plan_no="PO-2025-009", item_no="CN-4",     qty=180.0, plan="2025-03-18", delv="2025-04-08", cust="CUST-IMP-001"),
        # Alternate product family
        dict(plan_no="PO-2025-004", item_no="CFB-6",    qty=80.0,  plan="2025-03-15", delv="2025-04-15", cust="CUST-NM-002"),
        dict(plan_no="PO-2025-010", item_no="CFB-6",    qty=110.0, plan="2025-04-03", delv="2025-05-05", cust="CUST-VIP-001"),
        dict(plan_no="PO-2025-005", item_no="CMC6-6N",  qty=60.0,  plan="2025-03-20", delv="2025-04-30", cust="CUST-SM-001"),
        dict(plan_no="PO-2025-011", item_no="CMC6-6N",  qty=140.0, plan="2025-04-10", delv="2025-05-12", cust="CUST-NM-002"),
        # Semi-product cases
        dict(plan_no="PO-2025-012", item_no="CM081-300A0", qty=70.0,  plan="2025-03-12", delv="2025-04-02", cust="CUST-NM-001"),
        dict(plan_no="PO-2025-013", item_no="CM082-300AR", qty=55.0,  plan="2025-03-14", delv="2025-04-18", cust="CUST-SM-001"),
        # Undated demand cases (to test neo4j_include_undated_demands)
        dict(plan_no="PO-2025-014", item_no="CFB-4",    qty=45.0,  plan=None,         delv="2025-05-01", cust="CUST-IMP-001"),
        dict(plan_no="PO-2025-015", item_no="CN-4",     qty=35.0,  plan="2025-04-12", delv=None,         cust="CUST-NM-002"),
        dict(plan_no="PO-2025-016", item_no="CMC4-4N",  qty=25.0,  plan=None,         delv=None,         cust="CUST-INT-001"),
        # Batch 2 (double volume): mirror cases with new plan_no/date windows
        dict(plan_no="PO-2025-017", item_no="CMC4-4N",  qty=130.0, plan="2025-05-01", delv="2025-05-29", cust="CUST-VIP-001"),
        dict(plan_no="PO-2025-018", item_no="CFB-4",    qty=210.0, plan="2025-05-03", delv="2025-05-20", cust="CUST-IMP-001"),
        dict(plan_no="PO-2025-019", item_no="CFB-4",    qty=95.0,  plan="2025-05-12", delv="2025-06-03", cust="CUST-NM-001"),
        dict(plan_no="PO-2025-020", item_no="CFB-4",    qty=70.0,  plan="2025-05-16", delv="2025-06-08", cust="CUST-SM-001"),
        dict(plan_no="PO-2025-021", item_no="CFB-4",    qty=55.0,  plan="2025-05-20", delv="2025-06-12", cust="CUST-INT-001"),
        dict(plan_no="PO-2025-022", item_no="CN-4",     qty=165.0, plan="2025-05-05", delv="2025-05-31", cust="CUST-NM-001"),
        dict(plan_no="PO-2025-023", item_no="CN-4",     qty=190.0, plan="2025-05-10", delv="2025-05-28", cust="CUST-IMP-001"),
        dict(plan_no="PO-2025-024", item_no="CFB-6",    qty=100.0, plan="2025-05-07", delv="2025-06-09", cust="CUST-NM-002"),
        dict(plan_no="PO-2025-025", item_no="CFB-6",    qty=125.0, plan="2025-05-18", delv="2025-06-20", cust="CUST-VIP-001"),
        dict(plan_no="PO-2025-026", item_no="CMC6-6N",  qty=85.0,  plan="2025-05-09", delv="2025-06-14", cust="CUST-SM-001"),
        dict(plan_no="PO-2025-027", item_no="CMC6-6N",  qty=150.0, plan="2025-05-22", delv="2025-06-26", cust="CUST-NM-002"),
        dict(plan_no="PO-2025-028", item_no="CM081-300A0", qty=78.0, plan="2025-05-04", delv="2025-05-30", cust="CUST-NM-001"),
        dict(plan_no="PO-2025-029", item_no="CM082-300AR", qty=62.0, plan="2025-05-08", delv="2025-06-06", cust="CUST-SM-001"),
        dict(plan_no="PO-2025-030", item_no="CFB-4",    qty=40.0,  plan=None,         delv="2025-06-18", cust="CUST-IMP-001"),
        dict(plan_no="PO-2025-031", item_no="CN-4",     qty=30.0,  plan="2025-05-26", delv=None,         cust="CUST-NM-002"),
        dict(plan_no="PO-2025-032", item_no="CMC4-4N",  qty=28.0,  plan=None,         delv=None,         cust="CUST-INT-001"),
        # Batch 3 (2026 horizon coverage): helps run_scheduler default horizon (2026-04..06)
        # Force R1 candidates: tight due dates + larger quantities on shared routings
        dict(plan_no="PO-2026-001", item_no="CFB-4",    qty=520.0, plan="2026-04-02", delv="2026-04-06", cust="CUST-IMP-001"),
        dict(plan_no="PO-2026-002", item_no="CFB-4",    qty=340.0, plan="2026-04-10", delv="2026-04-14", cust="CUST-NM-001"),
        dict(plan_no="PO-2026-003", item_no="CN-4",     qty=140.0, plan="2026-04-05", delv="2026-04-30", cust="CUST-NM-002"),
        dict(plan_no="PO-2026-004", item_no="CN-4",     qty=175.0, plan="2026-04-16", delv="2026-05-06", cust="CUST-IMP-001"),
        dict(plan_no="PO-2026-005", item_no="CFB-6",    qty=260.0, plan="2026-04-08", delv="2026-04-18", cust="CUST-VIP-001"),
        dict(plan_no="PO-2026-006", item_no="CMC6-6N",  qty=130.0, plan="2026-04-20", delv="2026-05-18", cust="CUST-SM-001"),
        dict(plan_no="PO-2026-007", item_no="CM081-300A0", qty=82.0, plan="2026-04-12", delv="2026-05-01", cust="CUST-NM-001"),
        dict(plan_no="PO-2026-008", item_no="CM082-300AR", qty=64.0, plan="2026-04-14", delv="2026-05-08", cust="CUST-SM-001"),
        dict(plan_no="PO-2026-009", item_no="CFB-4",    qty=48.0,  plan=None,         delv="2026-06-10", cust="CUST-INT-001"),
        dict(plan_no="PO-2026-010", item_no="CN-4",     qty=33.0,  plan="2026-05-22", delv=None,         cust="CUST-NM-002"),
        dict(plan_no="PO-2026-011", item_no="CMC4-4N",  qty=27.0,  plan=None,         delv=None,         cust="CUST-INT-001"),
        dict(plan_no="PO-2026-012", item_no="CMC4-4N",  qty=145.0, plan="2026-04-01", delv="2026-06-25", cust="CUST-VIP-001"),
        # R1 stress pack: many demands sharing constrained routings with tight due dates.
        # In current scheduler, per-lot duration does not scale with qty, so volume must
        # come from number of demands rather than quantity.
        dict(plan_no="PO-2026-013", item_no="CFB-4",    qty=40.0,  plan="2026-04-01", delv="2026-04-01", cust="CUST-IMP-001"),
        dict(plan_no="PO-2026-014", item_no="CFB-4",    qty=45.0,  plan="2026-04-01", delv="2026-04-01", cust="CUST-VIP-001"),
        dict(plan_no="PO-2026-015", item_no="CFB-4",    qty=50.0,  plan="2026-04-01", delv="2026-04-02", cust="CUST-NM-001"),
        dict(plan_no="PO-2026-016", item_no="CFB-4",    qty=35.0,  plan="2026-04-01", delv="2026-04-02", cust="CUST-SM-001"),
        dict(plan_no="PO-2026-017", item_no="CFB-6",    qty=55.0,  plan="2026-04-01", delv="2026-04-02", cust="CUST-IMP-001"),
        dict(plan_no="PO-2026-018", item_no="CFB-6",    qty=60.0,  plan="2026-04-01", delv="2026-04-03", cust="CUST-NM-002"),
        dict(plan_no="PO-2026-019", item_no="CMC4-4N",  qty=70.0,  plan="2026-04-01", delv="2026-04-02", cust="CUST-VIP-001"),
        dict(plan_no="PO-2026-020", item_no="CMC4-4N",  qty=65.0,  plan="2026-04-01", delv="2026-04-03", cust="CUST-INT-001"),
    ]
    count = 0
    for r in rows:
        item = items.get(r["item_no"])
        if item is None:
            continue
        demand = session.query(Demand).filter_by(plan_no=r["plan_no"]).first()
        customer = customers.get(r["cust"])
        if demand is None:
            session.add(Demand(
                plan_no=r["plan_no"],
                item=item,
                customer=customer,
                plan_qty=r["qty"],
                plan_date=date.fromisoformat(r["plan"]) if r.get("plan") else None,
                delivery_date=date.fromisoformat(r["delv"]) if r.get("delv") else None,
                status_cd="notCreated",
                data_source="mock",
            ))
            count += 1
        else:
            demand.item = item
            demand.customer = customer
            demand.plan_qty = r["qty"]
            demand.plan_date = date.fromisoformat(r["plan"]) if r.get("plan") else None
            demand.delivery_date = date.fromisoformat(r["delv"]) if r.get("delv") else None
            demand.status_cd = "notCreated"
            demand.data_source = "mock"
    session.flush()
    return count


def _seed_stock(session) -> int:
    """Seed stock records mirroring G-System lg_stock structure.

    Skipped if table already has rows (real data from G-System DB sync takes precedence).
    item_id uses item_no as mock G-System item identifier.
    """
    if session.query(Stock).count() > 0:
        print("  stock: skipped (rows already exist)")
        return 0

    rows = [
        dict(id=1001, item_id="CMC4-4N",     stk_ym="202503", wh_cd="WH-MAIN", able_qty=250.0, in_qty=300.0, out_qty=50.0),
        dict(id=1002, item_id="CFB-4",        stk_ym="202503", wh_cd="WH-MAIN", able_qty=180.0, in_qty=200.0, out_qty=20.0),
        dict(id=1003, item_id="CFF-4",        stk_ym="202503", wh_cd="WH-MAIN", able_qty=160.0, in_qty=200.0, out_qty=40.0),
        dict(id=1004, item_id="CN-4",         stk_ym="202503", wh_cd="WH-MAIN", able_qty=320.0, in_qty=400.0, out_qty=80.0),
        dict(id=1005, item_id="CFB-6",        stk_ym="202503", wh_cd="WH-MAIN", able_qty=90.0,  in_qty=100.0, out_qty=10.0),
        dict(id=1006, item_id="CMC6-6N",      stk_ym="202503", wh_cd="WH-MAIN", able_qty=70.0,  in_qty=80.0,  out_qty=10.0),
        # Keep raw-material stock intentionally low so scheduler output can naturally
        # produce R2 (MATERIAL_SHORTAGE) from aps_input data.
        dict(id=1007, item_id="RAW-STEEL-4",  stk_ym="202503", wh_cd="WH-RAW",  able_qty=25.0, in_qty=60.0, out_qty=35.0),
        dict(id=1008, item_id="RAW-STEEL-6",  stk_ym="202503", wh_cd="WH-RAW",  able_qty=18.0, in_qty=45.0, out_qty=27.0),
        dict(id=1009, item_id="CM081-300A0",  stk_ym="202503", wh_cd="WH-SEMI", able_qty=40.0,  in_qty=50.0,  out_qty=10.0),
        dict(id=1010, item_id="CM082-300AR",  stk_ym="202503", wh_cd="WH-SEMI", able_qty=35.0,  in_qty=40.0,  out_qty=5.0),
    ]
    for r in rows:
        entry = session.get(Stock, r["id"])
        if entry is None:
            entry = Stock(
                id=r["id"],
                item_id=r["item_id"],
                stk_ym=r["stk_ym"],
                wh_cd=r["wh_cd"],
                stk_type="10",
                unit_cd="EA",
                able_qty=r["able_qty"],
                in_qty=r["in_qty"],
                out_qty=r["out_qty"],
            )
            session.add(entry)
    session.flush()
    return len(rows)


# ── Action card output fixtures ───────────────────────────────────────────────

def _seed_action_card_fixtures(session, wcs: dict[int, WorkCenter], routings: dict[int, Routing]) -> int:
    """Deprecated: do not seed aps_result fixtures.

    Action-card coverage must come from aps_input + run_scheduler output,
    not from pre-seeded result tables.
    """
    print("  action_card_fixtures: disabled (use run_scheduler output from aps_input)")
    return 0


# ── Entry point ───────────────────────────────────────────────────────────────

def seed(reset: bool = False) -> None:
    init_db()
    session = SessionLocal()
    try:
        if reset:
            from app.db.database import Base, engine
            Base.metadata.drop_all(bind=engine)
            init_db()
            print("Tables reset.")

        wcs       = _seed_workcenters(session)
        items     = _seed_items(session)
        customers = _seed_customers(session)
        routings  = _seed_routings(session)
        ri_count  = _seed_routing_items(session, routings, items)
        op_count  = _seed_operations(session, routings, wcs)
        cal       = _seed_calendar(session)
        bom       = _seed_bom(session, items)
        dem       = _seed_demands(session, items, customers)
        ip        = _seed_item_processes(session, items)
        stk       = _seed_stock(session)
        fixtures  = _seed_action_card_fixtures(session, wcs, routings)

        session.commit()
        print(
            f"Seeded: {len(wcs)} workcenters, {len(items)} items, "
            f"{len(customers)} customers, {len(routings)} routings, "
            f"{ri_count} routing_items, {op_count} operations, "
            f"{cal} calendar entries, {bom} bom components, "
            f"{dem} demands, {ip} item_processes, {stk} stock entries, "
            f"{fixtures} action_card_fixtures."
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    reset_flag = "--reset" in sys.argv
    seed(reset=reset_flag)

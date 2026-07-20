"""Seed a self-contained, fully-consistent mock island for the Work Plan List.

The shared seed_mock_data.py does NOT seed aps_mps_plan / aps_item_routing_spec
(and its stock seeder predates the gsystem_item_id rename), so the Work Plan List
never populated 워크센터/공정 from mock data. This script builds an isolated set —
new items/workcenters/routing/irs/item_process/mps — whose keys line up so every
column resolves:

  mps (item_id, routing_id, gsystem_routing_id) ─┐
                                                 ├─ aps_item_routing_spec (proc_sno, workcenter_id, proc_name)
  item_process_step (item_id, routing_id, proc_sno)┘        └─ aps_workcenter (workcenter_name)

Idempotent (keyed by gsystem_id / item_no / plan_no). Does not touch real data.

Usage (inside aps_core_api):
    python app/scripts/seed_workplan_mock.py
Then rebuild risk:  POST /api/v1/kpi-summary/daily-plan/rebuild
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.db.database import SessionLocal, init_db
from app.models import (
    BOM,
    Item,
    ItemProcessStep,
    ItemRoutingSpec,
    MpsPlan,
    Routing,
    Stock,
    WorkCenter,
)

# ── Mock definition (all ids in a high, isolated range) ───────────────────────

WORKCENTERS = [  # (gsystem_id, no, name, std_capa)
    (9001, "WC-M01", "절단 공정", 8.0),
    (9002, "WC-M02", "조립 공정", 8.0),
    (9003, "WC-M03", "검사 공정", 8.0),
    (9004, "WC-M04", "포장 공정", 8.0),  # dedicated WC for the normal-risk line
]

ITEMS = [  # (gsystem_id, item_no, item_name, asset_type)
    (9101, "MOCK-P1", "목업 제품 1", "Product"),
    (9102, "MOCK-P2", "목업 제품 2", "Product"),
    (9103, "MOCK-R1", "목업 원자재 1", "RawMaterial"),
    (9104, "MOCK-P3", "목업 제품 3", "Product"),  # no BOM → no material shortage
]

ROUTINGS = [  # (gsystem_id, name)
    (9201, "목업 라우팅 1"),
    (9202, "목업 라우팅 2"),
    (9203, "목업 라우팅 3"),
]

# routing_gsys → [(proc_sno, workcenter_gsys, proc_name)] — a routing's operations
ROUTING_OPS = {
    9201: [(1, 9001, "절단1"), (2, 9002, "조립1"), (3, 9003, "검사1")],
    9202: [(1, 9002, "조립2"), (2, 9003, "검사2")],
    9203: [(1, 9004, "포장1")],
}

# which item runs on which routing
ROUTING_ITEMS = {
    9201: ["MOCK-P1"],
    9202: ["MOCK-P2"],
    9203: ["MOCK-P3"],
}

# mps lines: (plan_no, item_no, routing_gsys, qty, start, end, delivery, po_no)
MPS_LINES = [
    ("WP-MOCK-001", "MOCK-P1", 9201, 500.0, "2026-04-01", "2026-04-10", "2026-04-15", "PO-M1"),
    ("WP-MOCK-002", "MOCK-P2", 9202, 300.0, "2026-04-02", "2026-04-12", "2026-04-20", "PO-M2"),
    ("WP-MOCK-003", "MOCK-P1", 9201, 800.0, "2026-04-05", "2026-04-18", "2026-04-30", "PO-M3"),
    # normal: dedicated workcenter + qty ≤ daily capacity (fits one day, no carry
    # overflow) + no BOM → neither overload nor material shortage.
    ("WP-MOCK-004", "MOCK-P3", 9203, 10.0, "2026-04-03", "2026-04-13", "2026-04-25", "PO-M4"),
]

# BOM: (parent_no, component_no, qty1) — level-1
BOM_LINKS = [("MOCK-P1", "MOCK-R1", 2.0)]

# stock: (item_gsystem_id, able_qty) — R1 kept low so MOCK-P1 goes short
STOCK = [(9103, 100.0)]


def _get_or_add(session, model, filter_by: dict, values: dict):
    obj = session.query(model).filter_by(**filter_by).first()
    if obj is None:
        obj = model(**{**filter_by, **values})
        session.add(obj)
    else:
        for k, v in values.items():
            setattr(obj, k, v)
    session.flush()
    return obj


def seed() -> None:
    init_db()
    session = SessionLocal()
    try:
        wcs = {
            gid: _get_or_add(session, WorkCenter, {"gsystem_id": gid},
                             dict(workcenter_no=no, workcenter_name=nm, workshop_cd="MOCK", std_capa=cap))
            for gid, no, nm, cap in WORKCENTERS
        }
        items = {
            no: _get_or_add(session, Item, {"item_no": no},
                            dict(gsystem_id=gid, item_name=nm, asset_type=at))
            for gid, no, nm, at in ITEMS
        }
        routings = {
            gid: _get_or_add(session, Routing, {"gsystem_id": gid},
                             dict(routing_name=nm, routing_type_cd="14681001"))
            for gid, nm in ROUTINGS
        }

        # aps_item_routing_spec + aps_item_process_step from one source of truth
        irs_gsid = 9300
        irs_n = ip_n = 0
        for r_gsys, ops in ROUTING_OPS.items():
            routing = routings[r_gsys]
            for item_no in ROUTING_ITEMS[r_gsys]:
                item = items[item_no]
                for proc_sno, wc_gsys, proc_name in ops:
                    irs_gsid += 1
                    _get_or_add(
                        session, ItemRoutingSpec, {"gsystem_id": irs_gsid},
                        dict(item_id=item.id, routing_id=routing.id,
                             gsystem_routing_id=r_gsys, proc_sno=proc_sno,
                             workcenter_id=wcs[wc_gsys].id, proc_name=proc_name,
                             work_time=30.0, jph=120.0),
                    )
                    irs_n += 1
                    _get_or_add(
                        session, ItemProcessStep,
                        {"routing_id": routing.id, "item_id": item.id, "proc_sno": proc_sno},
                        dict(gsystem_proc_id=irs_gsid),
                    )
                    ip_n += 1

        # aps_mps_plan
        mps_gsid = 9500
        mps_n = 0
        for plan_no, item_no, r_gsys, qty, ps, pe, dd, po in MPS_LINES:
            mps_gsid += 1
            item = items[item_no]
            routing = routings[r_gsys]
            _get_or_add(
                session, MpsPlan, {"gsystem_id": mps_gsid},
                dict(plan_no=plan_no, item_id=item.id, gsystem_item_id=item.gsystem_id,
                     routing_id=routing.id, gsystem_routing_id=r_gsys,
                     plan_qty=qty, order_qty=qty,
                     plan_start_date=date.fromisoformat(ps),
                     plan_end_date=date.fromisoformat(pe),
                     delivery_date=date.fromisoformat(dd),
                     po_no=po, status_cd="notCreated"),
            )
            mps_n += 1

        # BOM + stock (for material-shortage risk)
        for parent_no, comp_no, q1 in BOM_LINKS:
            p, c = items[parent_no], items[comp_no]
            _get_or_add(session, BOM, {"parent_item_id": p.id, "component_item_id": c.id},
                        dict(qty1=q1, qty2=1.0, bom_seq=1))
        for gid, able in STOCK:
            _get_or_add(session, Stock, {"gsystem_item_id": str(gid)},
                        dict(stk_ym="202604", wh_cd="WH-MOCK", stk_type="10", unit_cd="EA",
                             able_qty=able, in_qty=able))

        session.commit()
        print(f"Seeded mock island: {len(wcs)} workcenters, {len(items)} items, "
              f"{len(routings)} routings, {irs_n} item_routing_specs, "
              f"{ip_n} item_process_steps, {mps_n} mps lines, "
              f"{len(BOM_LINKS)} bom, {len(STOCK)} stock.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed()

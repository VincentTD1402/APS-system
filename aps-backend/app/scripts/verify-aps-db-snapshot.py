#!/usr/bin/env python3
"""Snapshot APS DB state for comparison between mock vs G-System sync.

Usage:
    uv run python app/scripts/verify-aps-db-snapshot.py mock      # save /tmp/snapshot_mock.json
    uv run python app/scripts/verify-aps-db-snapshot.py gsystem   # save /tmp/snapshot_gsystem.json
    uv run python app/scripts/verify-aps-db-snapshot.py diff      # compare the two snapshots
    uv run python app/scripts/verify-aps-db-snapshot.py           # print to stdout
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text
from app.db.database import SessionLocal

SNAPSHOT_DIR = Path("/tmp")
S = "aps_input"  # schema shorthand


def q(session, sql: str) -> list[dict]:
    result = session.execute(text(sql))
    cols = list(result.keys())
    return [dict(zip(cols, row)) for row in result.fetchall()]


def take_snapshot(session) -> dict:
    snap = {}

    # Items
    rows = q(session, f"""
        SELECT item_no, item_name, asset_type, gsystem_id
        FROM {S}.aps_item ORDER BY item_no
    """)
    snap["items"] = {"count": len(rows), "rows": rows}

    # Workcenters
    rows = q(session, f"""
        SELECT workcenter_no, workcenter_name, gsystem_id, std_capa
        FROM {S}.aps_workcenter ORDER BY workcenter_no
    """)
    snap["workcenters"] = {"count": len(rows), "rows": rows}

    # Routings (with item count + op count)
    rows = q(session, f"""
        SELECT r.gsystem_id, r.routing_name, r.routing_no, r.routing_type_cd,
               COUNT(DISTINCT ri.item_id) AS item_count,
               COUNT(DISTINCT o.id)       AS op_count
        FROM {S}.aps_routing r
        LEFT JOIN {S}.aps_routing_item ri ON ri.routing_id = r.id
        LEFT JOIN {S}.aps_routing_step    o  ON o.routing_id  = r.id
        GROUP BY r.id, r.gsystem_id, r.routing_name, r.routing_no, r.routing_type_cd
        ORDER BY r.gsystem_id
    """)
    snap["routings"] = {"count": len(rows), "rows": rows}

    # Operations
    rows = q(session, f"""
        SELECT r.gsystem_id AS routing_gsys_id, r.routing_name,
               o.process_seq, o.proc_name, o.gsystem_process_id,
               ROUND(o.work_time_hours::numeric, 4)  AS work_h,
               ROUND(o.setup_time_hours::numeric, 4) AS setup_h,
               wc.workcenter_no
        FROM {S}.aps_routing_step o
        JOIN {S}.aps_routing   r  ON r.id  = o.routing_id
        LEFT JOIN {S}.aps_workcenter wc ON wc.id = o.workcenter_id
        ORDER BY r.gsystem_id, o.process_seq
    """)
    snap["operations"] = {"count": len(rows), "rows": rows}

    # Routing → Item links
    rows = q(session, f"""
        SELECT r.gsystem_id AS routing_gsys_id, r.routing_name,
               i.item_no, i.item_name
        FROM {S}.aps_routing_item ri
        JOIN {S}.aps_routing r ON r.id = ri.routing_id
        JOIN {S}.aps_item    i ON i.id = ri.item_id
        ORDER BY r.gsystem_id, i.item_no
    """)
    snap["routing_items"] = {"count": len(rows), "rows": rows}

    # Item Processes
    rows = q(session, f"""
        SELECT i.item_no, ip.proc_sno, ip.gsystem_proc_id,
               ROUND(ip.work_time_hours::numeric, 4) AS work_h,
               ip.stock_yn, ip.inspection_yn
        FROM {S}.aps_item_process_step ip
        JOIN {S}.aps_item i ON i.id = ip.item_id
        ORDER BY i.item_no, ip.proc_sno
    """)
    snap["item_processes"] = {"count": len(rows), "rows": rows}

    # Demands summary
    rows = q(session, f"""
        SELECT d.plan_no, i.item_no, d.plan_qty::float,
               d.plan_date::text, d.delivery_date::text,
               d.status_cd, d.data_source
        FROM {S}.aps_demand d
        JOIN {S}.aps_item   i ON i.id = d.item_id
        ORDER BY d.plan_no
    """)
    snap["demands"] = {"count": len(rows), "rows": rows}

    # Stock
    rows = q(session, f"""
        SELECT item_id, wh_cd, able_qty::float, stk_ym
        FROM {S}.aps_stock ORDER BY item_id, wh_cd
    """)
    snap["stock"] = {"count": len(rows), "rows": rows}

    # Calendar summary (not full rows)
    rows = q(session, f"""
        SELECT COUNT(*)                                      AS total_days,
               SUM(CASE WHEN is_holiday THEN 1 ELSE 0 END)  AS holidays,
               MIN(work_date)::text                          AS from_date,
               MAX(work_date)::text                          AS to_date,
               ROUND(AVG(work_hours)::numeric, 2)            AS avg_work_h
        FROM {S}.aps_calendar
    """)
    snap["calendar"] = rows[0] if rows else {}

    return snap


def print_summary(snap: dict, label: str = "") -> None:
    prefix = f"[{label}] " if label else ""
    print(f"\n{'─'*56}")
    print(f"  {prefix}APS DB Snapshot")
    print(f"{'─'*56}")
    for key, val in snap.items():
        if isinstance(val, dict) and "count" in val:
            print(f"  {key:<20}: {val['count']:>4} rows")
        else:
            cal = val
            print(f"  {'calendar':<20}: {cal.get('total_days',0)} days "
                  f"({cal.get('from_date','')} → {cal.get('to_date','')}), "
                  f"{cal.get('holidays',0)} holidays")
    print(f"{'─'*56}")


def diff_snapshots(a: dict, b: dict, label_a="mock", label_b="gsystem") -> None:
    print(f"\n{'='*60}")
    print(f"  DIFF: {label_a}  vs  {label_b}")
    print(f"{'='*60}")

    all_keys = sorted(set(list(a.keys()) + list(b.keys())))
    any_diff = False

    for key in all_keys:
        va = a.get(key, {})
        vb = b.get(key, {})
        ca = va.get("count") if isinstance(va, dict) and "count" in va else va
        cb = vb.get("count") if isinstance(vb, dict) and "count" in vb else vb

        if ca == cb:
            print(f"  {key:<22} {label_a}={ca}  {label_b}={cb}  ✓")
        else:
            print(f"  {key:<22} {label_a}={ca}  {label_b}={cb}  ← DIFF")
            any_diff = True

    # Detailed diff for key entity lists
    print()
    for key, id_field in [("items", "item_no"), ("workcenters", "workcenter_no"),
                           ("routings", "gsystem_id"), ("routing_items", None)]:
        rows_a = a.get(key, {}).get("rows") or []
        rows_b = b.get(key, {}).get("rows") or []

        if id_field:
            set_a = {str(r.get(id_field)) for r in rows_a}
            set_b = {str(r.get(id_field)) for r in rows_b}
        else:
            set_a = {f"{r.get('routing_gsys_id')}:{r.get('item_no')}" for r in rows_a}
            set_b = {f"{r.get('routing_gsys_id')}:{r.get('item_no')}" for r in rows_b}

        only_a = sorted(set_a - set_b)
        only_b = sorted(set_b - set_a)
        if only_a:
            print(f"  [{key}] only in {label_a}: {only_a}")
            any_diff = True
        if only_b:
            print(f"  [{key}] only in {label_b}: {only_b}")
            any_diff = True

    # Item-process detailed diff
    def ip_key(r): return f"{r['item_no']}.seq{r['proc_sno']}"
    ipa = {ip_key(r): r for r in (a.get("item_processes", {}).get("rows") or [])}
    ipb = {ip_key(r): r for r in (b.get("item_processes", {}).get("rows") or [])}
    only_a_ip = sorted(set(ipa) - set(ipb))
    only_b_ip = sorted(set(ipb) - set(ipa))
    wt_diff = []
    for k in set(ipa) & set(ipb):
        if abs((ipa[k].get("work_h") or 0) - (ipb[k].get("work_h") or 0)) > 0.01:
            wt_diff.append(f"{k}: {label_a}={ipa[k].get('work_h')}h  {label_b}={ipb[k].get('work_h')}h")
    if only_a_ip:
        print(f"  [item_process] only in {label_a}: {only_a_ip}")
    if only_b_ip:
        print(f"  [item_process] only in {label_b}: {only_b_ip}")
    if wt_diff:
        print(f"  [item_process work_time diffs]:")
        for d in wt_diff:
            print(f"    {d}")

    if not any_diff and not only_a_ip and not only_b_ip and not wt_diff:
        print("  ✓ Snapshots are structurally identical")

    print(f"{'='*60}")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else None

    if mode == "diff":
        f_a = SNAPSHOT_DIR / "snapshot_mock.json"
        f_b = SNAPSHOT_DIR / "snapshot_gsystem.json"
        if not f_a.exists() or not f_b.exists():
            sys.exit("Missing snapshots. Run with 'mock' and 'gsystem' labels first.")
        diff_snapshots(
            json.loads(f_a.read_text()),
            json.loads(f_b.read_text()),
        )
        return

    session = SessionLocal()
    try:
        snap = take_snapshot(session)
    finally:
        session.close()

    print_summary(snap, label=mode or "")

    if mode in ("mock", "gsystem"):
        out = SNAPSHOT_DIR / f"snapshot_{mode}.json"
        out.write_text(json.dumps(snap, indent=2, default=str))
        print(f"\n  Saved → {out}")
    else:
        print(json.dumps(snap, indent=2, default=str))


if __name__ == "__main__":
    main()

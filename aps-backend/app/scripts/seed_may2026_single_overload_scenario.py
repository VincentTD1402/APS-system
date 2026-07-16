#!/usr/bin/env python3
"""Seed October 2026 WC002-overload demo scenario into G-System DB.

Scenario (Oct 1–31 2026):
  - WC001, WC002, WC003 all GREEN across the month
  - WC002 has exactly 3 RED blocks: Oct 7, 14, 21
  → SHIFT_SCHEDULE action clearly shows improvement when applied

Run this script BEFORE resetting Docker.
After Docker reset, Neo4j is rebuilt from G-System — this script ensures:
  1. Demo orders (ids 75–84) have October 2026 dates
  2. All other G-System orders pushed to Dec 2026 (so scheduler doesn't
     pack them into October and create unwanted overload)
After Docker reset: sync → run scheduler with Oct horizon → clean demo.

Target item: FG-CASE08-003 (item_id=91002), routing 30
  Routing 30 process → workcenter (from pd_if_aps_routing_process):
    proc 254 → WC001 (id=10)
    proc 260 → WC002 (id=11)
    proc 270 → WC003 (id=12)

  Work-time calibration per unit:
    WC001 proc 254: 180 min → 180/480 = 37.5%  (green)
    WC002 proc 260: 360 min → 360/480 = 75.0%  (green)
    WC003 proc 270: 180 min → 180/480 = 37.5%  (green)

  Green orders (qty=1 → all WCs green):
    WC001: 37.5%, WC002: 75%, WC003: 37.5%

  Red orders (qty=2, plan_date = delv_date — scheduler packs all work in 1 day):
    WC001: 2×180=360/480=75%  → green  ✓
    WC002: 2×360=720/480=150% → RED    ✓  ← R3 triggered → action card
    WC003: 2×180=360/480=75%  → green  ✓

Steps this script performs:
  1. item_process: INSERT proc 254 step for item 91002 (adds WC001 load)
  2. item_process: UPDATE proc 270 work_time 300→180 (keeps WC003 green under overload)
  3. prod_plan:    DELETE previously inserted rows (ids 75–84)
  4. prod_plan:    INSERT 7 green orders + 3 red orders
  5. demand link:  UPDATE from_id=104 for item 91002 rows id>=75
  6. non-demo:     Push all other G-System orders to Dec 2026

Prerequisite: seed_gsystem_demo_data.py must have been run first.

Usage:
    cd /path/to/aps-backend
    uv run python app/scripts/seed_may2026_single_overload_scenario.py [--dry-run]

After running, trigger APS sync + run scheduler:
    curl -X POST http://localhost:8001/api/v1/gsystem/sync/api
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# --- Load .env ---------------------------------------------------------------
_env_file = Path(__file__).parent.parent.parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    sys.exit("psycopg2 not found. Run: pip install psycopg2-binary")

# --- Connection --------------------------------------------------------------
GSYSTEM_HOST = "192.168.205.231"
GSYSTEM_PORT = 5432
GSYSTEM_DB   = "gsystem"
GSYSTEM_USER = os.environ.get("GSYSTEM_DB_USER", "dev_user")
GSYSTEM_PASS = os.environ.get("GSYSTEM_DB_PASSWORD", "Gaon@1229")
SCHEMA = "demo"

# --- Constants ---------------------------------------------------------------
CORP_ID     = 1
BIZ_ID      = 7
REG_USER_ID = 166
NOW         = datetime.now()

DRY_RUN = "--dry-run" in sys.argv

# IDs inserted by previous script runs — clean up before re-seeding
OLD_PROD_PLAN_IDS = list(range(70, 85))  # ids 70–84 (covers old heavy + old single-block rows)

# ── 0. routing_process calibration ───────────────────────────────────────────
# Sync reads from pd_if_aps_routing_process (not pd_if_aps_item_process).
# graph_full_loader now multiplies work_time × qty → duration.
# For overload to happen: a single operation's duration must exceed 480 min
# (one calendar day). This means: work_time_per_unit × qty > 480.
#
# Calibration (qty=1 → green, qty=2 → red on WC002):
#   WC001 (proc 254): 180 min/unit → qty=2: 360 min → green (75%)
#   WC002 proc 260:   260 min/unit → qty=2: 520 min > 480 → RED (108%) ✓
#   WC002 proc 280:    80 min/unit → qty=2: 160 min → green
#   WC002 proc 271:    20 min/unit → qty=2:  40 min → green
#   WC002 total:      360 min/unit → qty=1: 75% green ✓
#   WC003 (proc 270):  60 min/unit → qty=2: 120 min → green (25%)
# Format: work_time/setup_time stored as 4-digit zero-padded minutes "MMMM"
ROUTING_PROCESS_CALIBRATION = [
    # (routing_process_id, work_time_str, setup_time_str)
    (128, "0180", "0000"),  # proc 254 → WC001: 180 min/unit
    (129, "0260", "0000"),  # proc 260 → WC002: 260 min/unit (qty=2 → 520 > 480 → RED)
    (130, "0045", "0015"),  # proc 270 → WC003: keep 60 min/unit
    (131, "0080", "0000"),  # proc 280 → WC002:  80 min/unit
    (132, "0020", "0000"),  # proc 271 → WC002:  20 min/unit
    # WC002 total: 260+80+20 = 360 min/unit → qty=1: 75% green
    # WC002 qty=2: proc 260 alone = 520 min > 480 → overloads calendar day → RED
]

# ── 1. item_process: add proc 254 → WC001 for item 91002 ─────────────────────
# routing 30, proc 254 → WC001 (id=10), 180 min/unit → 37.5% load (green)
# id 202100 is safely above current max (202017)
NEW_ITEM_PROCESS_ROW = (
    202100, 91002, 254, 0,           # ip_id, item_id, proc_id, proc_sno (before existing steps)
    "10401002", 180,                  # making_gb, work_time (minutes)
    "N", "N", "Y",                   # stock_yn, inspection_yn, work_ins_yn
    30, 1,                            # routing_id, rev_no
)

# ── 2. Prod plan rows ─────────────────────────────────────────────────────────
# Columns: (id, plan_no, plan_date, item_id, plan_qty, delv_date)

# Green orders: qty=1 → WC001 37.5%, WC002 75%, WC003 37.5% (all green)
# Delivery dates are spaced away from red days (Oct 7, 14, 21)
GREEN_ORDERS = [
    (75, "PO-2026-075", "20261001", 91002, 1.0, "20261002"),  # Oct 1  (Thu) → Oct 2  (Fri)
    (76, "PO-2026-076", "20261005", 91002, 1.0, "20261006"),  # Oct 5  (Mon) → Oct 6  (Tue)
    (77, "PO-2026-077", "20261008", 91002, 1.0, "20261009"),  # Oct 8  (Thu) → Oct 9  (Fri)
    (78, "PO-2026-078", "20261013", 91002, 1.0, "20261015"),  # Oct 13 (Tue) → Oct 15 (Thu)
    (79, "PO-2026-079", "20261016", 91002, 1.0, "20261020"),  # Oct 16 (Fri) → Oct 20 (Tue)
    (80, "PO-2026-080", "20261022", 91002, 1.0, "20261023"),  # Oct 22 (Thu) → Oct 23 (Fri)
    (81, "PO-2026-081", "20261027", 91002, 1.0, "20261028"),  # Oct 27 (Tue) → Oct 28 (Wed)
]

# Red orders: qty=2, plan_date=delv_date (forces 2 units onto that exact day)
# WC001: 75% (green), WC002: 150% (RED), WC003: 75% (green)
RED_ORDERS = [
    (82, "PO-2026-082", "20261007", 91002, 2.0, "20261007"),  # Oct 7  → WC002 150% RED
    (83, "PO-2026-083", "20261014", 91002, 2.0, "20261014"),  # Oct 14 → WC002 150% RED
    (84, "PO-2026-084", "20261021", 91002, 2.0, "20261021"),  # Oct 21 → WC002 150% RED
]


# ── Helpers ──────────────────────────────────────────────────────────────────

def step0_calibrate_routing_process(cur) -> int:
    """UPDATE pd_if_aps_routing_process work/setup times so WC2 shows green for qty=1, red for qty=2."""
    if DRY_RUN:
        for rp_id, wt, st in ROUTING_PROCESS_CALIBRATION:
            print(f"    [DRY] Would UPDATE routing_process id={rp_id}: work_time={wt}, setup_time={st}")
        return len(ROUTING_PROCESS_CALIBRATION)

    updated = 0
    for rp_id, wt, st in ROUTING_PROCESS_CALIBRATION:
        cur.execute(
            f"""
            UPDATE {SCHEMA}.pd_if_aps_routing_process
               SET work_time = %s,
                   setup_time = %s,
                   if_status = 'U',
                   if_recv_yn = 'N'
             WHERE routing_process_id = %s
            """,
            (wt, st, rp_id),
        )
        updated += cur.rowcount
    return updated


def step1_add_wc001_item_process(cur) -> int:
    """INSERT proc 254 → WC001 step for item 91002 (if not already inserted)."""
    ip_id, item_id, proc_id, proc_sno, making_gb, work_time, \
        stock_yn, inspection_yn, work_ins_yn, routing_id, rev_no = NEW_ITEM_PROCESS_ROW

    if DRY_RUN:
        print(f"    [DRY] Would INSERT item_process id={ip_id} (item 91002, proc 254 → WC001, {work_time}min)")
        return 1

    cur.execute(
        f"""
        INSERT INTO {SCHEMA}.pd_if_aps_item_process
            (if_status, if_recv_yn, if_type, corp_id, biz_id,
             item_process_id, item_id, proc_id, proc_sno,
             making_gb, work_time, stock_yn, inspection_yn, work_ins_yn,
             reg_user_id, reg_dt, routing_id, rev_no)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        (
            "A", "N", "item_process", CORP_ID, BIZ_ID,
            ip_id, item_id, proc_id, proc_sno,
            making_gb, work_time, stock_yn, inspection_yn, work_ins_yn,
            REG_USER_ID, NOW, routing_id, rev_no,
        ),
    )
    return cur.rowcount


def step2_reduce_wc003_work_time(cur) -> int:
    """UPDATE item_process for item 91002 proc 270 (WC003): work_time 300→180 min.

    With 2 units on a red day: 2×180=360/480=75% → WC003 stays green.
    With original 300: 2×300=600/480=125% → WC003 would also turn red (unwanted).
    """
    if DRY_RUN:
        print("    [DRY] Would UPDATE item_process id=202007 work_time 300→180 (item 91002, proc 270, WC003)")
        return 1

    cur.execute(
        f"""
        UPDATE {SCHEMA}.pd_if_aps_item_process
           SET work_time = 180
         WHERE item_process_id = 202007
           AND item_id = 91002
           AND proc_id = 270
        """,
    )
    return cur.rowcount


def step3_delete_old_prod_plans(cur) -> int:
    """DELETE previously seeded prod_plan rows (heavy overload rows + old single-block rows)."""
    if DRY_RUN:
        print(f"    [DRY] Would DELETE prod_plan WHERE id IN {tuple(OLD_PROD_PLAN_IDS)}")
        return len(OLD_PROD_PLAN_IDS)

    cur.execute(
        f"DELETE FROM {SCHEMA}.pd_if_aps_prod_plan WHERE id = ANY(%s)",
        (OLD_PROD_PLAN_IDS,)
    )
    return cur.rowcount


def step4_insert_prod_plans(cur) -> tuple[int, int]:
    """INSERT 7 green orders + 3 red orders for May 2026."""
    all_rows = GREEN_ORDERS + RED_ORDERS
    rows = [
        (
            "A", "N", NOW, "prod_plan", CORP_ID, BIZ_ID,
            row_id, plan_no, plan_date, item_id,
            "10271006",   # asset_type_cd: finished goods
            "11271002",   # unit_cd: EA
            "S",          # plan_gbn: 수주 (sales order)
            plan_qty,
            delv_date,
            "notCreated",
            REG_USER_ID, NOW,
        )
        for row_id, plan_no, plan_date, item_id, plan_qty, delv_date in all_rows
    ]
    sql = f"""
        INSERT INTO {SCHEMA}.pd_if_aps_prod_plan
            (if_status, if_recv_yn, if_recv_dt, if_type, corp_id, biz_id,
             id, plan_no, plan_date, item_id,
             asset_type_cd, unit_cd, plan_gbn, plan_qty,
             delv_date, status_cd,
             reg_user_id, reg_dt)
        VALUES %s
        ON CONFLICT (id) DO NOTHING
    """
    if DRY_RUN:
        print(f"    [DRY] Would INSERT {len(GREEN_ORDERS)} green orders (ids 75–81) + {len(RED_ORDERS)} red orders (ids 82–84)")
        return len(GREEN_ORDERS), len(RED_ORDERS)

    execute_values(cur, sql, rows)
    return len(GREEN_ORDERS), len(RED_ORDERS)


def step6_push_nondemo_gsystem_to_december(cur) -> int:
    """Push all non-demo G-System prod_plan delivery dates to Dec 2026.

    Without this, after Docker reset Neo4j is rebuilt from G-System and the
    69 original orders (large qty, old delivery dates) get scheduled into the
    October horizon → massive WC002 overload wipes out the demo effect.

    This ONLY changes delivery dates — all other columns (qty, item, routing)
    are preserved. To restore: re-sync from G-System source or revert dates.
    """
    if DRY_RUN:
        print("    [DRY] Would UPDATE G-System non-demo prod_plan delv_date/plan_date → Dec 2026")
        return 0
    cur.execute(
        f"""
        UPDATE {SCHEMA}.pd_if_aps_prod_plan
           SET delv_date = '20261231',
               plan_date = '20261201'
         WHERE id NOT BETWEEN 75 AND 84
           AND delv_date <= '20261031'
        """,
    )
    return cur.rowcount


def step5_link_to_demand(cur) -> int:
    """Link new prod_plan rows to demand id=104 (item 91002 → FG-CASE08-003)."""
    if DRY_RUN:
        print("    [DRY] Would UPDATE from_id=104 for item 91002 rows id>=75")
        return len(GREEN_ORDERS) + len(RED_ORDERS)

    cur.execute(
        f"""
        UPDATE {SCHEMA}.pd_if_aps_prod_plan
           SET from_id   = 104,
               fromtable = 'pd_demand'
         WHERE item_id = 91002
           AND id >= 75
        """,
    )
    return cur.rowcount


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    print(f"Connecting to {GSYSTEM_HOST}:{GSYSTEM_PORT}/{GSYSTEM_DB} as {GSYSTEM_USER} ...")
    conn = psycopg2.connect(
        host=GSYSTEM_HOST, port=GSYSTEM_PORT, dbname=GSYSTEM_DB,
        user=GSYSTEM_USER, password=GSYSTEM_PASS,
    )
    conn.autocommit = False
    cur = conn.cursor()

    try:
        prefix = "[DRY RUN] " if DRY_RUN else ""
        print(f"\n{prefix}Setting up Oct 2026 WC002-overload scenario in '{SCHEMA}'...")

        n_rp   = step0_calibrate_routing_process(cur)
        n_ip   = step1_add_wc001_item_process(cur)
        n_upd  = step2_reduce_wc003_work_time(cur)
        n_del  = step3_delete_old_prod_plans(cur)
        n_g, n_r = step4_insert_prod_plans(cur)
        n_link = step5_link_to_demand(cur)
        n_push = step6_push_nondemo_gsystem_to_december(cur)

        print()
        print(f"  [0] routing_process calibrate WC1/WC2 work_times:  {n_rp} rows updated")
        print(f"  [1] item_process INSERT proc 254 → WC001 (180min): {n_ip} row")
        print(f"  [2] item_process UPDATE proc 270 WC003 300→180min:  {n_upd} row")
        print(f"  [3] prod_plan DELETE old rows:                      -{n_del} rows")
        print(f"  [4] prod_plan INSERT green orders (qty=1, Oct):     +{n_g} rows (ids 75–81)")
        print(f"  [4] prod_plan INSERT red orders (qty=2, Oct 7/14/21):+{n_r} rows (ids 82–84)")
        print(f"  [5] Demand link item 91002 → demand 104:            {n_link} rows updated")
        print(f"  [6] Non-demo orders pushed to Dec 2026:             {n_push} rows updated")

        if DRY_RUN:
            conn.rollback()
            print("\n[DRY RUN] No changes committed.")
        else:
            conn.commit()
            print("\nDone — all changes committed.")

        print("\nExpected result after APS sync + scheduler run (Oct 2026 horizon):")
        print("  Oct 01–06, 08–13, 15–20, 22–31: all 3 WCs GREEN")
        print("    WC001: ≈37.5% | WC002: ≈75% | WC003: ≈37.5%")
        print("  Oct 07, 14, 21 (3 red blocks on WC002):")
        print("    WC001: 75% (green) | WC002: 150% (RED) | WC003: 75% (green)")
        print("    → R3 PlanImpactedOrder × 3 → 3 action cards (SHIFT_SCHEDULE)")
        print("\nNext steps:")
        print("  1. Reset Docker (Neo4j will rebuild from G-System with updated dates)")
        print("  2. curl -X POST http://localhost:8001/api/v1/gsystem/sync/api")
        print("  3. Run scheduler with Oct 2026 horizon → clean demo result")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Seed G-System demo schema pd_if_aps_* tables — INSERT-ONLY (no delete/update).

Fills in:
  1. pd_if_aps_equipment_master_info  — empty table → 6 equipment rows
  2. pd_if_aps_routing_process        — routing 32 (T2) has 0 steps → add 2
  3. pd_if_aps_item_process           — 10 routing×item pairs have 0 item-processes → add them

Context:
  - G-System DB: postgresql://192.168.205.231:5432/gsystem (schema: demo)
  - Items:       cm_if_aps_item    → item_id 91000..91011
  - Workcenters: cm_if_aps_workshop → workshop_id 10 (WC001), 11 (WC002), 12 (WC003)
  - Routings:    pd_if_aps_routing  → routing_id 27..32 (all exist)

Usage:
    cd /path/to/aps-backend
    uv run python app/scripts/seed_gsystem_demo_data.py [--dry-run]

After running, trigger APS sync:
    curl -X POST http://localhost:8001/api/v1/gsystem/sync/api
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# --- Load .env ------------------------------------------------------------------
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

# --- Connection -----------------------------------------------------------------
GSYSTEM_HOST = "192.168.205.231"
GSYSTEM_PORT = 5432
GSYSTEM_DB   = "gsystem"
GSYSTEM_USER = os.environ.get("GSYSTEM_DB_USER", "dev_user")
GSYSTEM_PASS = os.environ.get("GSYSTEM_DB_PASSWORD", "Gaon@1229")
SCHEMA = "demo"

# --- Constants ------------------------------------------------------------------
CORP_ID      = 1
BIZ_ID       = 7
PAREA_ID     = 1
REG_USER_ID  = 166
REG_IP       = "127.0.0.1"
NOW          = datetime.now()

DRY_RUN = "--dry-run" in sys.argv


# ── 1. Equipment master info ─────────────────────────────────────────────────────
# Workcenter IDs from cm_if_aps_workshop: 10=WC001, 11=WC002, 12=WC003
# The equipment_id here is the business ID (not the auto-increment 'id')
# Starting from 20 to avoid collisions (table is empty, but using named IDs is safe)
EQUIPMENT_ROWS = [
    # (equipment_id, equipment_no, equipment_nm, workshop_id, process_cd, equip_cls1)
    # equipment_id / no / nm come from pd_equipment_master_info (valid IDs: 2-7)
    # workshop_id refs cm_workshop.id (10=WC001, 11=WC002, 12=WC003)
    (2, "DEMO-WELD-EQ-001", "용접설비-CO2/MIG 용접기",  10, "260", "14841001"),
    (3, "DEMO-WELD-EQ-002", "용접설비-TIG 용접기",      10, "260", "14841001"),
    (4, "DEMO-WELD-EQ-003", "가공설비-플라즈마 절단기", 11, "252", "14841002"),
    (5, "DEMO-WELD-EQ-004", "가공설비-밴드쏘",          11, "254", "14841002"),
    (6, "DEMO-WELD-EQ-005", "후처리설비-샷블라스트",    12, "280", "14841003"),
    (7, "DEMO-WELD-EQ-006", "검사설비-치수검사대",      12, "281", "14841003"),
]

# ── 2. Routing processes for routing 32 (T2) — currently 0 steps ─────────────────
# routing_process_id starts from 200 (existing max = 136)
# work_time / setup_time stored as HHMM string (e.g. "0730" = 7h30m)
# workcenter_id 12 = WC003 (Heat Treatment & Finishing)
ROUTING_PROCESS_ROWS = [
    # (routing_process_id, routing_id, process_seq, process_id, workcenter_id, work_time, setup_time)
    (200, 32, 1, 280, 12, "0730", "0020"),   # HEAT-TREATMENT on WC003
    (201, 32, 2, 281, 12, "0500", "0015"),   # FINISHING on WC003
]

# ── 3. Item processes — INSERT for routing×item pairs with 0 existing records ────
# work_time is INTEGER MINUTES (not HHMM — different from routing_process)
# item_process_id starts from 202000 (existing max = 201614)
# making_gb "10401002" = 제조 (manufacturing), "10401001" = 가상 (virtual/semi)
# Columns: (ip_id, item_id, proc_id, proc_sno, making_gb, work_time, stock_yn, inspection_yn, work_ins_yn, routing_id)
ITEM_PROCESS_ROWS = [
    # routing 28 (생산1과) × item 91008 (WIP-FRAME-LH)
    # Routing 28 has procs: 270 (seq1), 254 (seq2), 271 (seq3), 281 (seq4)
    (202000, 91008, 270, 1, "10401001", 450, "N", "N", "Y", 28),  # MACHINING-B
    (202001, 91008, 254, 2, "10401001", 300, "Y", "Y", "N", 28),  # WELDING (final + inspect)

    # routing 28 (생산1과) × item 91009 (WIP-FRAME-RH)
    (202002, 91009, 270, 1, "10401001", 450, "N", "N", "Y", 28),
    (202003, 91009, 254, 2, "10401001", 300, "Y", "Y", "N", 28),

    # routing 29 (4인치 BODY) × item 91001 (FG-CASE08-002)
    # Routing 29 has procs: 252 (seq1), 253 (seq2), 254 (seq3), 270 (seq4), 281 (seq5)
    # Matching pattern of item 91000 (proc 260, 261) for consistency
    (202004, 91001, 260, 1, "10401002", 480, "N", "N", "Y", 29),  # MACHINING-A
    (202005, 91001, 261, 2, "10401002", 360, "Y", "Y", "N", 29),  # ASSEMBLY-A (final)

    # routing 30 (4인치 NUT) × item 91002 (FG-CASE08-003)
    # Routing 30 has procs: 254, 260, 270, 280, 271
    (202006, 91002, 260, 1, "10401002", 360, "N", "N", "Y", 30),  # MACHINING-A
    (202007, 91002, 270, 2, "10401002", 300, "Y", "Y", "N", 30),  # MACHINING-B (final)

    # routing 30 (4인치 NUT) × item 91003 (FG-CASE08-004)
    (202008, 91003, 260, 1, "10401002", 360, "N", "N", "Y", 30),
    (202009, 91003, 270, 2, "10401002", 300, "Y", "Y", "N", 30),

    # routing 31 (6인치) × item 91004 (SF-BODY-4IN)
    # Routing 31 has procs: 261 (seq1), 271 (seq2), 270 (seq3), 280 (seq4)
    (202010, 91004, 261, 1, "10401002", 480, "N", "N", "Y", 31),  # ASSEMBLY-A
    (202011, 91004, 271, 2, "10401002", 360, "Y", "Y", "N", 31),  # ASSEMBLY-B (final)

    # routing 31 (6인치) × item 91005 (SF-BODY-6IN)
    (202012, 91005, 261, 1, "10401002", 600, "N", "N", "Y", 31),
    (202013, 91005, 271, 2, "10401002", 480, "Y", "Y", "N", 31),

    # routing 31 (6인치) × item 91006 (SF-NUT-4IN)
    (202014, 91006, 261, 1, "10401002", 360, "N", "N", "Y", 31),
    (202015, 91006, 271, 2, "10401002", 240, "Y", "Y", "N", 31),

    # routing 31 (6인치) × item 91007 (SF-NUT-6IN)
    (202016, 91007, 261, 1, "10401002", 420, "N", "N", "Y", 31),
    (202017, 91007, 271, 2, "10401002", 300, "Y", "Y", "N", 31),
]


# ── 4. Prod plan (demands) for items using WC001 ─────────────────────────────────
# FG-CASE08-003 (item_id=91002) and FG-CASE08-004 (item_id=91003) use routing 30
# which routes through WC001. Without demands for these items, WC001 never appears
# in the scheduler Gantt chart.
# id starts from 53 (existing max id = 52), plan_no: PO-2025-053..060
# Columns: (id, plan_no, plan_date, item_id, plan_qty, delv_date)
PROD_PLAN_ROWS = [
    # FG-CASE08-003 (CASE ASSEMBLY 8" LIGHT DUTY) — 4인치 NUT routing → WC001
    (53, "PO-2025-053", "20250228", 91002, 80.0,  "20250315"),
    (54, "PO-2025-054", "20250310", 91002, 120.0, "20250325"),
    (55, "PO-2025-055", "20250320", 91002, 100.0, "20250405"),
    (56, "PO-2025-056", "20250401", 91002, 150.0, "20250420"),
    # FG-CASE08-004 (CASE ASSEMBLY 8" HEAVY DUTY) — 4인치 NUT routing → WC001
    (57, "PO-2025-057", "20250228", 91003, 60.0,  "20250315"),
    (58, "PO-2025-058", "20250310", 91003, 90.0,  "20250325"),
    (59, "PO-2025-059", "20250320", 91003, 80.0,  "20250405"),
    (60, "PO-2025-060", "20250401", 91003, 110.0, "20250420"),
    # FG-CASE08-003 — 2026 (same months/days, year shifted)
    (61, "PO-2026-061", "20260228", 91002, 80.0,  "20260315"),
    (62, "PO-2026-062", "20260310", 91002, 120.0, "20260325"),
    (63, "PO-2026-063", "20260320", 91002, 100.0, "20260405"),
    (64, "PO-2026-064", "20260401", 91002, 150.0, "20260420"),
    # FG-CASE08-004 — 2026
    (65, "PO-2026-065", "20260228", 91003, 60.0,  "20260315"),
    (66, "PO-2026-066", "20260310", 91003, 90.0,  "20260325"),
    (67, "PO-2026-067", "20260320", 91003, 80.0,  "20260405"),
    (68, "PO-2026-068", "20260401", 91003, 110.0, "20260420"),
    # FG-CASE08-003 — 2026 May/Jun (delivery overlap May 2026 horizon → WC001 visible)
    (69, "PO-2026-069", "20260415", 91002, 80.0,  "20260515"),
    (70, "PO-2026-070", "20260501", 91002, 120.0, "20260530"),
    (71, "PO-2026-071", "20260510", 91002, 100.0, "20260620"),
    # FG-CASE08-004 — 2026 May/Jun
    (72, "PO-2026-072", "20260415", 91003, 60.0,  "20260515"),
    (73, "PO-2026-073", "20260501", 91003, 90.0,  "20260530"),
    (74, "PO-2026-074", "20260510", 91003, 80.0,  "20260620"),
]


# ── 5. pd_demand — one row per item, assigns customer for impact scoring ─────────
# Required NOT NULL: id, corp_id, parea_id, biz_id, dmd_no, dmd_date, dmd_serl,
#                   dmd_type, item_id, item_rev, dmd_qty, status_cd, reg_user_id, reg_dt
# cust_id references cm_if_aps_cust.cust_id (97001..97006)
# item_id references cm_if_aps_item.id (91000..91011)
# Columns: (id, cust_id, item_id, dmd_no, dmd_qty)
PD_DEMAND_ROWS = [
    (100, 97001, 91008, "DMD-INT-001", 500.0),   # WIP-FRAME-LH  → Internal (97001)
    (101, 97001, 91009, "DMD-INT-002", 500.0),   # WIP-FRAME-RH  → Internal (97001)
    (102, 97002, 91000, "DMD-MPT-001", 300.0),   # FG-CASE08-001 → Minh Phat Trading (97002)
    (103, 97003, 91001, "DMD-VHI-001", 300.0),   # FG-CASE08-002 → Viet Hung Industrial (97003)
    (104, 97004, 91002, "DMD-TLM-001", 300.0),   # FG-CASE08-003 → Thanh Long Mfg (97004)
    (105, 97005, 91003, "DMD-SEV-001", 200.0),   # FG-CASE08-004 → Samsung Electronics VN (97005)
    (106, 97003, 91004, "DMD-VHI-002", 200.0),   # SF-BODY-4IN   → Viet Hung Industrial (97003)
    (107, 97003, 91005, "DMD-VHI-003", 200.0),   # SF-BODY-6IN   → Viet Hung Industrial (97003)
    (108, 97002, 91006, "DMD-MPT-002", 200.0),   # SF-NUT-4IN    → Minh Phat Trading (97002)
    (109, 97006, 91007, "DMD-HMV-001", 200.0),   # SF-NUT-6IN    → Hyundai Motor Vietnam (97006)
]

# ── 6. BOM — add raw-material links for items without BOM ────────────────────────
# upitem_id / downitem_id are G-System item IDs (cm_if_aps_item.id via gsystem_id field)
# Existing G-System BOM: 91000→91010, 91001→91011, 91002→91010
# Adding BOM for all remaining finished/semi items → RM-TUBE-4IN (91010)
# id starts from 200052 (existing max = 200051)
# Columns: (id, upitem_id, downitem_id, qty1, qty2, bom_sort, rev_no)
# qty2 mirrors qty1 (same pattern as existing rows); rev_no=4 matches existing BOM revision
BOM_ROWS = [
    (200052, 91003, 91010, 1, 1, 1, 4),  # FG-CASE08-004 → RM-TUBE-4IN
    (200053, 91004, 91010, 1, 1, 1, 4),  # SF-BODY-4IN   → RM-TUBE-4IN
    (200054, 91005, 91011, 1, 1, 1, 4),  # SF-BODY-6IN   → RM-TUBE-6IN
    (200055, 91006, 91010, 2, 2, 1, 4),  # SF-NUT-4IN    → RM-TUBE-4IN (qty 2)
    (200056, 91007, 91011, 2, 2, 1, 4),  # SF-NUT-6IN    → RM-TUBE-6IN (qty 2)
    (200057, 91008, 91010, 1, 1, 1, 4),  # WIP-FRAME-LH  → RM-TUBE-4IN
    (200058, 91009, 91010, 1, 1, 1, 4),  # WIP-FRAME-RH  → RM-TUBE-4IN
]


# ── Helpers ──────────────────────────────────────────────────────────────────────

def _insert_many(cur, sql: str, rows: list) -> int:
    if DRY_RUN:
        print(f"    [DRY] Would insert {len(rows)} rows: {sql.split('INTO')[1].split('(')[0].strip()}")
        return len(rows)
    execute_values(cur, sql, rows)
    return len(rows)


# ── Seed functions ────────────────────────────────────────────────────────────────

def seed_equipment(cur) -> int:
    rows = [
        (
            "A", "N", NOW, "equipment", CORP_ID, BIZ_ID,
            equip_id, equip_no, equip_nm, workshop_id, proc_cd, cls1, "Y",
            REG_USER_ID, NOW, REG_IP,
        )
        for equip_id, equip_no, equip_nm, workshop_id, proc_cd, cls1 in EQUIPMENT_ROWS
    ]
    sql = f"""
        INSERT INTO {SCHEMA}.pd_if_aps_equipment_master_info
            (if_status, if_recv_yn, if_recv_dt, if_type, corp_id, biz_id,
             equipment_id, equipment_no, equipment_nm, workshop_id, process_cd, equip_cls1, use_yn,
             reg_user_id, reg_dt, reg_ip)
        VALUES %s
        ON CONFLICT DO NOTHING
    """
    return _insert_many(cur, sql, rows)


def seed_routing_processes(cur) -> int:
    rows = [
        (
            "A", "N", "routing_process", CORP_ID, BIZ_ID,
            rp_id, r_id, proc_seq, proc_id, wc_id,
            work_t, setup_t, "Y", "Y",
            REG_USER_ID, NOW, REG_IP, BIZ_ID, PAREA_ID,
        )
        for rp_id, r_id, proc_seq, proc_id, wc_id, work_t, setup_t in ROUTING_PROCESS_ROWS
    ]
    sql = f"""
        INSERT INTO {SCHEMA}.pd_if_aps_routing_process
            (if_status, if_recv_yn, if_type, corp_id, biz_id,
             routing_process_id, routing_id, process_seq, process_id, workcenter_id,
             work_time, setup_time, result_mgmt_yn, use_yn,
             reg_user_id, reg_dt, reg_ip, dept_id, parea_id)
        VALUES %s
        ON CONFLICT DO NOTHING
    """
    return _insert_many(cur, sql, rows)


def seed_prod_plans(cur) -> int:
    rows = [
        (
            "A", "N", NOW, "prod_plan", CORP_ID, BIZ_ID,
            row_id, plan_no, plan_date, item_id,
            "10271006",   # asset_type_cd: finished goods
            "11271002",   # unit_cd: EA
            "S",          # plan_gbn: 수주 (sales order)
            plan_qty,
            delv_date,
            "notCreated", # status_cd
            REG_USER_ID, NOW,
        )
        for row_id, plan_no, plan_date, item_id, plan_qty, delv_date in PROD_PLAN_ROWS
    ]
    sql = f"""
        INSERT INTO {SCHEMA}.pd_if_aps_prod_plan
            (if_status, if_recv_yn, if_recv_dt, if_type, corp_id, biz_id,
             id, plan_no, plan_date, item_id,
             asset_type_cd, unit_cd, plan_gbn, plan_qty,
             delv_date, status_cd,
             reg_user_id, reg_dt)
        VALUES %s
        ON CONFLICT DO NOTHING
    """
    return _insert_many(cur, sql, rows)


def seed_pd_demand(cur) -> int:
    """Insert pd_demand rows with cust_id assigned per item type."""
    rows = [
        (
            row_id, CORP_ID, PAREA_ID, BIZ_ID,
            dmd_no,                         # dmd_no (varchar 20)
            NOW.strftime("%Y%m%d"),         # dmd_date (varchar 8 — YYYYMMDD)
            1,                              # dmd_serl
            "10",                           # dmd_type (varchar 15)
            cust_id,                        # cust_id → cm_if_aps_cust.cust_id
            0,                              # cust_rev
            item_id,                        # item_id → cm_if_aps_item.id
            0,                              # item_rev
            dmd_qty,                        # dmd_qty
            "notCreated",                   # status_cd (varchar 15)
            REG_USER_ID, NOW,
        )
        for row_id, cust_id, item_id, dmd_no, dmd_qty in PD_DEMAND_ROWS
    ]
    sql = f"""
        INSERT INTO {SCHEMA}.pd_demand
            (id, corp_id, parea_id, biz_id,
             dmd_no, dmd_date, dmd_serl, dmd_type,
             cust_id, cust_rev, item_id, item_rev,
             dmd_qty, status_cd,
             reg_user_id, reg_dt)
        VALUES %s
        ON CONFLICT (id) DO NOTHING
    """
    return _insert_many(cur, sql, rows)


def link_prod_plans_to_demand(cur) -> int:
    """UPDATE pd_if_aps_prod_plan.from_id to point to pd_demand rows by item_id.

    Each pd_demand row (id 100-109) owns a specific item_id.
    All prod_plan rows for that item_id are linked to the corresponding demand row.
    """
    if DRY_RUN:
        print("    [DRY] Would UPDATE pd_if_aps_prod_plan.from_id per item_id")
        return len(PD_DEMAND_ROWS)
    # Build (from_id, item_id) pairs from PD_DEMAND_ROWS
    # pd_if_aps_prod_plan.item_id stores the G-System item ID directly
    total = 0
    for demand_id, _cust_id, item_id, _dmd_no, _qty in PD_DEMAND_ROWS:
        cur.execute(
            f"""
            UPDATE {SCHEMA}.pd_if_aps_prod_plan
               SET from_id   = %s,
                   fromtable = 'pd_demand'
             WHERE item_id = %s
            """,
            (demand_id, item_id),
        )
        total += cur.rowcount
    return total


def seed_bom(cur) -> int:
    rows = [
        (
            "A", "N", NOW, "bom", CORP_ID, BIZ_ID,
            bom_id, upitem_id, downitem_id, qty1, qty2, bom_sort, rev_no,
            REG_USER_ID, NOW,
        )
        for bom_id, upitem_id, downitem_id, qty1, qty2, bom_sort, rev_no in BOM_ROWS
    ]
    sql = f"""
        INSERT INTO {SCHEMA}.cm_if_aps_bom
            (if_status, if_recv_yn, if_recv_dt, if_type, corp_id, biz_id,
             id, upitem_id, downitem_id, qty1, qty2, bom_sort, rev_no,
             reg_user_id, reg_dt)
        VALUES %s
        ON CONFLICT DO NOTHING
    """
    return _insert_many(cur, sql, rows)


def seed_item_processes(cur) -> int:
    rows = [
        (
            "A", "N", "item_process", CORP_ID, BIZ_ID,
            ip_id, item_id, proc_id, proc_sno,
            making_gb, work_time, stock_yn, inspection_yn, work_ins_yn,
            REG_USER_ID, NOW, routing_id, 1,  # rev_no=1
        )
        for ip_id, item_id, proc_id, proc_sno, making_gb, work_time,
            stock_yn, inspection_yn, work_ins_yn, routing_id in ITEM_PROCESS_ROWS
    ]
    sql = f"""
        INSERT INTO {SCHEMA}.pd_if_aps_item_process
            (if_status, if_recv_yn, if_type, corp_id, biz_id,
             item_process_id, item_id, proc_id, proc_sno,
             making_gb, work_time, stock_yn, inspection_yn, work_ins_yn,
             reg_user_id, reg_dt, routing_id, rev_no)
        VALUES %s
        ON CONFLICT DO NOTHING
    """
    return _insert_many(cur, sql, rows)


# ── Entry point ──────────────────────────────────────────────────────────────────

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
        print(f"\n{prefix}Inserting missing mock data into '{SCHEMA}' pd_if_aps_* tables...")

        n_eq   = seed_equipment(cur)
        n_rp   = seed_routing_processes(cur)
        n_ip   = seed_item_processes(cur)
        n_pp   = seed_prod_plans(cur)
        n_dmd  = seed_pd_demand(cur)
        n_link = link_prod_plans_to_demand(cur)
        n_bom  = seed_bom(cur)

        print(f"\n  equipment master info:  +{n_eq} rows")
        print(f"  routing_process (r=32): +{n_rp} rows")
        print(f"  item_process (missing): +{n_ip} rows")
        print(f"  prod_plan (WC001 items):+{n_pp} rows")
        print(f"  pd_demand (cust link):  +{n_dmd} rows")
        print(f"  prod_plan → demand link: {n_link} rows updated")
        print(f"  bom (R2 coverage):      +{n_bom} rows")

        if DRY_RUN:
            conn.rollback()
            print("\n[DRY RUN] No changes committed.")
        else:
            conn.commit()
            print("\nDone — all inserts committed.")
            print("\nNext: trigger APS sync to pull the new pending records:")
            print("  curl -X POST http://localhost:8001/api/v1/gsystem/sync/api")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()

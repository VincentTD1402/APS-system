"""Material shortage builder — per-component required vs available (자재부족).

Direct 1-level BOM explosion (multi-level BOM nesting intentionally ignored):
each MPS plan line's parent item maps straight to its BOM components.

  required(component)  = Σ over MPS lines using it ( plan_qty × qty1 / qty2 )
  available(component) = Σ aps_stock.in_qty for that component (기초 재고 / on-hand)
  shortage(component)  = max(0, required − available)

Single-version: wipes and rewrites aps_material_shortage on every run. Caller
owns commit. Live output depends on aps_stock being populated — when stock is
empty, available is 0 so shortage == required (surfaced, not hidden).
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_logger
from app.models import BOM, DailyPlan, Item, ItemRoutingSpec, MaterialShortage, MpsPlan, Stock

logger = get_logger(__name__)


def _item_id_by_gsys(session: Session) -> dict[int, int]:
    """{aps_item.gsystem_id → aps_item.id} — the G-System-id → local-id resolver."""
    out: dict[int, int] = {}
    for local_id, gsys_id in session.execute(select(Item.id, Item.gsystem_id)).all():
        if gsys_id is not None:
            out[int(gsys_id)] = local_id
    return out


def _available_by_item(session: Session, item_id_by_gsys: dict[int, int]) -> dict[int, float]:
    """Sum aps_stock.in_qty per local item id (기초 재고 / on-hand).

    aps_stock.gsystem_item_id is the G-System business item id (string) →
    resolved to the local aps_item via aps_item.gsystem_id.
    """
    available: dict[int, float] = defaultdict(float)
    for stk in session.execute(select(Stock)).scalars().all():
        if stk.in_qty is None or not stk.gsystem_item_id:
            continue
        try:
            gsys_id = int(stk.gsystem_item_id)
        except (TypeError, ValueError):
            logger.info("material_shortage: stock gsystem_item_id=%r not an int — skipped", stk.gsystem_item_id)
            continue
        local_id = item_id_by_gsys.get(gsys_id)
        if local_id is None:
            continue
        available[local_id] += float(stk.in_qty)
    return available


def rebuild_material_shortage(session: Session) -> int:
    """Wipe and rebuild aps_material_shortage. Returns rows written.

    Per MPS line: resolve its gsystem_item_id → local aps_item.id (= the BOM
    parent_item_id), read that parent's BOM components (qty1/qty2), and sum the
    material requirement plan_qty × qty1 / qty2 per component.
    """
    item_id_by_gsys = _item_id_by_gsys(session)

    # Load item master once: display meta + which items are raw materials.
    items = session.execute(select(Item)).scalars().all()
    item_meta: dict[int, tuple[str | None, str | None]] = {i.id: (i.item_no, i.item_name) for i in items}
    raw_material_ids: set[int] = {i.id for i in items if i.asset_type == "RawMaterial"}

    # Components (BOM children) grouped by BOM parent (local aps_item.id).
    bom_by_parent: dict[int, list[BOM]] = defaultdict(list)
    for bom in session.execute(select(BOM)).scalars().all():
        bom_by_parent[bom.parent_item_id].append(bom)

    # Source MPS lines by gsystem_item_id (not the local item_id FK, which may be
    # unresolved/NULL on some lines) — resolve to the local parent id ourselves.
    mps_lines = session.execute(
        select(MpsPlan).where(MpsPlan.gsystem_item_id.isnot(None), MpsPlan.plan_qty.isnot(None))
    ).scalars().all()

    # Required per (parent product/semiproduct, component) — BOM-like grain.
    required: dict[tuple[int, int], float] = defaultdict(float)
    for mps in mps_lines:
        plan_qty = float(mps.plan_qty)
        if plan_qty <= 0:
            continue
        parent_id = item_id_by_gsys.get(int(mps.gsystem_item_id))
        if parent_id is None:
            logger.info("material_shortage: mps=%s gsystem_item_id=%s not in aps_item — skipped", mps.id, mps.gsystem_item_id)
            continue
        for bom in bom_by_parent.get(parent_id, []):
            # Only raw materials are tracked for shortage; skip semiproduct/product components.
            if bom.component_item_id not in raw_material_ids:
                continue
            qty1 = float(bom.qty1) if bom.qty1 is not None else 0.0
            qty2 = float(bom.qty2) if bom.qty2 else 1.0  # qty2 None/0 → 1 (avoid div-by-zero)
            if qty1 <= 0:
                continue
            required[(parent_id, bom.component_item_id)] += plan_qty * qty1 / qty2

    available = _available_by_item(session, item_id_by_gsys)

    session.query(MaterialShortage).delete(synchronize_session=False)

    inserted = 0
    for (parent_id, comp_id), req in required.items():
        avail = available.get(comp_id, 0.0)
        shortage = max(0.0, req - avail)
        parent_no, parent_name = item_meta.get(parent_id, (None, None))
        item_no, item_name = item_meta.get(comp_id, (None, None))
        session.add(
            MaterialShortage(
                parent_item_id=parent_id,
                parent_item_no=parent_no,
                parent_item_name=parent_name,
                item_id=comp_id,
                item_no=item_no,
                item_name=item_name,
                required_qty=round(req, 4),
                available_qty=round(avail, 4),
                shortage_qty=round(shortage, 4),
            )
        )
        inserted += 1

    session.flush()
    logger.info(
        "rebuild_material_shortage: %d (parent, component) rows across %d MPS lines", inserted, len(mps_lines)
    )
    return inserted


def _raw_components_by_parent(session: Session, raw_material_ids: set[int]) -> dict[int, list[tuple[int, float]]]:
    """{parent_item_id → [(raw_component_id, qty1/qty2)]} — raw-material components only."""
    out: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for bom in session.execute(select(BOM)).scalars().all():
        if bom.component_item_id not in raw_material_ids:
            continue
        qty1 = float(bom.qty1) if bom.qty1 is not None else 0.0
        qty2 = float(bom.qty2) if bom.qty2 else 1.0
        if qty1 <= 0:
            continue
        out[bom.parent_item_id].append((bom.component_item_id, qty1 / qty2))
    return out


def apply_daily_material_shortage(session: Session) -> int:
    """Set aps_daily_plan.material_shortage_qty from a backward material balance.

    Reads the already-built daily plan. Per MPS line the raw material is drawn at
    its FIRST routing step (smallest proc_sno); consumption/day = that step's
    planned_qty × qty1/qty2 per raw component. For each material the on-hand stock
    (기초, aps_stock.in_qty) is consumed earliest-day-first, so any shortfall lands
    on the LATEST production days (backward). The day's shortfall is split across
    the first-step rows consuming that material that day, proportional to each
    row's draw, and summed onto material_shortage_qty. Returns rows flagged (>0).
    Caller owns commit. Run AFTER rebuild_daily_plan, in the same transaction.
    """
    item_id_by_gsys = _item_id_by_gsys(session)
    raw_material_ids = {i.id for i in session.execute(select(Item)).scalars().all() if i.asset_type == "RawMaterial"}
    raw_by_parent = _raw_components_by_parent(session, raw_material_ids)
    available = _available_by_item(session, item_id_by_gsys)  # {material_id → on-hand}

    parent_by_mps: dict[int, int] = {}
    for mps in session.execute(
        select(MpsPlan).where(MpsPlan.gsystem_item_id.isnot(None))
    ).scalars().all():
        pid = item_id_by_gsys.get(int(mps.gsystem_item_id))
        if pid is not None:
            parent_by_mps[mps.id] = pid

    # daily_plan rows + their routing step's proc_sno.
    rows = session.execute(
        select(DailyPlan, ItemRoutingSpec.proc_sno)
        .join(ItemRoutingSpec, DailyPlan.item_routing_id == ItemRoutingSpec.id)
    ).all()

    # Reset previous flags; find each MPS line's first-step proc_sno.
    min_proc: dict[int, int] = {}
    for dp, proc in rows:
        dp.material_shortage_qty = 0
        if proc is None:
            continue
        cur = min_proc.get(dp.mps_plan_id)
        if cur is None or proc < cur:
            min_proc[dp.mps_plan_id] = proc

    # Material consumption timeline: {material_id: {work_date: [(daily_plan_row, amount)]}}.
    consumption: dict[int, dict] = defaultdict(lambda: defaultdict(list))
    for dp, proc in rows:
        if proc is None or proc != min_proc.get(dp.mps_plan_id):
            continue  # only the first (material-input) step draws raw material
        parent_id = parent_by_mps.get(dp.mps_plan_id)
        if parent_id is None:
            continue
        qty = float(dp.planned_qty)
        for comp_id, ratio in raw_by_parent.get(parent_id, []):
            amount = qty * ratio
            if amount > 0:
                consumption[comp_id][dp.work_date].append((dp, amount))

    # Running balance per material: stock earliest-day-first → shortfall on latest days.
    flagged: set[int] = set()
    for material_id, by_day in consumption.items():
        remaining = available.get(material_id, 0.0)
        for day in sorted(by_day):
            contributors = by_day[day]
            day_total = sum(a for _dp, a in contributors)
            if remaining >= day_total:
                remaining -= day_total
                continue
            short_day = day_total - remaining
            remaining = 0.0
            for dp, amount in contributors:
                dp.material_shortage_qty = float(dp.material_shortage_qty or 0) + round(short_day * amount / day_total, 4)
                flagged.add(dp.id)

    # Fold material shortage into the combined status flag:
    #   overload + short → 'urgent' | short only → 'material-shortage' | else keep.
    for dp, _proc in rows:
        if float(dp.material_shortage_qty or 0) <= 0:
            continue
        dp.status = "urgent" if dp.status == "overload" else "material-shortage"

    session.flush()
    logger.info("apply_daily_material_shortage: %d daily rows flagged short", len(flagged))
    return len(flagged)

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
from app.models import BOM, Item, MaterialShortage, MpsPlan, Stock

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

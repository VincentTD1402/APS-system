"""Material shortage builder — per-component required vs available (자재부족).

Direct 1-level BOM explosion (multi-level BOM nesting intentionally ignored):
each MPS plan line's parent item maps straight to its BOM components.

  required(component)  = Σ over MPS lines using it ( plan_qty × qty1 / qty2 )
  available(component) = Σ aps_stock.able_qty for that component (기초 재고)
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


def _available_by_item(session: Session) -> dict[int, float]:
    """Sum aps_stock.able_qty per local item id (기초 재고).

    aps_stock.gsystem_item_id is the G-System business item id (string) →
    resolved to the local aps_item via aps_item.gsystem_id.
    """
    item_by_gsys: dict[int, int] = {}
    for local_id, gsys_id in session.execute(select(Item.id, Item.gsystem_id)).all():
        if gsys_id is not None:
            item_by_gsys[int(gsys_id)] = local_id

    available: dict[int, float] = defaultdict(float)
    for stk in session.execute(select(Stock)).scalars().all():
        if stk.able_qty is None or not stk.gsystem_item_id:
            continue
        try:
            gsys_id = int(stk.gsystem_item_id)
        except (TypeError, ValueError):
            logger.info("material_shortage: stock gsystem_item_id=%r not an int — skipped", stk.gsystem_item_id)
            continue
        local_id = item_by_gsys.get(gsys_id)
        if local_id is None:
            continue
        available[local_id] += float(stk.able_qty)
    return available


def rebuild_material_shortage(session: Session) -> int:
    """Wipe and rebuild aps_material_shortage. Returns rows written."""
    # Required per component — Σ (plan_qty × qty1/qty2) across MPS lines (1-level BOM).
    bom_by_parent: dict[int, list[BOM]] = defaultdict(list)
    for bom in session.execute(select(BOM)).scalars().all():
        bom_by_parent[bom.parent_item_id].append(bom)

    mps_lines = session.execute(
        select(MpsPlan).where(MpsPlan.item_id.isnot(None), MpsPlan.plan_qty.isnot(None))
    ).scalars().all()

    required: dict[int, float] = defaultdict(float)
    for mps in mps_lines:
        plan_qty = float(mps.plan_qty)
        if plan_qty <= 0:
            continue
        for bom in bom_by_parent.get(mps.item_id, []):
            qty1 = float(bom.qty1) if bom.qty1 is not None else 0.0
            qty2 = float(bom.qty2) if bom.qty2 else 1.0  # qty2 None/0 → 1 (avoid div-by-zero)
            if qty1 <= 0:
                continue
            required[bom.component_item_id] += plan_qty * qty1 / qty2

    available = _available_by_item(session)
    item_meta: dict[int, tuple[str | None, str | None]] = {
        i.id: (i.item_no, i.item_name)
        for i in session.execute(select(Item)).scalars().all()
    }

    session.query(MaterialShortage).delete(synchronize_session=False)

    inserted = 0
    for comp_id, req in required.items():
        avail = available.get(comp_id, 0.0)
        shortage = max(0.0, req - avail)
        item_no, item_name = item_meta.get(comp_id, (None, None))
        session.add(
            MaterialShortage(
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
        "rebuild_material_shortage: %d components across %d MPS lines", inserted, len(mps_lines)
    )
    return inserted

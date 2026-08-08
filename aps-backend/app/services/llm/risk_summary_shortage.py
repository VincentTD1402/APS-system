"""공정 투입 자재 부족 across the work plans currently on screen."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyPlan, MaterialShortage
from app.schemas.work_plan import WorkPlanRow
from app.schemas.work_plan_recommendation import ShortageComponent


def build_shortage_components(
    db: Session, rows: list[WorkPlanRow]
) -> list[ShortageComponent]:
    """Raw materials short for the products in the listed plans, worst first.

    Read from aps_material_shortage — the same source as GET /material-shortage,
    so the panel and that screen always agree on 현재고 / 부족수량. Grain is
    (parent product → component) across every MPS line of that product, which is
    what a purchasing decision needs; it is not split per instruction.
    """
    parent_item_nos = {row.item_no for row in rows if row.item_no}
    if not parent_item_nos:
        return []

    found = (
        db.execute(
            select(MaterialShortage).where(
                MaterialShortage.parent_item_no.in_(parent_item_nos),
                MaterialShortage.shortage_qty > 0,
            )
        )
        .scalars()
        .all()
    )
    components = [
        ShortageComponent(
            parent_item_no=m.parent_item_no,
            item_no=m.item_no,
            item_name=m.item_name,
            required_qty=float(m.required_qty),
            available_qty=float(m.available_qty),
            shortage_qty=float(m.shortage_qty),
        )
        for m in found
    ]
    components.sort(key=lambda c: c.shortage_qty, reverse=True)
    return components


def plans_hit_by_shortage(
    db: Session, rows: list[WorkPlanRow], mps_by_row: dict[str, int]
) -> set[str]:
    """Row ids whose own plan carries a material shortage on any of its days.

    Uses aps_daily_plan.material_shortage_qty (per MPS line) rather than the
    product-level aps_material_shortage, so a plan is only counted when its own
    schedule actually runs short.
    """
    mps_ids = set(mps_by_row.values())
    if not mps_ids:
        return set()

    short_mps = {
        mps_id
        for (mps_id,) in db.execute(
            select(DailyPlan.mps_plan_id).where(
                DailyPlan.mps_plan_id.in_(mps_ids),
                DailyPlan.material_shortage_qty > 0,
            )
        ).all()
    }
    return {row.id for row in rows if mps_by_row.get(row.id) in short_mps}

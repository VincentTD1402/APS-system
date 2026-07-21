"""Master data routes — read-only lists for the FE master views.

work-centers / items / routings / bom / inventory. All GET, no scenario scope
(single-version master synced from G-System).
"""
from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models import BOM, Equipment, Item, ItemRoutingSpec, Stock, WorkCenter
from app.schemas.master import (
    BomComponentOut,
    EquipmentOut,
    InventoryRowOut,
    ItemOut,
    RoutingOut,
    WorkCenterOut,
)

router = APIRouter()


@router.get("/work-centers", response_model=list[WorkCenterOut], summary="List work centers + equipment")
def list_work_centers(db: Session = Depends(get_db)) -> list[WorkCenterOut]:
    wc_no = {w.id: w.workcenter_no for w in db.execute(select(WorkCenter)).scalars().all()}
    eq_by_wc: dict[int, list[Equipment]] = defaultdict(list)
    for eq in db.execute(select(Equipment)).scalars().all():
        if eq.workcenter_id is not None:
            eq_by_wc[eq.workcenter_id].append(eq)

    out: list[WorkCenterOut] = []
    for wc in db.execute(select(WorkCenter).order_by(WorkCenter.workcenter_no)).scalars().all():
        std = float(wc.std_capa) if wc.std_capa is not None else None
        eqs = eq_by_wc.get(wc.id, [])
        out.append(WorkCenterOut(
            code=wc.workcenter_no,
            name_ko=wc.workcenter_name,
            default_runtime_min=std,
            total_runtime_min=(std * len(eqs)) if std is not None else None,
            equipments=[
                EquipmentOut(
                    code=str(eq.equipment_id) if eq.equipment_id is not None else "",
                    wc_code=wc.workcenter_no,
                    name_ko=eq.equipment_name,
                    st_rate=float(eq.cycle_factor) if eq.cycle_factor is not None else None,
                )
                for eq in eqs
            ],
        ))
    return out


@router.get("/items", response_model=list[ItemOut], summary="List items")
def list_items(db: Session = Depends(get_db)) -> list[ItemOut]:
    return [
        ItemOut(code=it.item_no, name_ko=it.item_name, uom=it.uom)
        for it in db.execute(select(Item).order_by(Item.item_no)).scalars().all()
    ]


@router.get("/routings", response_model=list[RoutingOut], summary="List item routings")
def list_routings(db: Session = Depends(get_db)) -> list[RoutingOut]:
    item_no = {i.id: i.item_no for i in db.execute(select(Item)).scalars().all()}
    wc_no = {w.id: w.workcenter_no for w in db.execute(select(WorkCenter)).scalars().all()}
    out: list[RoutingOut] = []
    stmt = select(ItemRoutingSpec).order_by(ItemRoutingSpec.item_id, ItemRoutingSpec.proc_sno)
    for r in db.execute(stmt).scalars().all():
        out.append(RoutingOut(
            id=r.id,
            item_code=item_no.get(r.item_id) if r.item_id is not None else None,
            step_no=r.proc_sno,
            wc_code=wc_no.get(r.workcenter_id) if r.workcenter_id is not None else None,
            process_name_ko=r.proc_name,
            # work_time is stored as SECONDS per unit (jph = 3600 / work_time per item_routing.py).
            # FE field standardStMin expects MINUTES → convert.
            standard_st_min=float(r.work_time) / 60.0 if r.work_time is not None else None,
        ))
    return out


@router.get("/bom", response_model=list[BomComponentOut], summary="List BOM components")
def list_bom(db: Session = Depends(get_db)) -> list[BomComponentOut]:
    item_no = {i.id: i.item_no for i in db.execute(select(Item)).scalars().all()}
    out: list[BomComponentOut] = []
    for b in db.execute(select(BOM).order_by(BOM.parent_item_id, BOM.bom_seq)).scalars().all():
        qty1 = float(b.qty1) if b.qty1 is not None else None
        qty2 = float(b.qty2) if b.qty2 else 1.0  # qty2 None/0 → 1 (avoid div-by-zero)
        out.append(BomComponentOut(
            id=b.id,
            parent_item_code=item_no.get(b.parent_item_id),
            child_item_code=item_no.get(b.component_item_id),
            qty_per=(qty1 / qty2) if qty1 is not None else None,
            scrap_rate=float(b.scrap_rate) if b.scrap_rate is not None else 0.0,
        ))
    return out


@router.get("/inventory", response_model=list[InventoryRowOut], summary="List stock on hand")
def list_inventory(db: Session = Depends(get_db)) -> list[InventoryRowOut]:
    # aps_stock.gsystem_item_id (business id) → local item_no via aps_item.gsystem_id.
    item_no_by_gsys = {
        int(g): no
        for g, no in db.execute(select(Item.gsystem_id, Item.item_no)).all()
        if g is not None
    }
    out: list[InventoryRowOut] = []
    for s in db.execute(select(Stock).order_by(Stock.id)).scalars().all():
        item_code = None
        if s.gsystem_item_id:
            try:
                item_code = item_no_by_gsys.get(int(s.gsystem_item_id))
            except (TypeError, ValueError):
                item_code = None
        as_of = f"{s.stk_ym[:4]}-{s.stk_ym[4:6]}-01" if s.stk_ym and len(s.stk_ym) >= 6 else None
        out.append(InventoryRowOut(
            id=s.id,
            item_code=item_code,
            warehouse_code=s.wh_cd,
            # able_qty = available stock (tồn kho khả dụng); NOT in_qty (which is inbound in-period).
            # Scheduler's material shortage detection needs the available balance.
            on_hand=float(s.able_qty) if s.able_qty is not None else None,
            as_of_date=as_of,
        ))
    return out

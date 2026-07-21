"""Planning routes — read-only lists for the FE MPS / Work-order views."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models import DailyPlan, Item, MpsPlan, WorkCenter, WorkOrder
from app.schemas.planning import MpsOut, WorkOrderOut

router = APIRouter()

# aps_mps_plan.status_cd → FE status. Only 'created'/'notCreated' seen in data.
_MPS_STATUS = {"created": "CONFIRMED", "notCreated": "DRAFT", "cancelled": "CANCELLED"}


@router.get("/mps", response_model=list[MpsOut], summary="List MPS plan lines")
def list_mps(db: Session = Depends(get_db)) -> list[MpsOut]:
    item_no = {i.id: i.item_no for i in db.execute(select(Item)).scalars().all()}
    out: list[MpsOut] = []
    for m in db.execute(select(MpsPlan).order_by(MpsPlan.plan_no)).scalars().all():
        out.append(MpsOut(
            id=m.id,
            order_no=m.plan_no,
            item_code=item_no.get(m.item_id) if m.item_id is not None else None,
            plan_qty=float(m.plan_qty) if m.plan_qty is not None else None,
            end_date=m.delivery_date,
            work_start_date=m.plan_start_date,
            work_end_date=m.plan_end_date,
            status=_MPS_STATUS.get(m.status_cd or "", "DRAFT"),
        ))
    return out


@router.get("/work-orders", response_model=list[WorkOrderOut], summary="List work orders")
def list_work_orders(db: Session = Depends(get_db)) -> list[WorkOrderOut]:
    item_no = {i.id: i.item_no for i in db.execute(select(Item)).scalars().all()}
    wc_no = {w.id: w.workcenter_no for w in db.execute(select(WorkCenter)).scalars().all()}
    # Work orders synced from G-System often carry item_id=NULL — fall back to the
    # MPS line's item so itemCode is still populated.
    mps_item = {m.id: m.item_id for m in db.execute(select(MpsPlan)).scalars().all()}
    # planStart/End derived from the MPS line's daily plan span.
    span: dict[int, tuple] = {
        mps_id: (dmin, dmax)
        for mps_id, dmin, dmax in db.execute(
            select(DailyPlan.mps_plan_id, func.min(DailyPlan.work_date), func.max(DailyPlan.work_date))
            .group_by(DailyPlan.mps_plan_id)
        ).all()
    }
    out: list[WorkOrderOut] = []
    for wo in db.execute(select(WorkOrder).order_by(WorkOrder.id)).scalars().all():
        dmin, dmax = span.get(wo.mps_plan_id, (None, None)) if wo.mps_plan_id else (None, None)
        item_id = wo.item_id if wo.item_id is not None else mps_item.get(wo.mps_plan_id)
        out.append(WorkOrderOut(
            id=wo.id,
            wo_no=wo.work_order_no,
            mps_id=wo.mps_plan_id,
            item_code=item_no.get(item_id) if item_id is not None else None,
            wc_code=wc_no.get(wo.workcenter_id) if wo.workcenter_id is not None else None,
            plan_qty=float(wo.qty) if wo.qty is not None else None,
            plan_start_date=dmin,
            plan_end_date=dmax,
            status=wo.status,
        ))
    return out

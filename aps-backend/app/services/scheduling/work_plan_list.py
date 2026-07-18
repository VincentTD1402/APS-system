"""Assemble the Work Plan List (작업계획 리스트) — read-only.

Base = every `aps_input.aps_mps_plan` line. The `aps_result.work_order` table is a
lookup only: if the line's `plan_no` exists there → `work_order_no = plan_no`
(source_type "WO", 미완료 작업지시); otherwise `tmp_plan_no = plan_no`
(source_type "MPS", 미작성 생산계획). Exactly one of the two identifiers is set.

Column derivations follow the caller's spec (see docs/api-spec.md §6):
  - 워크센터: aps_item_routing_spec (item_id, routing_id) → workcenter → aps_workcenter.
  - 공정: aps_item_process_step (item_id, routing_id) → proc_sno → aps_item_routing_spec.
  - dates: raw aps_mps_plan.plan_start_date / plan_end_date / delivery_date.
  - overload: aps_result.aps_daily_plan.status for the line; material_short: BOM × stock.
Columns whose source data is missing are returned as null (no fallback).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    BOM,
    DailyPlan,
    Item,
    ItemProcessStep,
    ItemRoutingSpec,
    MpsPlan,
    Stock,
    WorkCenter,
    WorkOrder,
)
from app.schemas.work_plan import WorkPlanRow


def _build_workcenter_index(db: Session) -> dict[tuple[int, int], tuple[Optional[str], Optional[str]]]:
    """(item_id, routing_id) → (workcenter_no, workcenter_name).

    From aps_item_routing_spec rows that carry a workcenter_id, joined to
    aps_workcenter. Representative operation = lowest proc_sno.
    """
    stmt = select(ItemRoutingSpec, WorkCenter).join(
        WorkCenter, ItemRoutingSpec.workcenter_id == WorkCenter.id
    )
    grouped: dict[tuple[int, int], list] = defaultdict(list)
    for ir, wc in db.execute(stmt).all():
        if ir.item_id is not None and ir.routing_id is not None:
            grouped[(ir.item_id, ir.routing_id)].append((ir, wc))

    index: dict[tuple[int, int], tuple[Optional[str], Optional[str]]] = {}
    for key, group in grouped.items():
        _, wc = min(group, key=lambda t: t[0].proc_sno if t[0].proc_sno is not None else 0)
        index[key] = (wc.workcenter_no, wc.workcenter_name)
    return index


def _build_proc_index(db: Session) -> dict[tuple[int, int], str]:
    """(item_id, routing_id) → proc_name.

    proc_sno comes from aps_item_process_step (item_id, routing_id); proc_name from
    aps_item_routing_spec (item_id, routing_id, proc_sno). Representative = lowest
    proc_sno that resolves to a proc_name.
    """
    proc_name_by_key: dict[tuple[int, int, int], str] = {}
    for irs in db.execute(select(ItemRoutingSpec)).scalars().all():
        if irs.item_id is not None and irs.routing_id is not None and irs.proc_sno is not None:
            proc_name_by_key[(irs.item_id, irs.routing_id, irs.proc_sno)] = irs.proc_name

    snos_by_key: dict[tuple[int, int], list[int]] = defaultdict(list)
    for ips in db.execute(select(ItemProcessStep)).scalars().all():
        if ips.item_id is not None and ips.routing_id is not None and ips.proc_sno is not None:
            snos_by_key[(ips.item_id, ips.routing_id)].append(ips.proc_sno)

    index: dict[tuple[int, int], str] = {}
    for key, snos in snos_by_key.items():
        for sno in sorted(snos):
            name = proc_name_by_key.get((key[0], key[1], sno))
            if name is not None:
                index[key] = name
                break
    return index


def _build_overload_set(db: Session) -> set[int]:
    """mps_plan_id set with at least one overloaded aps_daily_plan row."""
    overloaded: set[int] = set()
    for mps_plan_id, status in db.execute(select(DailyPlan.mps_plan_id, DailyPlan.status)).all():
        if status == "overload":
            overloaded.add(mps_plan_id)
    return overloaded


def _build_material_shortage(db: Session) -> set[int]:
    """Return the set of mps_plan.id whose BOM has ≥1 short component (자재부족).

    required(component) = plan_qty × (bom.qty1 / qty2); available = Σ able_qty of
    the component's LATEST stock month (join aps_stock.item_id == aps_item.gsystem_id).
    Level-1 BOM only; each MPS line evaluated independently against full stock (spec P5).
    """
    # aps_stock.item_id (string) → aps_item.id, via aps_item.gsystem_id
    gsid_to_item_id = {
        str(gsid): iid
        for iid, gsid in db.execute(select(Item.id, Item.gsystem_id)).all()
        if gsid is not None
    }
    # latest stk_ym per stock item — avoid summing able_qty across months
    latest_ym: dict[str, str] = {}
    for item_key, ym in db.execute(select(Stock.item_id, Stock.stk_ym)).all():
        if item_key is None or ym is None:
            continue
        if item_key not in latest_ym or ym > latest_ym[item_key]:
            latest_ym[item_key] = ym
    available_by_item_id: dict[int, float] = defaultdict(float)
    for st in db.execute(select(Stock)).scalars().all():
        if st.item_id is None or st.able_qty is None or st.stk_ym != latest_ym.get(st.item_id):
            continue
        iid = gsid_to_item_id.get(st.item_id)
        if iid is not None:
            available_by_item_id[iid] += float(st.able_qty)

    # level-1 BOM: parent_item_id → [(component_item_id, ratio)]
    bom_by_parent: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for b in db.execute(select(BOM)).scalars().all():
        if b.parent_item_id is None or b.component_item_id is None:
            continue
        q1 = float(b.qty1) if b.qty1 is not None else 1.0
        q2 = float(b.qty2) if b.qty2 else 1.0  # guard None/0 → 1
        bom_by_parent[b.parent_item_id].append((b.component_item_id, q1 / q2))

    short: set[int] = set()
    for mps in db.execute(select(MpsPlan)).scalars().all():
        if mps.item_id is None or mps.plan_qty is None:
            continue
        qty = float(mps.plan_qty)
        for comp_id, ratio in bom_by_parent.get(mps.item_id, ()):
            if qty * ratio > available_by_item_id.get(comp_id, 0.0) + 1e-9:
                short.add(mps.id)
                break
    return short


def _risk_types(overload: bool, material_short: bool) -> list[str]:
    """리스크유형: '부하초과'(overload) and/or '자재부족'(material_short); else ['normal']."""
    risks: list[str] = []
    if overload:
        risks.append("overload")
    if material_short:
        risks.append("material_short")
    return risks or ["normal"]


def _row_matches_filters(
    row: WorkPlanRow,
    *,
    workcenter_no: Optional[str],
    item_no: Optional[str],
    risk_type: Optional[str],
    plan_no: Optional[str],
    date_from: Optional[date],
    date_to: Optional[date],
) -> bool:
    """Post-assembly filter. Kept module-level so it is unit-testable without a DB."""
    if workcenter_no and row.workcenter_no != workcenter_no:
        return False
    if item_no and row.item_no != item_no:
        return False
    if risk_type and risk_type not in row.risk_types:
        return False
    if plan_no and plan_no not in (row.tmp_plan_no or "", row.work_order_no or "", row.order_no or ""):
        return False
    # Overlap test against [date_from, date_to]; rows missing the relevant date are dropped.
    if date_from and (row.plan_end is None or row.plan_end < date_from):
        return False
    if date_to and (row.plan_start is None or row.plan_start > date_to):
        return False
    return True


def build_work_plan_list(
    db: Session,
    *,
    workcenter_no: Optional[str] = None,
    item_no: Optional[str] = None,
    risk_type: Optional[str] = None,
    plan_no: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> list[WorkPlanRow]:
    """Build the Work Plan List — one row per aps_mps_plan line."""
    wo_plan_nos = {wo.plan_no for wo in db.execute(select(WorkOrder)).scalars().all() if wo.plan_no}
    items_by_id = {it.id: it for it in db.execute(select(Item)).scalars().all()}
    wc_index = _build_workcenter_index(db)
    proc_index = _build_proc_index(db)
    overload_ids = _build_overload_set(db)
    short_mps_ids = _build_material_shortage(db)

    rows: list[WorkPlanRow] = []
    for mps in db.execute(select(MpsPlan)).scalars().all():
        item = items_by_id.get(mps.item_id) if mps.item_id is not None else None
        key = (mps.item_id, mps.routing_id)
        wc = wc_index.get(key)  # (workcenter_no, workcenter_name) or None
        has_wo = mps.plan_no in wo_plan_nos
        rows.append(
            WorkPlanRow(
                source_type="WO" if has_wo else "MPS",
                # 작업지시번호 / (임시)작업계획번호 — both are plan_no; exactly one is set.
                work_order_no=mps.plan_no if has_wo else None,
                tmp_plan_no=None if has_wo else mps.plan_no,
                order_no=mps.po_no,  # 오더 = PO NO
                item_no=item.item_no if item else None,
                item_name=item.item_name if item else None,
                workcenter_no=wc[0] if wc else None,
                workcenter_name=wc[1] if wc else None,
                proc_name=proc_index.get(key),
                planned_qty=float(mps.plan_qty) if mps.plan_qty is not None else None,
                plan_start=mps.plan_start_date,  # 계획시작 = plan_start_date (raw)
                plan_end=mps.plan_end_date,  # 계획완료 = plan_end_date (raw)
                delivery_date=mps.delivery_date,
                risk_types=_risk_types(mps.id in overload_ids, mps.id in short_mps_ids),
            )
        )

    return [
        r
        for r in rows
        if _row_matches_filters(
            r,
            workcenter_no=workcenter_no,
            item_no=item_no,
            risk_type=risk_type,
            plan_no=plan_no,
            date_from=date_from,
            date_to=date_to,
        )
    ]

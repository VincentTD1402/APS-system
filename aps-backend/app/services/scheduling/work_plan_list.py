"""Assemble the Work Plan List (작업계획 리스트) — read-only.

Combines two disjoint sources per spec P6 (docs/specs/my_explain.md):
  - Set A (source_type="WO"): incomplete work orders — aps_result.work_order.
  - Set B (source_type="MPS"): uncreated MPS plan lines shown as temporary
    ((임시)) work plans — aps_input.aps_mps_plan where status_cd='notCreated'.

Per-operation columns (공정/워크센터) and the overload risk are enriched from
aps_result.aps_daily_plan (the backward-fill output of daily_plan_builder). A
line with no daily_plan coverage (missing item/routing mapping) simply leaves
those columns null — a known data gap, not an error.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BOM, DailyPlan, Item, ItemRoutingSpec, MpsPlan, Stock, WorkCenter, WorkOrder
from app.schemas.work_plan import WorkPlanRow
from app.services.scheduling.daily_plan_builder import _anchor_end_date

# MPS status_cd for lines that have NOT been turned into a work order yet.
_UNCREATED_STATUS = "notCreated"


def _tmp_plan_no(mps: MpsPlan) -> str:
    """Provisional (임시)작업계획번호 for an uncreated MPS line."""
    return f"WP-{mps.id:07d}"


def _build_daily_plan_enrichment(db: Session) -> dict[int, dict]:
    """Aggregate aps_daily_plan per mps_plan_id.

    Returns {mps_plan_id: {start, end, overload, proc_name, workcenter_no,
    workcenter_name}}. The representative operation (for 공정/워크센터 display)
    is the earliest routing step (lowest proc_sno).
    """
    stmt = (
        select(DailyPlan, ItemRoutingSpec, WorkCenter)
        .join(ItemRoutingSpec, DailyPlan.item_routing_id == ItemRoutingSpec.id)
        .join(WorkCenter, DailyPlan.workcenter_id == WorkCenter.id)
    )
    grouped: dict[int, list] = defaultdict(list)
    for dp, ir, wc in db.execute(stmt).all():
        grouped[dp.mps_plan_id].append((dp, ir, wc))

    enrichment: dict[int, dict] = {}
    for mps_id, group in grouped.items():
        work_dates = [dp.work_date for dp, _, _ in group]
        _, rep_ir, rep_wc = min(
            group, key=lambda t: t[1].proc_sno if t[1].proc_sno is not None else 0
        )
        enrichment[mps_id] = {
            "start": min(work_dates),
            "end": max(work_dates),
            "overload": any(dp.status == "overload" for dp, _, _ in group),
            "proc_name": rep_ir.proc_name,
            "workcenter_no": rep_wc.workcenter_no,
            "workcenter_name": rep_wc.workcenter_name,
        }
    return enrichment


def _risk_types(enrichment: Optional[dict], material_short: bool = False) -> list[str]:
    """리스크유형 for a row: '부하초과'(overload) and/or '자재부족'(material_short)."""
    risks: list[str] = []
    if enrichment and enrichment["overload"]:
        risks.append("overload")
    if material_short:
        risks.append("material_short")
    return risks or ["normal"]


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
    """Build the combined Work Plan List (Set A work orders + Set B MPS lines)."""
    enrichment = _build_daily_plan_enrichment(db)
    short_mps_ids = _build_material_shortage(db)
    items_by_id = {it.id: it for it in db.execute(select(Item)).scalars().all()}
    wc_by_id = {wc.id: wc for wc in db.execute(select(WorkCenter)).scalars().all()}

    rows: list[WorkPlanRow] = []

    # --- Set B: uncreated MPS plan lines (미작성 생산계획) ---
    mps_lines = (
        db.execute(select(MpsPlan).where(MpsPlan.status_cd == _UNCREATED_STATUS)).scalars().all()
    )
    for mps in mps_lines:
        e = enrichment.get(mps.id)
        item = items_by_id.get(mps.item_id) if mps.item_id is not None else None
        rows.append(
            WorkPlanRow(
                source_type="MPS",
                work_order_no=None,
                tmp_plan_no=_tmp_plan_no(mps),
                order_no=mps.po_no,
                item_no=item.item_no if item else None,
                item_name=item.item_name if item else None,
                workcenter_no=e["workcenter_no"] if e else None,
                workcenter_name=e["workcenter_name"] if e else None,
                proc_name=e["proc_name"] if e else None,
                planned_qty=float(mps.plan_qty) if mps.plan_qty is not None else None,
                # 계획시작 = Backward(종료일자) = earliest daily_plan day, else raw plan_start_date.
                plan_start=(e["start"] if e else None) or mps.plan_start_date,
                # 계획완료 = 종료일자 = plan_end_date.
                plan_end=mps.plan_end_date,
                delivery_date=mps.delivery_date,
                risk_types=_risk_types(e, mps.id in short_mps_ids),
            )
        )

    # --- Set A: incomplete work orders (미완료 작업지시) ---
    # Per spec, WO dates are read from the linked MPS line (생산계획입력), joined by plan_no.
    mps_by_plan_no: dict[str, MpsPlan] = {}
    for mps in db.execute(select(MpsPlan)).scalars().all():
        if mps.plan_no and mps.plan_no not in mps_by_plan_no:
            mps_by_plan_no[mps.plan_no] = mps
    for wo in db.execute(select(WorkOrder)).scalars().all():
        mps = mps_by_plan_no.get(wo.plan_no) if wo.plan_no else None
        e = enrichment.get(mps.id) if mps else None
        item = items_by_id.get(wo.item_id) if wo.item_id is not None else None
        wc = wc_by_id.get(wo.workcenter_id) if wo.workcenter_id is not None else None
        rows.append(
            WorkPlanRow(
                source_type="WO",
                work_order_no=wo.work_order_no,
                tmp_plan_no=None,
                order_no=mps.po_no if mps else None,
                item_no=wo.item_no or (item.item_no if item else None),
                item_name=item.item_name if item else None,
                workcenter_no=(e["workcenter_no"] if e else None) or (wc.workcenter_no if wc else None),
                workcenter_name=(e["workcenter_name"] if e else None) or (wc.workcenter_name if wc else None),
                proc_name=e["proc_name"] if e else None,
                planned_qty=float(mps.plan_qty) if (mps and mps.plan_qty is not None) else None,
                # 계획시작 = 작업시작일자(plan_start_date), else Backward.
                plan_start=(mps.plan_start_date if mps else None) or (e["start"] if e else None),
                # 계획완료 = 작업종료일자(prod_end_date) else 종료일자(plan_end_date).
                plan_end=_anchor_end_date(mps) if mps else None,
                delivery_date=mps.delivery_date if mps else None,
                risk_types=_risk_types(e, (mps.id in short_mps_ids) if mps else False),
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

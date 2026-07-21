"""Assemble the Work Plan List (작업계획 리스트) — read-only.

Driven by ``aps_input.work_order`` (see docs/workplan.md §1/§6). Each work_order
row is classified and mapped:

  - Confirmed (source_type "WO"): work_order_no NOT NULL, status "CONFIRMED",
    sync_status "SUCCESS", temp_id NULL.
  - Temporary (source_type "MPS"): work_order_no NULL, status "PLANNED".
  - Any other row (SENT / FAILED / partial) is skipped.

Base tables are ``aps_input.work_order`` + ``aps_input.aps_mps_plan``; enrichment
joins to master tables (aps_item / aps_workcenter / aps_item_routing_spec). Column
sourcing follows the standard spec P6 (docs/workplan.md):
  - 계획시작: WO = work_order.work_date (작업시작일자 — the confirmed order's own work
    date), else Backward. MPS = Backward-computed 시작일자 = earliest
    aps_daily_plan.work_date for the plan (no work order → always Backward).
  - 계획완료: WO = response_json.endDate (작업종료일자 — the order's own end), else
    plan_end_date (종료일자). MPS = latest aps_daily_plan.work_date (Backward window end;
    == plan_end_date normally, == today when overdue), else plan_end_date.
  - 계획수량 = WO: work_order.qty; MPS: aps_mps_plan.plan_qty.
  - 품목 = work_order.item_id → aps_item (name + code); WO falls back to response
    itemNo → aps_item. Any column/join with no data → null (do not fabricate).

Notes / deviations (verified against data):
  1. 공정: WO uses response_json.procNm (the order's own process name, present on all
     confirmed rows). MPS has no such field → proc_name is the item's representative
     lowest-proc_sno step from aps_item_routing_spec, keyed on item_id alone (the
     mps<->routing link is unreliable, so routing is not part of the key).
  2. 워크센터 for MPS rows: PLANNED work_order rows have workcenter_id NULL, so the
     workcenter is derived from aps_item_routing_spec via (item_id, routing_id).
  3. Risk status literal is 'material-shortage' (the aps_daily_plan CHECK value),
     not workplan.md's 'lack_material'. Exposed to the API as 'material_short'.

Risk (리스크유형): plan-level aggregate over aps_daily_plan.status — 부하초과
('overload') if ANY of the plan's days is overload/urgent, 자재부족 ('material_short')
if ANY is material-shortage/urgent, else 'normal'. workplan.md §5's single
(mps_plan_id, workcenter_id, work_date) key never matches the Backward-filled dates
(and MPS workcenter is often NULL), so it is realised as this aggregate — see
_build_risk_sets. Rebuild via POST /kpi-summary/daily-plan/rebuild first.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    DailyPlan,
    Item,
    ItemRoutingSpec,
    MpsPlan,
    WorkCenter,
    WorkOrder,
)
from app.schemas.work_plan import WorkPlanRow


def _parse_iso_date(value: object) -> Optional[date]:
    """Parse a G-System ISO date string (YYYY-MM-DD...) → date, or None."""
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _is_confirmed(wo: WorkOrder) -> bool:
    """작업지시 (confirmed) per workplan.md §2.A."""
    return (
        wo.work_order_no is not None
        and wo.status == "CONFIRMED"
        and wo.sync_status == "SUCCESS"
        and wo.temp_id is None
    )


def _is_planned(wo: WorkOrder) -> bool:
    """작업계획 (temporary) per workplan.md §2.B."""
    return wo.work_order_no is None and wo.status == "PLANNED"


def _build_wc_representative_index(
    db: Session,
) -> dict[tuple[int, int], tuple[int, Optional[str], Optional[str]]]:
    """(item_id, routing_id) → (workcenter_id, workcenter_no, workcenter_name).

    Representative workcenter for an item's routing, from aps_item_routing_spec
    rows carrying a workcenter, joined to aps_workcenter. Representative = lowest
    (proc_sno, gsystem_id). Keyed on (item_id, routing_id) because
    aps_item_routing_spec is item-specific — routing_id alone could belong to
    another item. Used for PLANNED rows, whose work_order.workcenter_id is NULL.

    Note: on current data this index is effectively empty for workcenter purposes —
    the item_routing_spec rows that carry a workcenter have no routing_id, so a
    routing-based match resolves nothing until routing steps get a workcenter
    assigned upstream. Intended (business-correct) behaviour: show null until then.
    """
    stmt = select(ItemRoutingSpec, WorkCenter).join(
        WorkCenter, ItemRoutingSpec.workcenter_id == WorkCenter.id
    )
    grouped: dict[tuple[int, int], list] = defaultdict(list)
    for irs, wc in db.execute(stmt).all():
        if irs.item_id is not None and irs.routing_id is not None:
            grouped[(irs.item_id, irs.routing_id)].append((irs, wc))

    index: dict[tuple[int, int], tuple[int, Optional[str], Optional[str]]] = {}
    for key, group in grouped.items():
        _, wc = min(
            group,
            key=lambda t: (
                t[0].proc_sno if t[0].proc_sno is not None else 0,
                t[0].gsystem_id if t[0].gsystem_id is not None else 0,
            ),
        )
        index[key] = (wc.id, wc.workcenter_no, wc.workcenter_name)
    return index


def _build_proc_by_item(db: Session) -> dict[int, str]:
    """item_id → proc_name of the representative (lowest proc_sno) step from
    aps_item_routing_spec. Used for MPS (temporary) rows: 공정 = the item's first
    process. Item-scoped, NOT routing-scoped — the mps<->routing link is unreliable
    on this data (item_id/routing_id FKs sparse, gsystem_routing_id shared across
    items), so item-only gives the correct, highest-coverage result. Representative =
    lowest (proc_sno, gsystem_id) for determinism.
    """
    groups: dict[int, list] = defaultdict(list)
    for irs in db.execute(select(ItemRoutingSpec)).scalars().all():
        if irs.item_id is not None and irs.proc_name is not None:
            groups[irs.item_id].append(irs)
    index: dict[int, str] = {}
    for item_id, g in groups.items():
        rep = min(
            g,
            key=lambda x: (
                x.proc_sno if x.proc_sno is not None else 0,
                x.gsystem_id if x.gsystem_id is not None else 0,
            ),
        )
        index[item_id] = rep.proc_name
    return index


def _build_risk_sets(db: Session) -> tuple[set[int], set[int]]:
    """(overload_mps_ids, material_short_mps_ids) from aps_daily_plan.status.

    리스크유형 is a plan-level summary: a work-plan row is 부하초과 if ANY of its plan's
    aps_daily_plan days is 'overload'/'urgent', 자재부족 if ANY is
    'material-shortage'/'urgent'. workplan.md §5 keys a single
    (mps_plan_id, workcenter_id, work_date) row, but that exact date never coincides
    with the Backward-filled work_date (verified 0/208) and the MPS workcenter is often
    NULL — so a single-row read is always 'normal'. Aggregating over the plan's days
    realises §5's intent (surface the plan's risk from aps_daily_plan.status) and is
    robust to the sparse workcenter/date data. Rebuild via
    POST /kpi-summary/daily-plan/rebuild first.
    """
    overload: set[int] = set()
    short: set[int] = set()
    for mps_plan_id, status in db.execute(select(DailyPlan.mps_plan_id, DailyPlan.status)).all():
        if status in ("overload", "urgent"):
            overload.add(mps_plan_id)
        if status in ("material-shortage", "urgent"):
            short.add(mps_plan_id)
    return overload, short


def _build_backward_window_index(db: Session) -> dict[int, tuple[date, date]]:
    """mps_plan_id → (earliest, latest) aps_daily_plan.work_date — the Backward window.

    daily_plan_builder already computes this: it anchors on the end date
    (prod_end_date/plan_end_date), fills day-by-day backward, and clamps to >= today.
    So earliest = 계획시작 (Backward), latest = 계획완료 of the temporary plan — normally
    == plan_end_date, but == today when the plan is overdue and got clamped, which keeps
    계획시작 <= 계획완료 (no start>end artifact). Plans with no daily_plan rows are absent.
    Rebuild via POST /kpi-summary/daily-plan/rebuild first.
    """
    lo: dict[int, date] = {}
    hi: dict[int, date] = {}
    for mps_plan_id, work_date in db.execute(
        select(DailyPlan.mps_plan_id, DailyPlan.work_date)
    ).all():
        if mps_plan_id not in lo or work_date < lo[mps_plan_id]:
            lo[mps_plan_id] = work_date
        if mps_plan_id not in hi or work_date > hi[mps_plan_id]:
            hi[mps_plan_id] = work_date
    return {k: (lo[k], hi[k]) for k in lo}


def _risk_types(overload: bool, material_short: bool) -> list[str]:
    """리스크유형: 'overload' and/or 'material_short'; else ['normal']."""
    risks: list[str] = []
    if overload:
        risks.append("overload")
    if material_short:
        risks.append("material_short")
    return risks or ["normal"]


def _risk_rank(row: WorkPlanRow) -> int:
    """Sort weight: count of real risks (2 = both, 1 = one, 0 = normal). Higher first."""
    return sum(1 for r in row.risk_types if r != "normal")


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
    """Post-assembly filter. Module-level so it is unit-testable without a DB."""
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
    """Build the Work Plan List — one row per confirmed/planned aps_input.work_order."""
    items_by_id = {it.id: it for it in db.execute(select(Item)).scalars().all()}
    items_by_no = {it.item_no: it for it in items_by_id.values() if it.item_no is not None}
    wc_by_id = {wc.id: wc for wc in db.execute(select(WorkCenter)).scalars().all()}
    mps_by_id = {mps.id: mps for mps in db.execute(select(MpsPlan)).scalars().all()}
    wc_repr_index = _build_wc_representative_index(db)
    proc_by_item = _build_proc_by_item(db)
    overload_ids, short_ids = _build_risk_sets(db)
    backward = _build_backward_window_index(db)

    rows: list[WorkPlanRow] = []
    for wo in db.execute(select(WorkOrder)).scalars().all():
        mps = mps_by_id.get(wo.mps_plan_id) if wo.mps_plan_id is not None else None

        if _is_confirmed(wo):
            resp = wo.response_json or {}
            # 품목: work_order.item_id → aps_item (name + code); fall back to response itemNo.
            item = items_by_id.get(wo.item_id) if wo.item_id is not None else None
            if item is None and resp.get("itemNo"):
                item = items_by_no.get(resp["itemNo"])
            wc = wc_by_id.get(wo.workcenter_id) if wo.workcenter_id is not None else None
            # 계획시작 (P6, 미완료 작업지시): 작업시작일자 = the work order's own scheduled
            # work date (work_order.work_date = response_json.workDate); else Backward-computed.
            wo_window = backward.get(wo.mps_plan_id) if wo.mps_plan_id is not None else None
            plan_start = wo.work_date or (wo_window[0] if wo_window else None)
            # 계획완료 (P6): 작업종료일자 = the work order's own end date (response_json.endDate);
            # else 종료일자 (aps_mps_plan.plan_end_date).
            plan_end = _parse_iso_date(resp.get("endDate")) or (mps.plan_end_date if mps else None)
            # 리스크유형: plan-level — any risky day of this plan's aps_daily_plan (see _build_risk_sets).
            overload, short = (wo.mps_plan_id in overload_ids, wo.mps_plan_id in short_ids)
            rows.append(
                WorkPlanRow(
                    source_type="WO",
                    work_order_no=wo.work_order_no,  # 작업지시번호 (P6 = số lệnh SX = work_order.work_order_no)
                    tmp_plan_no=None,
                    order_no=mps.po_no if mps else None,  # 오더
                    item_no=(item.item_no if item else resp.get("itemNo")),  # 품목 코드
                    item_name=item.item_name if item else None,  # 품목 명 (P6 = tên Item)
                    workcenter_no=wc.workcenter_no if wc else None,
                    workcenter_name=wc.workcenter_name if wc else None,
                    proc_name=resp.get("procNm"),  # 공정 (work order's own process name)
                    planned_qty=(  # 계획수량: work_order.qty (base table)
                        float(wo.qty) if wo.qty is not None
                        else (float(resp["planQty"]) if resp.get("planQty") is not None else None)
                    ),
                    plan_start=plan_start,  # 계획시작 (WO's own work date)
                    plan_end=plan_end,  # 계획완료 (WO's own end date)
                    delivery_date=mps.delivery_date if mps else None,  # 납기일자
                    risk_types=_risk_types(overload, short),
                )
            )
        elif _is_planned(wo) and mps is not None:
            item = items_by_id.get(mps.item_id) if mps.item_id is not None else None
            window = backward.get(mps.id)  # Backward-computed (start, end) from aps_daily_plan
            # 워크센터 (workplan.md §3): prefer work_order.workcenter_id; if NULL — always so
            # for PLANNED stubs today — fall back to the item's routing representative step.
            if wo.workcenter_id is not None:
                wc_obj = wc_by_id.get(wo.workcenter_id)
                wc_no = wc_obj.workcenter_no if wc_obj else None
                wc_name = wc_obj.workcenter_name if wc_obj else None
            else:
                rep = wc_repr_index.get((mps.item_id, mps.routing_id))
                wc_no = rep[1] if rep else None
                wc_name = rep[2] if rep else None
            # 리스크유형: plan-level — any risky day of this plan's aps_daily_plan.
            overload, short = (mps.id in overload_ids, mps.id in short_ids)
            rows.append(
                WorkPlanRow(
                    source_type="MPS",
                    work_order_no=None,
                    tmp_plan_no=mps.plan_no,  # (임시)작업계획번호
                    order_no=mps.po_no,  # 오더
                    item_no=item.item_no if item else None,  # 품목
                    item_name=item.item_name if item else None,
                    workcenter_no=wc_no,
                    workcenter_name=wc_name,
                    proc_name=proc_by_item.get(mps.item_id),  # 공정 (item's representative step)
                    planned_qty=float(mps.plan_qty) if mps.plan_qty is not None else None,  # 계획수량
                    plan_start=window[0] if window else None,  # 계획시작 (Backward-start)
                    plan_end=(window[1] if window else mps.plan_end_date),  # 계획완료 (Backward-end; fallback 종료일자)
                    delivery_date=mps.delivery_date,  # 납기일자
                    risk_types=_risk_types(overload, short),
                )
            )
        # else: SENT / FAILED / partial rows are not part of the work plan list.

    filtered = [
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
    # 리스크 건 최우선 정렬: more risks first, then earliest delivery; stable within group.
    filtered.sort(key=lambda r: (-_risk_rank(r), r.delivery_date or date.max))
    return filtered

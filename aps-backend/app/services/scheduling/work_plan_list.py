"""Assemble the Work Plan List (작업계획 리스트) — read-only.

Base = every `aps_input.aps_mps_plan` line. The `aps_result.work_order` table is a
lookup only: if the line's `plan_no` exists there → `work_order_no = plan_no`
(source_type "WO", 미완료 작업지시); otherwise `tmp_plan_no = plan_no`
(source_type "MPS", 미작성 생산계획). Exactly one of the two identifiers is set.

Column derivations follow the caller's spec (see docs/api-spec.md §6):
  - 워크센터: aps_item_routing_spec (item_id, routing_id) → workcenter → aps_workcenter.
  - 공정: aps_item_process_step (item_id, routing_id) → proc_sno → aps_item_routing_spec.
  - dates: raw aps_mps_plan.plan_start_date / plan_end_date / delivery_date.
  - risk (overload / material_short): aps_result.aps_daily_plan.status for the line
    (rebuild via POST /kpi-summary/daily-plan/rebuild first).
Columns whose source data is missing are returned as null (no fallback).
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
    ItemProcessStep,
    ItemRoutingSpec,
    MpsPlan,
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


def _build_risk_sets(db: Session) -> tuple[set[int], set[int]]:
    """(overload_mps_ids, material_short_mps_ids) derived from aps_daily_plan.status.

    Both risks share one source: the per-day status folded by rebuild_daily_plan +
    apply_daily_material_shortage (via POST /kpi-summary/daily-plan/rebuild). A line
    is overloaded if any of its daily rows is 'overload'/'urgent', and material-short
    if any is 'material-shortage'/'urgent'. Lines with no daily_plan rows → neither.
    """
    overload: set[int] = set()
    short: set[int] = set()
    for mps_plan_id, status in db.execute(select(DailyPlan.mps_plan_id, DailyPlan.status)).all():
        if status in ("overload", "urgent"):
            overload.add(mps_plan_id)
        if status in ("material-shortage", "urgent"):
            short.add(mps_plan_id)
    return overload, short


def _risk_types(overload: bool, material_short: bool) -> list[str]:
    """리스크유형: '부하초과'(overload) and/or '자재부족'(material_short); else ['normal']."""
    risks: list[str] = []
    if overload:
        risks.append("overload")
    if material_short:
        risks.append("material_short")
    return risks or ["normal"]


def _risk_rank(row: WorkPlanRow) -> int:
    """Sort weight for the risk-first ordering: count of real risks on the row.

    2 = both overload+material_short, 1 = one risk, 0 = normal. Higher first.
    """
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
    overload_ids, short_mps_ids = _build_risk_sets(db)

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
    # 리스크 건 최우선 정렬: rows with more risks first, then earliest delivery.
    # Stable sort keeps same-rank/same-delivery rows in aps_mps_plan order; rows
    # without a delivery_date fall to the bottom of their risk group.
    filtered.sort(key=lambda r: (-_risk_rank(r), r.delivery_date or date.max))
    return filtered

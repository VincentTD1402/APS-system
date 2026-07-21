"""Daily plan builder — backward-fill each MPS plan line's plan_qty into
per-day quantities per routing step, feeding KPI3 (workcenter load).

Algorithm per MPS line (aps_mps_plan):
  1. Anchor end date — 작업종료일자(prod_end_date) when status_cd=="created" and
     set, else 종료일자(plan_end_date) (matches G-System's own display rule).
  2. Routing steps for the item (aps_item_routing_spec, ordered by proc_sno),
     filtered to the MPS line's routing_id when it matches one of the item's
     steps.
  3. Walk steps from the LAST (highest proc_sno) backward: each step's window
     ends the day before the next (later) step's earliest day — steps must
     complete in sequence. The last step's window ends at the MPS anchor date.
  4. Within a step's window, fill day-by-day backward at that step's daily
     output capacity (workcenter capacity minutes ÷ step work_time minutes)
     for THAT specific day — capacity varies by day when equipment cycle_factor
     changes over time (see workcenter_capacity_minutes_on). Never schedule
     before today — any quantity that would land on a past day is merged
     entirely into today.
  5. Fractional carry: each day's allocation is floored; the accumulated
     fractional remainder is added onto the earliest day used (시작일 compensation).

This is a temporary/approximate calculation — each step assumes the full
workcenter capacity is available to it alone. KPI3 detects overload by
aggregating planned_qty × work_time across ALL steps sharing a workcenter/day
and comparing against that workcenter's real daily capacity.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_logger
from app.models import DailyPlan, Equipment, ItemRoutingSpec, MpsPlan, WorkCenter

logger = get_logger(__name__)


def _parse_g_date(value: str | None) -> date | None:
    """Parse G-System YYYYMMDD string → date, or None."""
    if not value or len(value) < 8:
        return None
    try:
        return date(int(value[0:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return None


def build_workcenter_capacity_index(session: Session) -> "WorkcenterCapacityIndex":
    """Load workcenter std_capa + equipment (with parsed validity windows).

    Returns an index object whose `.minutes_on(workcenter_id, day)` computes
    capacity for a specific day: std_capa × Σ(cycle_factor of the ONE
    currently-valid version per physical equipment_id on that day).
    """
    std_capa_by_wc: dict[int, float] = {
        wc.id: float(wc.std_capa) if wc.std_capa is not None else 0.0
        for wc in session.execute(select(WorkCenter)).scalars().all()
    }
    equipment_by_wc: dict[int, list[tuple[int, float, date | None, date | None]]] = defaultdict(list)
    for eq in session.execute(select(Equipment)).scalars().all():
        if eq.workcenter_id is None:
            continue
        key = eq.equipment_id if eq.equipment_id is not None else eq.id
        cf = float(eq.cycle_factor) if eq.cycle_factor is not None else 1.0
        equipment_by_wc[eq.workcenter_id].append(
            (key, cf, _parse_g_date(eq.valid_from), _parse_g_date(eq.valid_to))
        )
    return WorkcenterCapacityIndex(std_capa_by_wc, equipment_by_wc)


class WorkcenterCapacityIndex:
    """Per-day workcenter capacity lookup — see build_workcenter_capacity_index."""

    def __init__(
        self,
        std_capa_by_wc: dict[int, float],
        equipment_by_wc: dict[int, list[tuple[int, float, date | None, date | None]]],
    ) -> None:
        self._std_capa_by_wc = std_capa_by_wc
        self._equipment_by_wc = equipment_by_wc

    def minutes_on(self, workcenter_id: int, on_date: date) -> float:
        std_capa = self._std_capa_by_wc.get(workcenter_id, 0.0)
        rows = self._equipment_by_wc.get(workcenter_id)
        if not rows:
            return std_capa * 1.0

        # One physical machine (equipment_id) can have several time-versioned
        # rows (cycle_factor changed over time) — pick only the version valid
        # on `on_date`, never sum multiple versions of the same machine.
        active_cf_by_equipment: dict[int, float] = {}
        active_vf_by_equipment: dict[int, date] = {}
        for key, cf, valid_from, valid_to in rows:
            if valid_from is not None and on_date < valid_from:
                continue
            if valid_to is not None and on_date > valid_to:
                continue
            best_vf = active_vf_by_equipment.get(key)
            this_vf = valid_from or date.min
            if best_vf is None or this_vf >= best_vf:
                active_cf_by_equipment[key] = cf
                active_vf_by_equipment[key] = this_vf

        if not active_cf_by_equipment:
            return std_capa * 1.0
        return std_capa * sum(active_cf_by_equipment.values())


def _anchor_end_date(mps: MpsPlan) -> date | None:
    """작업종료일자(prod_end_date) if status=created and set, else 종료일자(plan_end_date)."""
    if mps.status_cd == "created" and mps.prod_end_date is not None:
        return mps.prod_end_date
    return mps.plan_end_date


def _backward_fill_step(
    *, qty: float, window_end: date, daily_capacity_qty_on: Callable[[date], float], today: date,
) -> tuple[dict[date, float], date]:
    """Backward-fill `qty` from `window_end`, at each day's own capacity.

    Never schedules before `today` — any remainder that would land earlier is
    merged into today. Returns ({date: qty}, earliest_date_used).
    """
    allocations: dict[date, float] = defaultdict(float)
    remaining = qty
    day = window_end
    carry_fraction = 0.0
    last_day_used = window_end

    while remaining > 1e-9 and day >= today:
        day_capacity = daily_capacity_qty_on(day)
        if day_capacity <= 0:
            day -= timedelta(days=1)
            continue
        alloc = min(remaining, day_capacity)
        floored = math.floor(alloc)
        carry_fraction += alloc - floored
        allocations[day] += floored
        remaining -= alloc
        last_day_used = day
        day -= timedelta(days=1)

    if remaining > 1e-9:
        # Would land before today — merge entirely into today instead.
        allocations[today] += remaining
        last_day_used = min(last_day_used, today)

    if carry_fraction > 1e-9:
        allocations[last_day_used] += round(carry_fraction, 2)

    return dict(allocations), last_day_used


def rebuild_daily_plan(session: Session) -> int:
    """Wipe and rebuild aps_daily_plan from aps_mps_plan × aps_item_routing_spec.

    Rows with `adjusted=True` (set by POST /aps/adjust) are preserved instead of
    wiped — a manual override must survive a G-System resync. Any
    (mps_plan_id, item_routing_id) group with a surviving adjusted row is
    skipped entirely (not regenerated), so the schedule isn't half hand-edited/
    half backward-filled. Adjusted rows still feed the overload second pass so
    their capacity usage is accounted for.

    Returns rows inserted (adjusted rows kept from a prior run are not counted).
    Caller owns commit.
    """
    today = date.today()
    capacity_index = build_workcenter_capacity_index(session)

    mps_lines = session.execute(
        select(MpsPlan).where(MpsPlan.item_id.isnot(None), MpsPlan.plan_qty.isnot(None))
    ).scalars().all()

    routing_steps_by_item: dict[int, list[ItemRoutingSpec]] = defaultdict(list)
    for step in session.execute(select(ItemRoutingSpec)).scalars().all():
        if step.item_id is not None:
            routing_steps_by_item[step.item_id].append(step)
    for steps in routing_steps_by_item.values():
        steps.sort(key=lambda s: s.proc_sno if s.proc_sno is not None else 0)

    session.query(DailyPlan).filter(DailyPlan.adjusted.is_(False)).delete(synchronize_session=False)
    session.flush()

    adjusted_groups: set[tuple[int, int]] = set()
    required_minutes_by_slot: dict[tuple[int, date], float] = defaultdict(float)
    rows_by_slot: dict[tuple[int, date], list[DailyPlan]] = defaultdict(list)
    work_time_by_routing_id: dict[int, float] = {
        step.id: float(step.work_time) / 60.0
        for steps in routing_steps_by_item.values() for step in steps if step.work_time
    }
    for row in session.execute(select(DailyPlan).where(DailyPlan.adjusted.is_(True))).scalars().all():
        adjusted_groups.add((row.mps_plan_id, row.item_routing_id))
        wtm = work_time_by_routing_id.get(row.item_routing_id, 0.0)
        if wtm > 0:
            slot = (row.workcenter_id, row.work_date)
            required_minutes_by_slot[slot] += float(row.planned_qty) * wtm
            rows_by_slot[slot].append(row)

    inserted = 0
    for mps in mps_lines:
        anchor = _anchor_end_date(mps)
        if anchor is None or not mps.plan_qty or float(mps.plan_qty) <= 0:
            continue
        plan_qty = float(mps.plan_qty)

        steps = routing_steps_by_item.get(mps.item_id, [])
        if mps.routing_id is not None:
            matching = [s for s in steps if s.routing_id == mps.routing_id]
            if matching:
                steps = matching
        if not steps:
            continue
        # Any step already hand-adjusted for this MPS line — skip the whole
        # line so a partial regeneration doesn't fight the adjustment.
        if any((mps.id, step.id) in adjusted_groups for step in steps):
            continue

        window_end = anchor
        for step in reversed(steps):  # highest proc_sno first — last step finishes at anchor
            if step.workcenter_id is None or not step.work_time:
                continue
            work_time_minutes = float(step.work_time) / 60.0
            if work_time_minutes <= 0:
                continue
            wc_id = step.workcenter_id

            def _daily_qty_on(day: date, _wc_id: int = wc_id, _wtm: float = work_time_minutes) -> float:
                return capacity_index.minutes_on(_wc_id, day) / _wtm

            allocations, earliest_day = _backward_fill_step(
                qty=plan_qty, window_end=window_end, daily_capacity_qty_on=_daily_qty_on, today=today,
            )
            for work_date, qty in allocations.items():
                if qty <= 0:
                    continue
                persisted_qty = round(qty, 2)
                row = DailyPlan(
                    mps_plan_id=mps.id,
                    item_routing_id=step.id,
                    workcenter_id=step.workcenter_id,
                    work_date=work_date,
                    planned_qty=persisted_qty,
                    status="normal",
                )
                session.add(row)
                slot = (step.workcenter_id, work_date)
                required_minutes_by_slot[slot] += persisted_qty * work_time_minutes
                rows_by_slot[slot].append(row)
                inserted += 1

            window_end = max(today, earliest_day - timedelta(days=1))

    # Second pass: a (workcenter, day) slot is overloaded when the total
    # required minutes across ALL steps sharing it exceeds real daily
    # capacity — only knowable after every MPS line has been processed.
    for (wc_id, work_date), required in required_minutes_by_slot.items():
        capacity = capacity_index.minutes_on(wc_id, work_date)
        if capacity > 0 and required > capacity:
            for row in rows_by_slot[(wc_id, work_date)]:
                row.status = "overload"

    session.flush()
    logger.info("rebuild_daily_plan: %d rows across %d MPS lines", inserted, len(mps_lines))
    return inserted

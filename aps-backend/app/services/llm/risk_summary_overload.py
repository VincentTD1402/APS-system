"""공정 부하율 초과 across the work plans currently on screen."""
from __future__ import annotations

from datetime import date as date_cls

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyPlan
from app.schemas.work_plan import WorkPlanRow
from app.schemas.work_plan_recommendation import OverloadDay, WorkcenterOverload
from app.services.kpi_summary.daily_plan_rollup import workcenter_daily_status_rollup


def workcenters_in_scope(
    db: Session, mps_ids: set[int], start: date_cls | None, end: date_cls | None
) -> set[int]:
    """Workcenters the listed plans actually load inside the window.

    Keeps the summary about what the user filtered to: a workcenter busy with
    plans outside the current filter is not part of this analysis.
    """
    if not mps_ids:
        return set()
    stmt = select(DailyPlan.workcenter_id).where(DailyPlan.mps_plan_id.in_(mps_ids))
    if start is not None:
        stmt = stmt.where(DailyPlan.work_date >= start)
    if end is not None:
        stmt = stmt.where(DailyPlan.work_date <= end)
    return {wc for (wc,) in db.execute(stmt).all() if wc is not None}


def build_overload_facts(
    db: Session,
    *,
    workcenter_ids: set[int],
    start: date_cls | None,
    end: date_cls | None,
) -> tuple[list[WorkcenterOverload], dict[int, set[date_cls]]]:
    """Per-workcenter overload breakdown, heaviest workcenter first.

    Returns the display models plus a {workcenter_id: overloaded days} index the
    caller uses to decide which plans are affected.

    `load_percent` is the whole cell's load — every plan running on that
    workcenter that day, including ones outside the current filter. Capacity is
    shared, so that is the honest figure; the narrative must therefore speak of
    workcenter overload, never blame a single instruction.
    """
    if not workcenter_ids:
        return [], {}

    out: list[WorkcenterOverload] = []
    days_by_wc: dict[int, set[date_cls]] = {}

    for wc_id in workcenter_ids:
        slots = workcenter_daily_status_rollup(
            db,
            workcenter_id=wc_id,
            start_date=start.isoformat() if start else None,
            end_date=end.isoformat() if end else None,
        )
        # 'urgent' is overload + material shortage on the same day — still an overload.
        over = sorted(
            (s for s in slots if s.status in ("overload", "urgent")),
            key=lambda s: s.load_percent,
            reverse=True,
        )
        if not over:
            continue
        days_by_wc[wc_id] = {s.work_date for s in over}
        out.append(
            WorkcenterOverload(
                workcenter_no=over[0].workcenter_no,
                workcenter_name=over[0].workcenter_name,
                overload_days=[
                    OverloadDay(
                        work_date=s.work_date,
                        load_percent=s.load_percent,
                        used_minutes=s.used_minutes,
                        capacity_minutes=s.capacity_minutes,
                    )
                    for s in over
                ],
                overload_day_count=len(over),
                peak_day=over[0].work_date,
                peak_load_percent=over[0].load_percent,
            )
        )

    out.sort(key=lambda w: w.peak_load_percent, reverse=True)
    return out, days_by_wc


def plans_hit_by_overload(
    db: Session,
    rows: list[WorkPlanRow],
    mps_by_row: dict[str, int],
    days_by_wc: dict[int, set[date_cls]],
) -> set[str]:
    """Row ids whose plan loads at least one overloaded (workcenter, day) cell."""
    if not days_by_wc:
        return set()

    all_days = {d for days in days_by_wc.values() for d in days}
    mps_ids = set(mps_by_row.values())
    if not mps_ids or not all_days:
        return set()

    loaded = db.execute(
        select(DailyPlan.mps_plan_id, DailyPlan.workcenter_id, DailyPlan.work_date).where(
            DailyPlan.mps_plan_id.in_(mps_ids),
            DailyPlan.work_date.in_(all_days),
        )
    ).all()
    hit_mps = {
        mps_id
        for mps_id, wc_id, day in loaded
        if day in days_by_wc.get(wc_id, ())
    }
    return {row.id for row in rows if mps_by_row.get(row.id) in hit_mps}

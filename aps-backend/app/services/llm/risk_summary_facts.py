"""Deterministic risk summary for the AI제안 panel.

Summarises the WHOLE work plan list currently on screen — same filters as
GET /work-plan/list. Selecting a row does not change it; only the Action card
below the panel is row-scoped.

Every figure the panel shows is computed here, from aps_daily_plan and
aps_material_shortage. The LLM downstream receives this as read-only prompt
context and may only add prose; it never supplies a number, an ID or a date.
That split is what keeps the panel trustworthy when the model hallucinates.
"""
from __future__ import annotations

from datetime import date as date_cls

from sqlalchemy.orm import Session

from app.config import get_logger
from app.schemas.work_plan import WorkPlanRow
from app.schemas.work_plan_recommendation import (
    SAMPLE_MAX,
    AffectedPlanRef,
    AffectedPlans,
    RiskSummaryFacts,
    RiskTotals,
    Severity,
    Urgency,
    WorkcenterOverload,
)
from app.services.llm.risk_summary_lookups import (
    days_from_today,
    mps_ids_by_row,
    plan_window,
)
from app.services.llm.risk_summary_overload import (
    build_overload_facts,
    plans_hit_by_overload,
    workcenters_in_scope,
)
from app.services.llm.risk_summary_shortage import (
    build_shortage_components,
    plans_hit_by_shortage,
)
from app.services.scheduling.work_plan_list import build_work_plan_list

logger = get_logger(__name__)

# Load above capacity is already a risk; 150% is where rescheduling stops being
# optional (a full extra shift cannot absorb it).
_CRITICAL_LOAD_PERCENT = 150.0
_WARNING_LOAD_PERCENT = 100.0

# Delivery within this many days counts as DUE_SOON.
_DUE_SOON_DAYS = 3


def _severity(
    workcenters: list[WorkcenterOverload], has_shortage: bool, both: bool
) -> Severity:
    """Worst-case grade for the FE badge and the LLM prompt.

    Both risk kinds present at once is CRITICAL regardless of load: a shortage
    blocks production outright, so rescheduling alone cannot recover the plan.
    """
    peak = workcenters[0].peak_load_percent if workcenters else 0.0
    if both or peak >= _CRITICAL_LOAD_PERCENT:
        return "CRITICAL"
    if peak >= _WARNING_LOAD_PERCENT or has_shortage:
        return "WARNING"
    return "LOW"


def _urgency(delivery_date: date_cls | None) -> tuple[Urgency, int | None]:
    """Delivery pressure of the most urgent affected plan."""
    days = days_from_today(delivery_date)
    if days is None:
        return "UNKNOWN", None
    if days < 0:
        return "OVERDUE", days
    if days == 0:
        return "DUE_TODAY", days
    if days <= _DUE_SOON_DAYS:
        return "DUE_SOON", days
    return "NORMAL", days


def _affected(rows: list[WorkPlanRow], hit_ids: set[str]) -> AffectedPlans:
    """영향받는 오더 — every hit plan counted, a capped sample carried."""
    hits = [r for r in rows if r.id in hit_ids]
    # Soonest delivery first: the sample should show what needs attention now.
    hits.sort(key=lambda r: (r.delivery_date is None, r.delivery_date))
    return AffectedPlans(
        count=len(hits),
        sample=[
            AffectedPlanRef(
                id=r.id,
                work_order_no=r.work_order_no,
                tmp_plan_no=r.tmp_plan_no,
                order_no=r.order_no,
                item_no=r.item_no,
                workcenter_no=r.workcenter_no,
                delivery_date=r.delivery_date,
                risk_types=r.risk_types,
            )
            for r in hits[:SAMPLE_MAX]
        ],
    )


def build_risk_summary_facts(
    db: Session,
    *,
    workcenter_no: str | None = None,
    item_no: str | None = None,
    risk_type: str | None = None,
    plan_no: str | None = None,
    date_from: date_cls | None = None,
    date_to: date_cls | None = None,
) -> RiskSummaryFacts:
    """Collect every deterministic figure behind the AI제안 narrative.

    Filters mirror GET /work-plan/list so the summary always describes exactly
    the rows the user is looking at. An empty or risk-free list returns valid
    facts with zero totals — the caller can render the panel without the LLM.
    """
    rows = build_work_plan_list(
        db,
        workcenter_no=workcenter_no,
        item_no=item_no,
        risk_type=risk_type,
        plan_no=plan_no,
        date_from=date_from,
        date_to=date_to,
    )
    start, end = plan_window(rows)
    mps_by_row = mps_ids_by_row(db, rows)

    wc_ids = workcenters_in_scope(db, set(mps_by_row.values()), start, end)
    workcenters, days_by_wc = build_overload_facts(
        db, workcenter_ids=wc_ids, start=start, end=end
    )

    # Risk membership is derived from aps_daily_plan directly, never from
    # row.risk_types: that label keeps only one risk per plan (a shortage on one
    # day suppresses an overload on another) because the grid cell shows a single
    # colour. The panel must describe what is actually there.
    overload_ids = plans_hit_by_overload(db, rows, mps_by_row, days_by_wc)
    shortage_ids = plans_hit_by_shortage(db, rows, mps_by_row)
    shortages = build_shortage_components(db, rows)

    affected = _affected(rows, overload_ids | shortage_ids)
    earliest = next(
        (r.delivery_date for r in affected.sample if r.delivery_date is not None), None
    )
    urgency, days_to_delivery = _urgency(earliest)
    peak_day = workcenters[0].peak_day if workcenters else None

    facts = RiskSummaryFacts(
        window_start=start,
        window_end=end,
        totals=RiskTotals(
            total_plans=len(rows),
            risk_plans=affected.count,
            overload_plans=len(overload_ids),
            shortage_plans=len(shortage_ids),
            overloaded_workcenters=len(workcenters),
        ),
        workcenters=workcenters,
        affected=affected,
        shortages=shortages,
        severity=_severity(
            workcenters,
            has_shortage=bool(shortage_ids or shortages),
            both=bool(overload_ids and shortage_ids),
        ),
        urgency=urgency,
        earliest_delivery_date=earliest,
        days_to_earliest_delivery=days_to_delivery,
        days_to_peak_overload=days_from_today(peak_day),
    )
    logger.info(
        "risk summary: plans=%d risk=%d overload=%d shortage=%d wc=%d severity=%s urgency=%s",
        facts.totals.total_plans,
        facts.totals.risk_plans,
        facts.totals.overload_plans,
        facts.totals.shortage_plans,
        facts.totals.overloaded_workcenters,
        facts.severity,
        facts.urgency,
    )
    return facts

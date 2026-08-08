"""Schemas for the AI제안 panel (plan-wide risk summary).

camelCase like app/schemas/aps.py — the FE Work Plan view consumes these
alongside WorkPlanOut, so both sides share one casing convention.

Scope: the panel summarises the WHOLE work plan list currently on screen (same
filters as GET /work-plan/list), not the selected row. Selecting a row changes
only the Action card below it.

Everything here is deterministic: values are computed from aps_daily_plan and
aps_material_shortage by app.services.llm.risk_summary_facts. The LLM never
writes into these fields — it only reads them as prompt input.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field

from app.schemas.aps import CamelModel

Severity = Literal["CRITICAL", "WARNING", "LOW"]
Urgency = Literal["OVERDUE", "DUE_TODAY", "DUE_SOON", "NORMAL", "UNKNOWN"]

# Cap on the sample lists handed to the FE/LLM. Full counts are reported
# separately so a capped list never reads as "only this many".
SAMPLE_MAX = 10


class OverloadDay(CamelModel):
    """One overloaded day of one workcenter, from the aps_daily_plan rollup."""

    work_date: date
    load_percent: float = Field(..., description="used_minutes / capacity_minutes × 100")
    used_minutes: float
    capacity_minutes: float


class WorkcenterOverload(CamelModel):
    """공정 부하율 초과 for one workcenter inside the current plan window."""

    workcenter_no: str | None = None
    workcenter_name: str | None = None
    overload_days: list[OverloadDay] = Field(
        default_factory=list, description="Overloaded days, load_percent descending"
    )
    overload_day_count: int = 0
    peak_day: date | None = None
    peak_load_percent: float = 0.0


class AffectedPlanRef(CamelModel):
    """One work plan hit by an overloaded cell or a material shortage."""

    id: str = Field(..., description="work_order.id — same key as WorkPlanRow.id")
    work_order_no: str | None = Field(None, description="작업지시번호 — WO rows only")
    tmp_plan_no: str | None = Field(None, description="(임시)작업계획번호 — MPS rows only")
    order_no: str | None = Field(None, description="오더")
    item_no: str | None = None
    workcenter_no: str | None = None
    delivery_date: date | None = Field(None, description="납기일자")
    risk_types: list[str] = Field(default_factory=list)


class AffectedPlans(CamelModel):
    """영향받는 오더 — full count plus a capped sample."""

    count: int = 0
    sample: list[AffectedPlanRef] = Field(default_factory=list)


class ShortageComponent(CamelModel):
    """One raw material short across the plans on screen (aps_material_shortage)."""

    parent_item_no: str | None = Field(None, description="품목 — the product needing it")
    item_no: str | None = Field(None, description="자재 코드")
    item_name: str | None = Field(None, description="자재명")
    required_qty: float = Field(..., description="소요예정")
    available_qty: float = Field(..., description="현재고")
    shortage_qty: float = Field(..., description="부족수량")


class RiskTotals(CamelModel):
    """Headline counts — these mirror what the KPI cards above the panel show."""

    total_plans: int = 0
    risk_plans: int = Field(0, description="Plans carrying any risk")
    overload_plans: int = 0
    shortage_plans: int = 0
    overloaded_workcenters: int = 0


class RiskSummaryFacts(CamelModel):
    """Deterministic input for the AI제안 narrative — the whole list, not one row."""

    window_start: date | None = Field(None, description="Earliest planned day in scope")
    window_end: date | None = Field(None, description="Latest planned day in scope")
    totals: RiskTotals = Field(default_factory=RiskTotals)
    workcenters: list[WorkcenterOverload] = Field(
        default_factory=list, description="Overloaded workcenters, peak_load_percent descending"
    )
    affected: AffectedPlans = Field(default_factory=AffectedPlans)
    shortages: list[ShortageComponent] = Field(default_factory=list)

    severity: Severity = "LOW"
    urgency: Urgency = "UNKNOWN"
    earliest_delivery_date: date | None = Field(
        None, description="Soonest 납기일자 among affected plans — what urgency is graded on"
    )
    days_to_earliest_delivery: int | None = None
    days_to_peak_overload: int | None = Field(
        None, description="Days from today to the heaviest overloaded day (negative = past)"
    )


class RecommendationItem(CamelModel):
    """One 우선순위 line of 해결 및 완화 권고 — written by the LLM."""

    priority: int = Field(..., ge=1, description="1 = act on this first")
    text: str


class RiskNarrative(CamelModel):
    """The prose half of the panel. Every field here is LLM-written.

    Numbers stay in RiskSummaryFacts; these strings only describe them, so a
    hallucinated figure can never reach a field the UI renders as data.
    """

    root_cause: str = Field("", description="1. 영향(Impact)의 근본 원인")
    impact_summary: str = Field("", description="2. 영향받는 오더 및 작업장(WO) 및 심각도")
    recommendations: list[RecommendationItem] = Field(
        default_factory=list, description="3. 해결 및 완화 권고"
    )


class RiskRecommendation(CamelModel):
    """Response of the AI제안 endpoints: deterministic facts + narrative.

    The narrative is LLM-written when the model is reachable and its figures
    check out, and falls back to a deterministic Korean template otherwise. The
    panel renders both the same way, so which one produced the text is a server
    concern (it decides what may be cached) and is not part of this contract.
    """

    facts: RiskSummaryFacts
    narrative: RiskNarrative
    rejected_numbers: list[str] = Field(
        default_factory=list,
        description="Figures the LLM invented that failed the numeric guard, if any",
    )

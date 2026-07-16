"""Pydantic schemas for LLM API endpoints."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SuggestionRequest(BaseModel):
    """Request body for POST /llm/suggestions."""

    context_type: str
    scenario_id: str | None = None
    workcenter_id: str | None = None
    affected_items: list[str] = Field(default_factory=list)
    kpi_summary: dict = Field(default_factory=dict)
    max_suggestions: int = 3


class AlertItemOut(BaseModel):
    """APS alert card item for dashboard."""

    level: Literal["주의", "경고", "🔴", "🟠"]
    message: str
    context: dict[str, Any] = Field(default_factory=dict)
    ai_insight: str
    priority: Literal["high", "medium", "low"]


class SuggestionResponse(BaseModel):
    """Response for POST /llm/suggestions."""

    alerts: list[AlertItemOut] = Field(default_factory=list)
    context_type: str
    config_used: str = "no_think"


class PlanDetailItemOut(BaseModel):
    """One structured impact block — type is Korean label for FE."""

    type: Literal["계획납기준수율", "공정투입자재부족", "공정부하율"]
    target: dict[str, Any] = Field(
        default_factory=dict,
        description="Target entity for this item (demand/order/material/workcenter)",
    )
    impact_summary: str = Field(..., description="Short summary of the impact")
    kpi_value: dict[str, Any] = Field(
        default_factory=dict,
        description="Metrics: order → dates/late_days; material → shortage/need_date; line → overload_percent",
    )


class PlanDetailSingleResult(BaseModel):
    """Response for POST /llm/plans/{plan_id}/detail and one entry in batch."""

    plan_id: str
    impacted_ids: list[str] = Field(
        default_factory=list,
        description="Primary keys from `plan_impacted_order` for this plan_id",
    )
    items: list[PlanDetailItemOut] = Field(default_factory=list)
    llm_detail: str | None = Field(
        None, description="Markdown analysis from LLM (parallel per plan in batch)"
    )
    reason_types: list[str] = Field(
        default_factory=list,
        description="Raw reason_type values from plan_impacted_order",
    )
    severity: str | None = Field(
        None,
        description="Highest CRITICAL/WARNING/LOW derived from impacts or priority_score",
    )
    error: str | None = Field(
        None,
        description="Set when plan_id was missing or load failed (batch continues)",
    )


class PlanDetailBatchRequest(BaseModel):
    """Body for POST /llm/plans/detail — pass multiple plan_ids (e.g. from KPI plan-impacted-orders)."""

    plan_ids: list[str] = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Plan IDs to analyze in parallel (from GET .../kpi-summary/{scenario_id}/plan-impacted-orders)",
    )
    scenario_id: str | None = Field(
        None,
        description=(
            "Optional scenario for llm_response_cache; if omitted, server resolves scenario_id "
            "from aps_result.plan_order for each plan_id so DB cache still applies."
        ),
    )
    refresh: bool = Field(
        False,
        description=(
            "If true, bypass llm_response_cache for this request and re-run the LLM, "
            "then overwrite the cache row. Defaults to false (cache-first)."
        ),
    )


class PlanDetailBatchResponse(BaseModel):
    """Response for POST /llm/plans/detail."""

    results: list[PlanDetailSingleResult]


# Same schema as PlanDetailSingleResult — keeps legacy imports working after rename.
PlanDetailResponse = PlanDetailSingleResult

"""LLM routes — AI suggestions and the AI제안 (work-plan risk summary) panel."""
from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import date as date_cls

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.config import get_logger
from app.db.database import get_db
from app.schemas.llm import SuggestionRequest, SuggestionResponse
from app.schemas.work_plan_recommendation import RiskRecommendation
from app.services.llm import build_risk_summary_facts, get_cached_chat_service, SuggestionService
from app.services.llm.llm_cache import (
    CACHE_RISK_SUMMARY,
    CACHE_SUGGESTION,
    LIVE_SCENARIO,
    get_cached_response,
    set_cached_response,
)
from app.services.llm.concurrency import (
    LLM_PLAN_DETAIL_TIMEOUT_S,
    llm_plan_detail_semaphore,
)
from app.services.llm.risk_narrative import generate_narrative

logger = get_logger(__name__)
router = APIRouter()


def _filter_cache_key(filters: dict) -> str:
    """Stable key for one filter combination.

    The summary describes whatever the filters select, so the filters *are* the
    identity of the answer. Sorted JSON keeps the hash independent of argument
    order.
    """
    canonical = json.dumps(filters, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()[:32]


def _parse_date(value: str | None, field: str) -> date_cls | None:
    if not value:
        return None
    try:
        return date_cls.fromisoformat(value)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"{field} must be YYYY-MM-DD") from e


@router.post("/suggestions", response_model=SuggestionResponse)
async def generate_suggestions(
    payload: SuggestionRequest,
    db: Session = Depends(get_db),
) -> SuggestionResponse:
    """Generate AI action suggestions from schedule/KPI context. Cached per scenario_id."""
    rid = None
    if payload.scenario_id:
        cached = get_cached_response(db, payload.scenario_id, CACHE_SUGGESTION, payload.scenario_id)
        if cached:
            return SuggestionResponse(**cached)

    try:
        service = SuggestionService()
        sem = llm_plan_detail_semaphore()
        async with sem:
            alerts = await asyncio.wait_for(
                service.generate(payload, db),
                timeout=LLM_PLAN_DETAIL_TIMEOUT_S,
            )
        response = SuggestionResponse(
            alerts=alerts,
            context_type=payload.context_type,
        )

        if payload.scenario_id:
            set_cached_response(
                db, payload.scenario_id, CACHE_SUGGESTION,
                payload.scenario_id, response.model_dump(mode="json"),
            )

        return response
    except asyncio.TimeoutError as e:
        logger.warning("generate_suggestions timeout scenario=%s", payload.scenario_id)
        raise HTTPException(status_code=503, detail="LLM timeout") from e
    except Exception as e:
        logger.exception("generate_suggestions error: %s", e)
        raise HTTPException(status_code=503, detail="LLM unavailable") from e


@router.get(
    "/work-plan-risk-summary",
    response_model=RiskRecommendation,
    summary="AI suggestion panel — plan risk summary and recommendations",
    description=(
        "Risk summary for the work plan list currently on screen. Filters mirror "
        "GET /work-plan/list, so the analysis always describes exactly the rows the "
        "user is looking at; selecting a row does not change it.\n\n"
        "`facts` is computed from aps_daily_plan / aps_material_shortage — every number "
        "shown comes from there. `narrative` is Korean prose over those facts; it never "
        "supplies a figure. The prose comes from the LLM when the model is reachable and "
        "its figures check out, and from a deterministic template otherwise, so the "
        "response shape never changes. Figures the LLM invented — and which were therefore "
        "discarded — are listed in `rejectedNumbers`.\n\n"
        "Call POST /kpi-summary/daily-plan/rebuild first so the risk data is fresh."
    ),
)
async def get_work_plan_risk_summary(
    workcenter_no: str | None = Query(None, description="Filter by work center no"),
    item_no: str | None = Query(None, description="Filter by item no"),
    risk_type: str | None = Query(
        None, description="Keep rows whose risk_types contains this ('overload', 'material_short')"
    ),
    plan_no: str | None = Query(None, description="Match tmp_plan_no / work_order_no / order_no"),
    date_from: str | None = Query(None, description="Keep rows with mps_completion_date >= (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="Keep rows with mps_completion_date <= (YYYY-MM-DD)"),
    refresh: bool = Query(False, description="Bypass the cache and re-run the LLM"),
    db: Session = Depends(get_db),
) -> RiskRecommendation:
    filters = {
        "workcenter_no": workcenter_no,
        "item_no": item_no,
        "risk_type": risk_type,
        "plan_no": plan_no,
        "date_from": date_from,
        "date_to": date_to,
    }
    cache_key = _filter_cache_key(filters)

    if not refresh:
        cached = get_cached_response(db, LIVE_SCENARIO, CACHE_RISK_SUMMARY, cache_key)
        if cached:
            return RiskRecommendation(**cached)

    # build_risk_summary_facts is synchronous DB work — keep it off the event loop.
    facts = await run_in_threadpool(
        build_risk_summary_facts,
        db,
        workcenter_no=workcenter_no,
        item_no=item_no,
        risk_type=risk_type,
        plan_no=plan_no,
        date_from=_parse_date(date_from, "date_from"),
        date_to=_parse_date(date_to, "date_to"),
    )

    narrative, generated_by, rejected = await generate_narrative(facts)
    response = RiskRecommendation(
        facts=facts,
        narrative=narrative,
        rejected_numbers=rejected,
    )

    # Only cache real LLM prose. Caching a template would freeze a degraded answer
    # in place long after the model came back up. `generated_by` stays a server-side
    # signal — the response contract does not expose it.
    if generated_by == "llm":
        set_cached_response(
            db, LIVE_SCENARIO, CACHE_RISK_SUMMARY, cache_key,
            response.model_dump(mode="json", by_alias=True),
        )

    return response


@router.get("/health")
async def llm_health() -> dict:
    """Health check for LLM service — always returns 200 with status healthy/degraded."""
    results = {}
    for name in ("no_think", "think"):
        try:
            svc = get_cached_chat_service(name)
            results[name] = await svc.health_check()
        except Exception as e:
            results[name] = {"status": "unhealthy", "error": str(e)}
    overall = "healthy" if all(r.get("status") == "healthy" for r in results.values()) else "degraded"
    return {"status": overall, "configs": results}

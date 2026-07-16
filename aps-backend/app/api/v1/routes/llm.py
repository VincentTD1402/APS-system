"""LLM routes — AI suggestions."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_logger
from app.db.database import get_db
from app.schemas.llm import SuggestionRequest, SuggestionResponse
from app.services.llm import get_cached_chat_service, SuggestionService
from app.services.llm.llm_cache import (
    CACHE_SUGGESTION,
    get_cached_response,
    set_cached_response,
)
from app.services.llm.concurrency import (
    LLM_PLAN_DETAIL_TIMEOUT_S,
    llm_plan_detail_semaphore,
)

logger = get_logger(__name__)
router = APIRouter()


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

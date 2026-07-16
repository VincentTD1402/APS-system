"""LLM response cache — read/write helpers for llm_response_cache table."""
from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import get_logger
from app.models.output.llm_response_cache import LlmResponseCache

logger = get_logger(__name__)

# Cache type constants
CACHE_SUGGESTION = "SUGGESTION"
CACHE_PLAN_DETAIL = "PLAN_DETAIL"
# Serialized ActionCardResponse (actions/generate) — keyed by impacted_id
CACHE_ACTION_GENERATE = "ACTION_GENERATE"


def get_cached_response(
    db: Session,
    scenario_id: str,
    cache_type: str,
    cache_key: str,
) -> Any | None:
    """Return cached response_json or None if not found (dict or list JSON)."""
    row = db.execute(
        select(LlmResponseCache.response_json).where(
            LlmResponseCache.scenario_id == scenario_id,
            LlmResponseCache.cache_type == cache_type,
            LlmResponseCache.cache_key == cache_key,
        )
    ).scalar_one_or_none()
    if row is not None:
        logger.info("LLM cache HIT: %s/%s/%s", scenario_id, cache_type, cache_key)
    return row


def set_cached_response(
    db: Session,
    scenario_id: str,
    cache_type: str,
    cache_key: str,
    response_json: dict | list,
) -> None:
    """Upsert cached response (insert or update on conflict)."""
    try:
        stmt = pg_insert(LlmResponseCache).values(
            scenario_id=scenario_id,
            cache_type=cache_type,
            cache_key=cache_key,
            response_json=response_json,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["scenario_id", "cache_type", "cache_key"],
            set_={"response_json": stmt.excluded.response_json},
        )
        db.execute(stmt)
        db.commit()
        logger.info("LLM cache SET: %s/%s/%s", scenario_id, cache_type, cache_key)
    except Exception:
        db.rollback()
        logger.warning(
            "LLM cache SET failed (FK? scenario not in plan_scenario): %s/%s/%s",
            scenario_id, cache_type, cache_key,
        )


def invalidate_scenario_cache(db: Session, scenario_id: str) -> int:
    """Delete all cached LLM responses for a scenario. Returns deleted count."""
    result = db.execute(
        delete(LlmResponseCache).where(
            LlmResponseCache.scenario_id == scenario_id,
        )
    )
    db.commit()
    count = result.rowcount
    if count > 0:
        logger.info("LLM cache INVALIDATED: scenario=%s, deleted=%d", scenario_id, count)
    return count

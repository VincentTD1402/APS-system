"""APS Local DB — LLM response cache.

Caches LLM-generated responses (suggestions, plan details) per scenario
to avoid redundant LLM calls on page reload. Invalidated when scenario re-runs.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class LlmResponseCache(Base):
    """Cached LLM response keyed by (scenario_id, cache_type, cache_key).

    cache_type: SUGGESTION | PLAN_DETAIL | ACTION_GENERATE
    cache_key:  scenario_id for SUGGESTION; plan_id for PLAN_DETAIL; impacted_id for ACTION_GENERATE
    """

    __tablename__ = "llm_response_cache"
    __table_args__ = (
        Index(
            "uq_llm_cache_scenario_type_key",
            "scenario_id", "cache_type", "cache_key",
            unique=True,
        ),
        {"schema": "aps_result"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scenario_id: Mapped[str] = mapped_column(
        ForeignKey("aps_result.plan_scenario.scenario_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cache_type: Mapped[str] = mapped_column(String(20), nullable=False)
    cache_key: Mapped[str] = mapped_column(String(200), nullable=False)
    response_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

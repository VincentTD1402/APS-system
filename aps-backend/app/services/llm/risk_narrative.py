"""LLM narrative for the AI제안 panel — prose (per `lang`) over deterministic facts.

Three defences against a hallucinated figure reaching a planner:

1. Shape — vLLM `response_format={"type": "json_schema"}` masks tokens, so the
   reply is always valid JSON of the declared form.
2. Content — the prompt bans arithmetic and any figure outside the facts.
3. Audit — every number in the prose is checked against the facts; a reply
   quoting an invented one is discarded in favour of the template.

Numbers the UI renders as data live in RiskSummaryFacts and never come from
here, so even a reply that slips through all three cannot corrupt a KPI.
"""
from __future__ import annotations

import asyncio
import json

from app.config import get_logger
from app.schemas.work_plan_recommendation import (
    RecommendationItem,
    RiskNarrative,
    RiskSummaryFacts,
)
from app.services.llm.chat_service import ChatServiceError, get_cached_chat_service
from app.services.llm.concurrency import (
    LLM_PLAN_DETAIL_TIMEOUT_S,
    llm_plan_detail_semaphore,
)
from app.services.llm.risk_narrative_guard import (
    allowed_numbers,
    find_invented_numbers,
    narrative_text,
)
from app.services.llm.risk_narrative_i18n import DEFAULT_LANG, severity_label, template_strings
from app.services.llm.risk_narrative_prompt import (
    NARRATIVE_JSON_SCHEMA,
    USER_PROMPT,
    build_system_prompt,
)

logger = get_logger(__name__)

_MAX_RECOMMENDATIONS = 3


def build_template_narrative(facts: RiskSummaryFacts, lang: str = DEFAULT_LANG) -> RiskNarrative:
    """Deterministic fallback in `lang` — used when the LLM is skipped or rejected.

    Written from the same facts, so the panel degrades to plainer wording rather
    than to an empty block.
    """
    t = template_strings(lang)
    if not facts.workcenters and not facts.shortages:
        return RiskNarrative(
            root_cause=t["no_risk_root_cause"],
            impact_summary=t["no_risk_impact"],
            recommendations=[],
        )

    severity = severity_label(facts.severity, lang)
    causes: list[str] = [t["risk_detected"].format(severity=severity)]
    if facts.workcenters:
        worst = facts.workcenters[0]
        causes.append(t["overload_cause"].format(
            wc=worst.workcenter_no, day=worst.peak_day, pct=worst.peak_load_percent,
        ))
    if facts.shortages:
        short = facts.shortages[0]
        causes.append(t["shortage_cause"].format(
            item=short.item_no, available=short.available_qty, shortage=short.shortage_qty,
        ))

    wc_list = ", ".join(w.workcenter_no or "-" for w in facts.workcenters) or t["no_wc"]
    impact = t["impact_summary"].format(
        wc_list=wc_list, count=facts.affected.count, severity=severity, urgency=facts.urgency,
    )

    recs: list[RecommendationItem] = []
    if facts.workcenters:
        recs.append(RecommendationItem(priority=len(recs) + 1, text=t["rec_overload"]))
    if facts.shortages:
        recs.append(RecommendationItem(priority=len(recs) + 1, text=t["rec_shortage"]))
    recs.append(RecommendationItem(priority=len(recs) + 1, text=t["rec_priority"]))

    return RiskNarrative(
        root_cause=" ".join(causes),
        impact_summary=impact,
        recommendations=recs[:_MAX_RECOMMENDATIONS],
    )


def _to_narrative(payload: dict) -> RiskNarrative:
    items = []
    for raw in (payload.get("recommendations") or [])[:_MAX_RECOMMENDATIONS]:
        text = str((raw or {}).get("text") or "").strip()
        if not text:
            continue
        items.append(RecommendationItem(priority=len(items) + 1, text=text))
    return RiskNarrative(
        root_cause=str(payload.get("root_cause") or "").strip(),
        impact_summary=str(payload.get("impact_summary") or "").strip(),
        recommendations=items,
    )


async def generate_narrative(
    facts: RiskSummaryFacts, config_name: str = "no_think", lang: str = DEFAULT_LANG
) -> tuple[RiskNarrative, str, list[str]]:
    """Return (narrative, generated_by, rejected_numbers).

    `lang` is a GSystem language code (same as the FE's active locale) — both the
    LLM prompt's output-language directive and the deterministic template follow it.

    `generated_by` is "template" whenever the LLM was skipped, failed, timed
    out, or quoted a figure the facts do not support. The caller never has to
    handle an error path — the panel always gets renderable text in `lang`.
    """
    if not facts.workcenters and not facts.shortages:
        # Nothing to explain — spending an LLM call here would only invite invention.
        return build_template_narrative(facts, lang), "template", []

    payload = facts.model_dump(mode="json", by_alias=True)
    messages = [
        {"role": "system", "content": build_system_prompt(lang)},
        {
            "role": "user",
            "content": USER_PROMPT.format(
                facts=json.dumps(payload, ensure_ascii=False)
            ),
        },
    ]

    try:
        chat = get_cached_chat_service(config_name)
        async with llm_plan_detail_semaphore():
            raw = await asyncio.wait_for(
                chat.invoke_json(messages, NARRATIVE_JSON_SCHEMA, "risk_narrative"),
                timeout=LLM_PLAN_DETAIL_TIMEOUT_S,
            )
    except (asyncio.TimeoutError, ChatServiceError, ValueError, OSError) as e:
        logger.warning("risk narrative LLM unavailable (%s) — using template", e)
        return build_template_narrative(facts, lang), "template", []

    invented = find_invented_numbers(narrative_text(raw), allowed_numbers(payload))
    if invented:
        logger.warning(
            "risk narrative rejected — figures absent from facts: %s", invented
        )
        return build_template_narrative(facts, lang), "template", invented

    narrative = _to_narrative(raw)
    if not narrative.root_cause or not narrative.recommendations:
        logger.warning("risk narrative incomplete — using template")
        return build_template_narrative(facts, lang), "template", []

    return narrative, "llm", []

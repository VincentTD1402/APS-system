"""LLM narrative for the AI제안 panel — Korean prose over deterministic facts.

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
from app.services.llm.risk_narrative_prompt import (
    NARRATIVE_JSON_SCHEMA,
    SYSTEM_PROMPT,
    USER_PROMPT,
)

logger = get_logger(__name__)

_MAX_RECOMMENDATIONS = 3


def _severity_ko(severity: str) -> str:
    return {"CRITICAL": "심각", "WARNING": "주의"}.get(severity, "정상")


def build_template_narrative(facts: RiskSummaryFacts) -> RiskNarrative:
    """Deterministic Korean fallback — used when the LLM is skipped or rejected.

    Written from the same facts, so the panel degrades to plainer wording rather
    than to an empty block.
    """
    if not facts.workcenters and not facts.shortages:
        return RiskNarrative(
            root_cause="[정상] 현재 조회 범위에서 즉시 조치가 필요한 생산 리스크가 없습니다.",
            impact_summary="영향받는 작업지시가 없습니다.",
            recommendations=[],
        )

    causes: list[str] = [f"[{facts.severity}] 계획 리스크가 확인되었습니다."]
    if facts.workcenters:
        worst = facts.workcenters[0]
        causes.append(
            f"작업장 {worst.workcenter_no}의 {worst.peak_day} 부하율이 "
            f"{worst.peak_load_percent}%로 허용량을 초과했습니다."
        )
    if facts.shortages:
        short = facts.shortages[0]
        causes.append(
            f"자재 {short.item_no}의 현재고는 {short.available_qty}이며 "
            f"{short.shortage_qty}만큼 부족합니다."
        )

    wc_list = ", ".join(w.workcenter_no or "-" for w in facts.workcenters) or "없음"
    impact = (
        f"영향받는 작업장: {wc_list}. "
        f"영향받는 작업지시: {facts.affected.count}건. "
        f"심각도: {facts.severity} (긴급도: {facts.urgency})."
    )

    recs: list[RecommendationItem] = []
    if facts.workcenters:
        recs.append(RecommendationItem(
            priority=len(recs) + 1,
            text="과부하 작업장의 작업 일정을 조정하거나 여유 있는 작업장으로 재배분하십시오.",
        ))
    if facts.shortages:
        recs.append(RecommendationItem(
            priority=len(recs) + 1,
            text="부족 자재의 구매 요청 또는 대체 자재 가능 여부를 확인하십시오.",
        ))
    recs.append(RecommendationItem(
        priority=len(recs) + 1,
        text="납기가 임박한 작업지시부터 우선순위를 재검토하십시오.",
    ))

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
    facts: RiskSummaryFacts, config_name: str = "no_think"
) -> tuple[RiskNarrative, str, list[str]]:
    """Return (narrative, generated_by, rejected_numbers).

    `generated_by` is "template" whenever the LLM was skipped, failed, timed
    out, or quoted a figure the facts do not support. The caller never has to
    handle an error path — the panel always gets renderable Korean text.
    """
    if not facts.workcenters and not facts.shortages:
        # Nothing to explain — spending an LLM call here would only invite invention.
        return build_template_narrative(facts), "template", []

    payload = facts.model_dump(mode="json", by_alias=True)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
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
        return build_template_narrative(facts), "template", []

    invented = find_invented_numbers(narrative_text(raw), allowed_numbers(payload))
    if invented:
        logger.warning(
            "risk narrative rejected — figures absent from facts: %s", invented
        )
        return build_template_narrative(facts), "template", invented

    narrative = _to_narrative(raw)
    if not narrative.root_cause or not narrative.recommendations:
        logger.warning("risk narrative incomplete — using template")
        return build_template_narrative(facts), "template", []

    return narrative, "llm", []

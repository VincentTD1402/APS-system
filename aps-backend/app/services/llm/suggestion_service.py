"""SuggestionService — generate APS action suggestions from schedule/KPI context."""
from __future__ import annotations

import json
import re

from app.config import get_logger
from app.models.input.workcenter import WorkCenter
from app.models.output.plan_evaluation import PlanEvaluationAction
from app.schemas.llm import AlertItemOut, SuggestionRequest
from app.services.llm.chat_service import ChatService, ChatServiceError, get_cached_chat_service
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = get_logger(__name__)

_SYSTEM_PROMPT = """\
당신은 APS 운영 경보 분석가입니다.
반드시 한국어로만 답변하세요.
입력으로 주어진 alerts의 숫자/대상/맥락은 유지하고, 각 alert에 ai_insight만 보강하세요.
JSON만 반환하세요:
{{
  "alerts": [
    {{
      "ai_insight": "<2문장 이내: 원인 + 권고>"
    }}
  ]
}}
규칙:
- alert 순서는 입력과 동일
- ai_insight는 짧고 실행 가능해야 함
- 새로운 수치/ID를 지어내지 말 것
"""

_USER_PROMPT = """\
컨텍스트 유형: {context_type}
작업장: {workcenter_id}
영향 품목: {affected_items}
기준 alerts(JSON):
{alerts_json}
"""


def _parse_numbered_list(text: str) -> list[str]:
    """Extract numbered/bulleted list items from LLM output.

    Handles: '1. item', '1) item', '- item', '• item'
    Falls back to non-empty lines if no list markers found.
    """
    lines = text.strip().splitlines()
    results = []
    for line in lines:
        line = line.strip()
        m = re.match(r"^(?:\d+[.)]\s*|[-•]\s*)(.+)", line)
        if m:
            results.append(m.group(1).strip())
    return results if results else [ln.strip() for ln in lines if ln.strip()]


def _priority_from_level(level: str) -> str:
    level = (level or "").strip()
    if level == "🔴":
        return "high"
    if level in ("경고", "🟠"):
        return "medium"
    return "low"


def _safe_num(v: object, default: float = 0.0) -> float:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _fmt_level_prefix(level: str) -> str:
    if level in ("주의", "경고"):
        return level
    if level in ("🔴", "🟠"):
        return f"경고 {level}"
    return "주의"


def _extract_overload_rows(kpi: dict) -> list[dict]:
    """Collect overload rows from multiple payload shapes."""
    load = kpi.get("load_kpi") or {}
    rows: list[dict] = []
    rows.extend(load.get("overloaded_slots") or [])
    # fallback 1: entries with overloaded=true or load>100
    for e in (load.get("entries") or []):
        if e.get("overloaded") or _safe_num(e.get("load_percent"), 0.0) > 100:
            rows.append(e)
    # fallback 2: schedule-style loads at top-level
    for e in (kpi.get("workcenter_loads") or []):
        if e.get("overloaded") or _safe_num(e.get("load_percent"), 0.0) > 100:
            rows.append(e)
    return rows


def _derive_alerts_from_kpi(request: SuggestionRequest) -> list[AlertItemOut]:
    """Build dashboard-like alerts directly from KPI summary payload (non-hardcoded)."""
    kpi = request.kpi_summary or {}
    out: list[AlertItemOut] = []

    delivery = kpi.get("delivery_kpi") or kpi.get("delivery_risk") or {}
    delayed = int(delivery.get("delayed_orders") or 0)
    total = int(delivery.get("total_orders") or 0)
    if delayed > 0:
        rate = _safe_num(
            delivery.get("kpi_value")
            if delivery.get("kpi_value") is not None
            else delivery.get("compliance_rate"),
            0.0,
        )
        worst_delay = int(delivery.get("worst_delay_days") or 0)
        level = "경고" if delayed < 3 else "🔴"
        out.append(
            AlertItemOut(
                level=level,
                message=(
                    f"{_fmt_level_prefix(level)} 계획납기준수율 저하 | "
                    f"지연 {delayed}/{total} | 준수율 {rate:.1f}%"
                ),
                context={
                    "type": "delivery",
                    "delayed_orders": delayed,
                    "total_orders": total,
                    "compliance_rate": round(rate, 2),
                    "worst_delay_days": worst_delay,
                },
                ai_insight="납기 지연 원인을 우선 공정/자재 관점에서 분리 진단하세요.",
                priority="high" if delayed >= 3 else "medium",
            )
        )

    slots = _extract_overload_rows(kpi)
    for slot in slots[:2]:
        pct = _safe_num(slot.get("load_percent"), 0.0)
        wc = slot.get("workcenter_code") or slot.get("workcenter_name") or slot.get("workcenter_id")
        day = slot.get("plan_date") or slot.get("work_date") or slot.get("date")
        level = "🔴" if pct >= 120 else "🟠"
        out.append(
            AlertItemOut(
                level=level,
                message=f"{_fmt_level_prefix(level)} {wc} | {pct:.0f}% | {day}",
                context={
                    "type": "load",
                    "workcenter": wc,
                    "load_percent": round(pct, 2),
                    "plan_date": day,
                },
                ai_insight="과부하 구간을 분산할 수 있는 대체 라인/잔업 시나리오를 비교하세요.",
                priority="high" if level == "🔴" else "medium",
            )
        )

    shortage = kpi.get("shortage_kpi") or kpi.get("material_shortage") or {}
    shortage_items = shortage.get("shortage_items") or []
    if not shortage_items and shortage:
        # Fallback compact shape: material_shortage.{worst_item,worst_shortage_qty,...}
        worst_item = shortage.get("worst_item")
        worst_qty = _safe_num(shortage.get("worst_shortage_qty"), 0.0)
        worst_pct = _safe_num(shortage.get("worst_shortage_percent"), 0.0)
        if worst_item or worst_qty > 0:
            shortage_items = [
                {
                    "item_no": worst_item,
                    "item_name": None,
                    "shortage_qty": worst_qty,
                    "shortage_percent": worst_pct,
                }
            ]
    for s in shortage_items[:2]:
        sq = _safe_num(s.get("shortage_qty"), 0.0)
        item = s.get("item_no") or s.get("item_id")
        level = "주의" if sq < 100 else "🟠"
        out.append(
            AlertItemOut(
                level=level,
                message=f"{_fmt_level_prefix(level)} {item} | 부족 {sq:.0f}",
                context={
                    "type": "material",
                    "item_no": s.get("item_no"),
                    "item_name": s.get("item_name"),
                    "shortage_qty": round(sq, 2),
                    "shortage_percent": _safe_num(s.get("shortage_percent"), 0.0),
                    "items_with_shortage": int(shortage.get("items_with_shortage") or 0),
                    "total_shortage_qty": _safe_num(shortage.get("total_shortage_qty"), 0.0),
                },
                ai_insight="대체 자재 또는 긴급 구매의 리드타임을 먼저 확인하세요.",
                priority="low" if sq < 100 else "medium",
            )
        )

    # Fallback compact shape for overload: wc_overload (single row)
    wc_over = kpi.get("wc_overload") or {}
    if wc_over and not slots:
        pct = _safe_num(wc_over.get("max_load_percent"), 0.0)
        wc = wc_over.get("overloaded_workcenter") or request.workcenter_id
        day = wc_over.get("plan_date")
        if pct > 0 and wc:
            level = "🔴" if pct >= 120 else "🟠"
            out.append(
                AlertItemOut(
                    level=level,
                    message=f"{_fmt_level_prefix(level)} {wc} | {pct:.0f}% | {day}",
                    context={
                        "type": "load",
                        "workcenter": wc,
                        "load_percent": round(pct, 2),
                        "plan_date": day,
                        "overloaded_slots": int(wc_over.get("overloaded_slots") or 0),
                    },
                    ai_insight="과부하 구간을 분산할 수 있는 대체 라인/잔업 시나리오를 비교하세요.",
                    priority="high" if level == "🔴" else "medium",
                )
            )

    if not out:
        out.append(
            AlertItemOut(
                level="주의",
                message="현재 KPI 기준 즉시 조치가 필요한 생산 경보가 없습니다.",
                context={"type": "summary", "context_type": request.context_type},
                ai_insight="모니터링을 유지하고 임계치 접근 시 선제 대응하세요.",
                priority="low",
            )
        )
    return out[: max(1, request.max_suggestions)]


def _parse_alert_insights(raw: str, base_alerts: list[AlertItemOut]) -> list[AlertItemOut]:
    """Merge LLM ai_insight text back into precomputed alerts."""
    clean = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
    try:
        data = json.loads(clean)
        rows = data.get("alerts", [])
        for idx, row in enumerate(rows):
            if idx >= len(base_alerts):
                break
            insight = (row.get("ai_insight") or "").strip()
            if insight:
                base_alerts[idx].ai_insight = insight
        return base_alerts
    except Exception:
        return base_alerts


class SuggestionService:
    """Generate action suggestions from KPI/schedule context using LLM."""

    def __init__(self, config_name: str = "no_think") -> None:
        self._chat: ChatService = get_cached_chat_service(config_name)

    def _attach_history_from_actions(
        self,
        alerts: list[AlertItemOut],
        db: Session | None,
        workcenter_no: str | None,
    ) -> list[AlertItemOut]:
        """Enrich alerts with simple history from plan_evaluation_action (no format change)."""
        if db is None:
            return alerts

        wc_id: int | None = None
        if workcenter_no:
            wc = db.execute(
                select(WorkCenter).where(WorkCenter.workcenter_no == workcenter_no)
            ).scalar_one_or_none()
            if wc:
                wc_id = int(wc.id)

        rows = db.execute(select(PlanEvaluationAction)).scalars().all()
        actionable = [r for r in rows if r.action_type in ("APPLY_OVERTIME", "SHIFT_SCHEDULE", "LINE_BALANCE")]
        executed = [r for r in actionable if r.executed_at is not None]

        ot_rows = [r for r in actionable if r.action_type == "APPLY_OVERTIME"]
        if wc_id is not None:
            ot_rows = [
                r for r in ot_rows
                if isinstance(r.parameters, dict)
                and int((r.parameters or {}).get("workcenter_id") or -1) == wc_id
            ]
        ot_caps: list[float] = []
        for r in ot_rows:
            p = r.parameters or {}
            cap = p.get("max_ot_hours") if isinstance(p, dict) else None
            if cap is None and isinstance(p, dict):
                cap = p.get("extra_hours")
            cap_f = _safe_num(cap, -1.0)
            if cap_f >= 0:
                ot_caps.append(cap_f)

        total = len(actionable)
        executed_cnt = len(executed)
        success_rate = (
            round(100.0 * executed_cnt / total, 1) if total > 0 else None
        )
        max_ot = round(max(ot_caps), 2) if ot_caps else None

        for a in alerts:
            ctx = a.context or {}
            ctx["history_actions_total"] = total
            ctx["history_actions_executed"] = executed_cnt
            ctx["history_success_rate_pct"] = success_rate
            if ctx.get("type") == "load":
                ctx["max_ot_hours"] = max_ot
                if max_ot is not None:
                    a.message = f"주의 OT {max_ot:.1f}h 범위 내 완화 가능 | {a.message}"
            if total > 0:
                a.message = f"{a.message} | 유사조치 {total}건 중 실행 {executed_cnt}건"
            a.context = ctx
        return alerts

    async def generate(
        self,
        request: SuggestionRequest,
        db: Session | None = None,
    ) -> list[AlertItemOut]:
        """Return structured APS alerts derived from KPI payload + LLM insight (Korean)."""
        base_alerts = _derive_alerts_from_kpi(request)
        base_alerts = self._attach_history_from_actions(
            base_alerts, db, request.workcenter_id
        )
        messages = [
            {
                "role": "system",
                "content": _SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": _USER_PROMPT.format(
                    context_type=request.context_type,
                    workcenter_id=request.workcenter_id or "N/A",
                    affected_items=", ".join(request.affected_items) or "N/A",
                    alerts_json=json.dumps([a.model_dump() for a in base_alerts], ensure_ascii=False),
                ),
            },
        ]
        try:
            raw = await self._chat.invoke(messages)
            alerts = _parse_alert_insights(raw, base_alerts)
        except Exception:
            alerts = base_alerts
        logger.info("SuggestionService generated %d alerts for context=%s", len(alerts), request.context_type)
        return alerts

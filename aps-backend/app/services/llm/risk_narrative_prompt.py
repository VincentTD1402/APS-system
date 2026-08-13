"""Prompt and output schema for the AI제안 narrative.

The schema is enforced by vLLM's `response_format={"type": "json_schema"}`
token mask, so the model cannot reply with prose, a code fence, or a `<think>`
block — the shape is guaranteed before the text is ever parsed. The prompt then
only has to police *content*: no arithmetic, no figures outside the facts.
"""
from __future__ import annotations

from app.services.llm.risk_narrative_i18n import DEFAULT_LANG, LANGUAGE_DIRECTIVE

# Mirrors RiskNarrative. `additionalProperties: false` keeps the decoder from
# inventing extra keys that would silently carry unvalidated claims.
NARRATIVE_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "root_cause": {"type": "string"},
        "impact_summary": {"type": "string"},
        "recommendations": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "priority": {"type": "integer", "minimum": 1, "maximum": 3},
                    "text": {"type": "string"},
                },
                "required": ["priority", "text"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["root_cause", "impact_summary", "recommendations"],
    "additionalProperties": False,
}

def build_system_prompt(lang: str = DEFAULT_LANG) -> str:
    """SYSTEM_PROMPT with the output-language directive swapped for `lang`.

    Everything else stays Korean — an explicit "respond only in X" directive is
    followed reliably regardless of the surrounding instruction language, and
    translating every rule per language would multiply this file for no
    measurable quality gain.
    """
    directive = LANGUAGE_DIRECTIVE.get(lang, LANGUAGE_DIRECTIVE[DEFAULT_LANG])
    return _SYSTEM_PROMPT_TEMPLATE.format(language_directive=directive)


_SYSTEM_PROMPT_TEMPLATE = """\
당신은 APS 생산계획 리스크 분석가입니다. {language_directive}

[절대 규칙 — 숫자]
- facts JSON에 있는 숫자만 그대로 인용하세요.
- 계산 금지: 더하기, 빼기, 나누기, 평균, 증감률, 배수(예: "8배", "2배")를 만들지 마세요.
- facts에 없는 수치, 작업장 코드, 품목 코드, 날짜, 오더 번호를 만들지 마세요.
- 숫자를 모르면 숫자를 쓰지 말고 문장으로만 설명하세요.

[해석 규칙]
- loadPercent는 그 작업장 전체의 부하입니다. 특정 지시 하나의 책임으로 서술하지 마세요.
- daysToPeakOverload가 음수면 최대 부하일은 이미 지난 날짜입니다. 양수면 앞으로 남은 일수입니다.
- shortages가 비어 있으면 자재 부족을 언급하지 마세요.
- workcenters가 비어 있으면 부하 초과를 언급하지 마세요.

[작성 지침]
- root_cause: 근본 원인 2~4문장. severity를 대괄호로 시작하세요. 예: "[CRITICAL] ..."
- impact_summary: 다음 세 가지를 모두 포함한 2~3문장.
    영향받는 작업장 (workcenters의 workcenterNo 전부 나열)
    영향받는 오더 건수 (affected.count)
    심각도와 긴급도 (severity, urgency)
- recommendations: 우선순위 1~3, 각각 한 문장의 실행 가능한 조치.
  일정 조정, 작업 재배분, 자재 확보처럼 계획 담당자가 바로 할 수 있는 행동으로 쓰세요.
"""

USER_PROMPT = """\
아래 facts JSON만 근거로 작성하세요.

facts:
{facts}
"""

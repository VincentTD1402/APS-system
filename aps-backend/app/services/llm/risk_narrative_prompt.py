"""Prompt and output schema for the AI제안 narrative.

The schema is enforced by vLLM's `response_format={"type": "json_schema"}`
token mask, so the model cannot reply with prose, a code fence, or a `<think>`
block — the shape is guaranteed before the text is ever parsed. The prompt then
only has to police *content*: no arithmetic, no figures outside the facts.
"""
from __future__ import annotations

from app.services.llm.risk_narrative_i18n import (
    DEFAULT_LANG,
    SYSTEM_PROMPT_BY_LANG,
    USER_PROMPT_REMINDER,
)

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
    """Full system prompt for `lang` — see risk_narrative_i18n.SYSTEM_PROMPT_BY_LANG."""
    return SYSTEM_PROMPT_BY_LANG.get(lang, SYSTEM_PROMPT_BY_LANG[DEFAULT_LANG])

def build_user_prompt(facts_json: str, lang: str = DEFAULT_LANG) -> str:
    reminder = USER_PROMPT_REMINDER.get(lang, USER_PROMPT_REMINDER[DEFAULT_LANG])
    return (
        "아래 facts JSON만 근거로 작성하세요.\n\n"
        f"facts:\n{facts_json}\n\n"
        f"{reminder}"
    )

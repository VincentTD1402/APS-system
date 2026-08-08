"""Numeric guard for LLM-written narrative text.

Constrained decoding guarantees the *shape* of the reply, never its truthfulness.
This is the second layer: any figure in the prose that does not appear in the
facts is treated as invented, and the caller falls back to the template rather
than showing a made-up number to a planner.

Known limit: a wrong figure that happens to coincide with some other number in
the facts passes (e.g. writing "8배" when 8 also appears inside a date). The
prompt bans arithmetic for exactly that reason — the guard catches fabrication,
the prompt discourages derivation.
"""
from __future__ import annotations

import re

# Matches 657.15, 2,664 and plain integers. Commas are stripped before compare.
_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")

# Ordinals the template/prompt legitimately use ("우선순위 1"), plus the percentage
# baseline every capacity sentence leans on.
_ALWAYS_ALLOWED = {0.0, 1.0, 2.0, 3.0, 100.0}


def _as_float(token: str) -> float | None:
    try:
        return float(token.replace(",", ""))
    except ValueError:
        return None


def _variants(value: float) -> set[float]:
    """Ways the same figure may legitimately be written in prose.

    657.15 may appear as 657.15, 657.2 or 657; a date part as 08 or 8.
    """
    out = {value, round(value), round(value, 1), round(value, 2)}
    return {float(v) for v in out}


def allowed_numbers(facts_payload: dict) -> set[float]:
    """Every number a sentence may legitimately quote, taken from the facts.

    Dates are decomposed too ("2026-08-07" → 2026, 8, 7) so the narrative can
    spell them out in Korean without tripping the guard.
    """
    allowed: set[float] = set(_ALWAYS_ALLOWED)

    def walk(node: object) -> None:
        if isinstance(node, bool) or node is None:
            return
        if isinstance(node, (int, float)):
            allowed.update(_variants(float(node)))
        elif isinstance(node, str):
            for token in _NUMBER_RE.findall(node):
                value = _as_float(token)
                if value is not None:
                    allowed.update(_variants(value))
        elif isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(facts_payload)
    return allowed


def find_invented_numbers(text: str, allowed: set[float]) -> list[str]:
    """Figures in `text` that no fact backs. Order-preserving, deduplicated."""
    seen: list[str] = []
    for token in _NUMBER_RE.findall(text):
        value = _as_float(token)
        if value is None:
            continue
        if not _variants(value) & allowed and token not in seen:
            seen.append(token)
    return seen


def narrative_text(narrative_json: dict) -> str:
    """Flatten the LLM reply to one string for guarding."""
    parts = [
        str(narrative_json.get("root_cause") or ""),
        str(narrative_json.get("impact_summary") or ""),
    ]
    parts.extend(
        str((item or {}).get("text") or "")
        for item in (narrative_json.get("recommendations") or [])
    )
    return "\n".join(parts)

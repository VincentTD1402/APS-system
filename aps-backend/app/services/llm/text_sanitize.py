"""Remove model reasoning / thinking blocks from LLM text (Qwen3, etc.)."""
from __future__ import annotations

import re


def _pair_tag(tag_name: str) -> re.Pattern[str]:
    """Match `<tag>...</tag>` with identical open/close names."""
    return re.compile(
        r"<"
        + re.escape(tag_name)
        + r">[\s\S]*?</"
        + re.escape(tag_name)
        + r">",
        re.IGNORECASE,
    )


# Common wrapped reasoning tags (incl. redacted_thinking on some Qwen servers).
_TAG_NAMES: tuple[str, ...] = ("think", "thinking", "reasoning", "redacted_thinking")

_THINK_PATTERNS: list[re.Pattern[str]] = [_pair_tag(t) for t in _TAG_NAMES]

_UNCLOSED_PAIRS: tuple[tuple[str, str], ...] = tuple(
    (f"<{t}>", f"</{t}>") for t in _TAG_NAMES
)


def strip_llm_thinking(text: str) -> str:
    """Drop thinking / chain-of-thought blocks; keep only user-facing answer text."""
    if not text or not text.strip():
        return text
    out = text
    for pat in _THINK_PATTERNS:
        out = pat.sub("", out)
    for open_tag, close_tag in _UNCLOSED_PAIRS:
        lower = out.lower()
        oi = lower.find(open_tag.lower())
        if oi == -1:
            continue
        tail = out[oi:]
        if close_tag.lower() not in tail.lower():
            out = out[:oi].rstrip()
            break
    return out.strip()

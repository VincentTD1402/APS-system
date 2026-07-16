"""Shared Bolt session kwargs (reduces Neo4j 5+ GQL schema hint noise in logs)."""

from __future__ import annotations

from typing import Any

from app.config import settings


def neo4j_session_extra_kwargs() -> dict[str, Any]:
    """Return kwargs for ``driver.session(...)``.

    When ``APS_NEO4J_SILENCE_NOTIFICATIONS`` (default True): set
    ``notifications_min_severity=OFF`` to avoid spamming 01N50/01N51/01N52
    (labels/properties missing from catalog — common on fresh DBs or before full graph import).
    """
    if not getattr(settings, "APS_NEO4J_SILENCE_NOTIFICATIONS", True):
        return {}
    try:
        from neo4j import NotificationMinimumSeverity

        return {"notifications_min_severity": NotificationMinimumSeverity.OFF}
    except ImportError:
        return {}

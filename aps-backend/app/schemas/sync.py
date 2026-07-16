from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class EntityCount(BaseModel):
    synced: int
    skipped: int


class SyncRunResponse(BaseModel):
    started_at: datetime
    finished_at: datetime | None
    success: bool
    error: str | None
    counts: dict[str, EntityCount]
    calendar_synced: int
    neo4j_nodes: int = 0
    neo4j_relationships: int = 0
    rdf_triples: int = 0

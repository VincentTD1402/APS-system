"""APS Local DB — G-System sync job persistence."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Integer, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class GsystemSyncJob(Base):
    """Persists G-System sync job results across server restarts.

    Replaces the in-memory OrderedDict that was lost on restart.
    """
    __tablename__ = "gsystem_sync_job"
    __table_args__ = {"schema": "aps_result"}

    job_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="running", index=True,
    )  # running | completed | failed

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    success: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    counts: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    calendar_synced: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    neo4j_nodes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    neo4j_relationships: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rdf_triples: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

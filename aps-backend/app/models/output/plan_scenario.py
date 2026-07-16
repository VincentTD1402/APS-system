"""APS Local DB — Plan Scenario model."""

from datetime import date, datetime, timezone
from typing import List, Optional
from sqlalchemy import String, Integer, DateTime, Date, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class PlanScenario(Base):
    """Lifecycle status: Draft / Running / Simulated / Approved / Released
    
    For SIMULATION scenarios:
    - scenario_id: unique identifier (e.g., "SCH-R1_sim_1")
    - parent_scenario_id: links back to baseline scenario (e.g., "SCH-R1")
    - what_if_index: 1, 2, or 3 to denote which simulation branch
    
    For BASELINE scenarios:
    - parent_scenario_id: NULL
    - what_if_index: NULL
    """
    __tablename__ = "plan_scenario"
    __table_args__ = {"schema": "aps_result"}

    scenario_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    horizon_start: Mapped[date] = mapped_column(Date, nullable=False)
    horizon_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_message: Mapped[Optional[str]] = mapped_column(String(500))
    scenario_type: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
        nullable=False,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    what_if_index: Mapped[Optional[int]] = mapped_column(Integer)  # 1, 2, or 3. NULL for BASELINE
    
    # Link simulation scenario back to its baseline parent (NULL if this IS the baseline)
    parent_scenario_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        ForeignKey("aps_result.plan_scenario.scenario_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    orders: Mapped[List["PlanOrder"]] = relationship(back_populates="scenario", cascade="all, delete-orphan")
    utilizations: Mapped[List["PlanUtilization"]] = relationship(back_populates="scenario", cascade="all, delete-orphan")
    
    # Self-referencing relationships for simulation branching
    parent: Mapped[Optional["PlanScenario"]] = relationship(
        back_populates="simulations",
        remote_side=[scenario_id],
        foreign_keys=[parent_scenario_id],
    )
    simulations: Mapped[List["PlanScenario"]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
    )
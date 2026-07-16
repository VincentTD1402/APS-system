"""APS Local DB — WorkCalendar model (daily work schedule)."""

from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class CalendarEntry(Base):
    """One row per calendar date from G-System cm_calendar.

    Shared calendar for all WorkCenters (G-System has no per-WC calendar).
    work_hours stored as decimal hours converted from HHMM (e.g. "0800" → 8.0).
    """

    __tablename__ = "aps_calendar"
    __table_args__ = (
        CheckConstraint("work_hours >= 0", name="ck_calendar_work_hours_non_negative"),
        {"schema": "aps_input"},
    )

    # work_date is the natural PK (one entry per day)
    work_date: Mapped[date] = mapped_column(Date, primary_key=True)
    # Original G-System day_of_week code (e.g. "10291003")
    day_of_week_cd: Mapped[str | None] = mapped_column(String(20))
    # Original G-System work_gb code (e.g. "10431002")
    work_gb_cd: Mapped[str | None] = mapped_column(String(20))
    is_holiday: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Available working hours for this date (0.0 on holidays)
    work_hours: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0.0)

    def __repr__(self) -> str:
        return f"<CalendarEntry {self.work_date} holiday={self.is_holiday} hours={self.work_hours}>"

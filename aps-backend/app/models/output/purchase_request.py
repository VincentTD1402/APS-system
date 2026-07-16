from datetime import datetime, timezone
from sqlalchemy import String, Integer, ForeignKey, Numeric, DateTime, Date
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base

class PurchaseRequest(Base):
    __tablename__ = "purchase_request"
    __table_args__ = {"schema": "aps_result"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scenario_id: Mapped[str] = mapped_column(String(50), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("aps_input.aps_item.id"), nullable=False)
    shortage_qty: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    need_date: Mapped[datetime] = mapped_column(Date, nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), default="VENDOR")
    status: Mapped[str] = mapped_column(String(20), default="APPLIED")
    ext_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    req_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    corp_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    biz_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ext_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    response_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
"""Pydantic schemas for Purchase Request read endpoints."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class PurchaseRequestRow(BaseModel):
    """Single row from GET /purchase-requests."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    scenario_id: str
    item_id: int
    shortage_qty: float
    need_date: date | None = None
    source_type: str | None = None
    status: str
    sync_status: str | None = None
    ext_status: str | None = None
    ext_id: int | None = None
    req_no: str | None = None
    corp_id: int | None = None
    biz_id: int | None = None
    sent_at: datetime | None = None
    created_at: datetime

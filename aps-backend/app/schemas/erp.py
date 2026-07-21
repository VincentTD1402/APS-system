"""Pydantic schemas for POST /erp/purchase-requests and POST /erp/work-orders.

camelCase like app/schemas/aps.py — see that file's docstring for why.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.schemas.aps import CamelModel


class PurchaseRequestCreateIn(CamelModel):
    plan_id: str
    qty: float
    note: str | None = None


class WorkOrderDispatchIn(CamelModel):
    plan_id: str


class ErpOutboxRow(CamelModel):
    id: int
    run_id: str | None = None
    action: str
    payload: dict[str, Any]
    status: str
    created_at: datetime
    pushed_at: datetime | None = None
    error: str | None = None

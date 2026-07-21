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
    # FE's ErpOutboxRow.id is `string` (aps-frontend/src/types/planning.ts) — the
    # underlying PK is an int (PurchaseRequest.id / WorkOrder.id); stringify at the
    # route boundary, not here, so callers can't accidentally pass an int through.
    id: str
    run_id: str | None = None
    action: str
    payload: dict[str, Any]
    # FE's ErpOutboxStatus = 'PENDING' | 'PUSHED' | 'FAILED' — routes must map the
    # underlying PurchaseRequest.status ("PENDING"/"APPLIED") / WorkOrder.status
    # ("PLANNED"/"SENT"/"CONFIRMED"/"FAILED") onto this before constructing the row.
    status: str
    created_at: datetime
    pushed_at: datetime | None = None
    error: str | None = None

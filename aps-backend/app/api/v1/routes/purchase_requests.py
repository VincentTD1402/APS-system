"""Read endpoints for PurchaseRequest rows produced by CREATE_PURCHASE_REQUEST."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.output.purchase_request import PurchaseRequest
from app.schemas.purchase_request import PurchaseRequestRow

router = APIRouter()


@router.get(
    "",
    response_model=List[PurchaseRequestRow],
    summary="List purchase requests",
    description=(
        "Rows from aps_result.purchase_request, filterable by scenario / item / status. "
        "FE reads `sync_status` to render the action card outcome."
    ),
)
def list_purchase_requests(
    scenario_id: Optional[str] = Query(None, description="Filter by scenario_id"),
    item_id: Optional[int] = Query(None, description="Filter by item_id (aps_item.id)"),
    sync_status: Optional[str] = Query(
        None,
        description="Filter by sync_status: SUCCESS / FAILED / ERROR / SIMULATED",
    ),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> List[PurchaseRequestRow]:
    stmt = select(PurchaseRequest).order_by(
        PurchaseRequest.created_at.desc(), PurchaseRequest.id.desc()
    )
    if scenario_id:
        stmt = stmt.where(PurchaseRequest.scenario_id == scenario_id)
    if item_id is not None:
        stmt = stmt.where(PurchaseRequest.item_id == item_id)
    if sync_status:
        stmt = stmt.where(PurchaseRequest.sync_status == sync_status)
    stmt = stmt.limit(limit)

    rows = db.execute(stmt).scalars().all()
    return [PurchaseRequestRow.model_validate(r) for r in rows]

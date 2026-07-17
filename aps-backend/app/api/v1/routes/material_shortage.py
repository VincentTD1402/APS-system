"""Endpoints for material shortage (자재부족).

POST /material-shortage/rebuild → recompute aps_material_shortage (wipe + rewrite).
GET  /material-shortage         → list per-component required/available/shortage.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models import MaterialShortage
from app.schemas.material_shortage import (
    MaterialShortageRebuildResponse,
    MaterialShortageRow,
)
from app.services.material_shortage import rebuild_material_shortage

router = APIRouter()


@router.post(
    "/rebuild",
    response_model=MaterialShortageRebuildResponse,
    summary="Rebuild material shortage",
    description=(
        "Recompute aps_result.aps_material_shortage from aps_mps_plan × aps_bom "
        "(required = plan_qty × qty1/qty2) vs aps_stock (available). Wipes + rewrites."
    ),
)
def rebuild_material_shortage_endpoint(db: Session = Depends(get_db)) -> MaterialShortageRebuildResponse:
    rows = rebuild_material_shortage(db)
    db.commit()
    return MaterialShortageRebuildResponse(rows_inserted=rows)


@router.get(
    "",
    response_model=List[MaterialShortageRow],
    summary="List material shortage rows",
    description="Rows from aps_result.aps_material_shortage (call POST .../rebuild first).",
)
def list_material_shortage(
    shortage_only: bool = Query(False, description="Return only components with shortage_qty > 0"),
    item_id: Optional[int] = Query(None, description="Filter by component item id"),
    db: Session = Depends(get_db),
) -> List[MaterialShortageRow]:
    stmt = select(MaterialShortage).order_by(
        MaterialShortage.shortage_qty.desc(), MaterialShortage.item_no
    )
    if shortage_only:
        stmt = stmt.where(MaterialShortage.shortage_qty > 0)
    if item_id is not None:
        stmt = stmt.where(MaterialShortage.item_id == item_id)

    rows = db.execute(stmt).scalars().all()
    return [
        MaterialShortageRow(
            item_id=r.item_id,
            item_no=r.item_no,
            item_name=r.item_name,
            required_qty=float(r.required_qty),
            available_qty=float(r.available_qty),
            shortage_qty=float(r.shortage_qty),
            is_short=float(r.shortage_qty) > 0,
        )
        for r in rows
    ]

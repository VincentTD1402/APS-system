"""API v1 Routes Package.

NOTE: All endpoints are currently public (no auth middleware).
TODO: Add authentication/authorization middleware (e.g. OAuth2, API key)
      before production deployment.
"""

from fastapi import APIRouter

from app.api.v1.routes import (
    aps,
    erp,
    gsystem_sync,
    kpi_summary,
    llm,
    # material_shortage,  # router disabled below, import commented to avoid unused-import lint
    purchase_requests,
    work_plan,
)

api_router = APIRouter()

api_router.include_router(gsystem_sync.router, prefix="/gsystem", tags=["gsystem"])
# Hidden from Swagger (not used by FE yet) — routes still active, just excluded from OpenAPI schema.
api_router.include_router(llm.router, prefix="/llm", tags=["LLM"], include_in_schema=False)
api_router.include_router(kpi_summary.router, prefix="/kpi-summary", tags=["kpi_summary"])
api_router.include_router(purchase_requests.router, prefix="/purchase-requests", tags=["purchase_requests"])
api_router.include_router(aps.router, prefix="/aps", tags=["aps"])
api_router.include_router(erp.router, prefix="/erp", tags=["erp"])
api_router.include_router(work_plan.router, prefix="/work-plan", tags=["work_plan"])
# material_shortage router disabled — POST rebuild is redundant (already called inside
# POST /kpi-summary/daily-plan/rebuild) and GET list is unused by FE. Code kept as-is.
# api_router.include_router(material_shortage.router, prefix="/material-shortage", tags=["material_shortage"])

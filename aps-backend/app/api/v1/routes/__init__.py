"""API v1 Routes Package.

NOTE: All endpoints are currently public (no auth middleware).
TODO: Add authentication/authorization middleware (e.g. OAuth2, API key)
      before production deployment.
"""

from fastapi import APIRouter

from app.api.v1.routes import (
    gsystem_sync,
    kpi_summary,
    llm,
    purchase_requests,
    work_plan,
    material_shortage,
    workorder,
)

api_router = APIRouter()

api_router.include_router(gsystem_sync.router, prefix="/gsystem", tags=["gsystem"])
api_router.include_router(llm.router, prefix="/llm", tags=["LLM"])
api_router.include_router(kpi_summary.router, prefix="/kpi-summary", tags=["kpi_summary"])
api_router.include_router(workorder.router, prefix="/workorder", tags=["workorder"])
api_router.include_router(purchase_requests.router, prefix="/purchase-requests", tags=["purchase_requests"])
api_router.include_router(work_plan.router, prefix="/work-plan", tags=["work_plan"])
api_router.include_router(material_shortage.router, prefix="/material-shortage", tags=["material_shortage"])

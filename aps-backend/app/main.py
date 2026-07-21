from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.routes import api_router
from app.config.config import settings
from app.scheduler.gsystem_cron import (
    shutdown_gsystem_cron_scheduler,
    start_gsystem_cron_scheduler,
)
from app.services.llm.concurrency import (
    configured_limits,
    metrics_snapshot,
    new_request_id,
    request_id_var,
)
from app.services.llm.chat_service import warmup_cached_chat_services


@asynccontextmanager
async def lifespan(_app: FastAPI):
    start_gsystem_cron_scheduler()
    # Preload LLM clients once at startup to avoid first-request cold-start stalls.
    warmup_cached_chat_services()
    yield
    shutdown_gsystem_cron_scheduler()


app = FastAPI(
    title="APS System Backend Core",
    description="Advanced Planning and Scheduling System API - Core Module",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],  # Allow frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Total-Count"],
)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Stamp every request with X-Request-ID; expose via response header + ContextVar."""

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or new_request_id()
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            request_id_var.reset(token)


app.add_middleware(RequestIdMiddleware)

# Include routers
app.include_router(api_router, prefix=f"/api/{settings.API_VERSION}")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "APS System Backend Core API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Liveness probe — always cheap, never touches DB/LLM."""
    return {"status": "healthy"}


@app.get("/metrics")
async def metrics():
    """Lightweight in-process metrics: in-flight LLM ops + p50/p95 per route."""
    return {
        "limits": configured_limits(),
        "routes": metrics_snapshot(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=True,
        reload=True,
        workers=1,
    )

"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine
from app.routers import (
    assignment,
    auth,
    balance,
    campaign_templates,
    campaigns,
    categories,
    charge_requests,
    companies,
    dashboard,
    extraction_jobs,
    network_presets,
    notices,
    notifications,
    orders,
    pipeline,
    places,
    products,
    redirect,
    scheduler,
    settlements,
    superap_accounts,
    system_settings,
    users,
)
from app.routers.internal import callbacks


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    from app.core.scheduler import start_scheduler, stop_scheduler
    await start_scheduler()
    yield
    await stop_scheduler()
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dashboard
app.include_router(dashboard.router, prefix="/api/v1")

# Routers - Phase 1A
app.include_router(auth.router, prefix="/api/v1")
app.include_router(companies.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")

# Routers - Phase 1B
app.include_router(products.router, prefix="/api/v1")
app.include_router(orders.router, prefix="/api/v1")
app.include_router(balance.router, prefix="/api/v1")
app.include_router(system_settings.router, prefix="/api/v1")

# Routers - Phase 1C
app.include_router(places.router, prefix="/api/v1")
app.include_router(extraction_jobs.router, prefix="/api/v1")
app.include_router(campaigns.router, prefix="/api/v1")
app.include_router(network_presets.router, prefix="/api/v1")
app.include_router(superap_accounts.router, prefix="/api/v1")
app.include_router(campaign_templates.router, prefix="/api/v1")
app.include_router(assignment.router, prefix="/api/v1")
app.include_router(pipeline.router, prefix="/api/v1")

# Routers - Phase 2 (New features)
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(notices.router, prefix="/api/v1")
app.include_router(settlements.router, prefix="/api/v1")
app.include_router(categories.router, prefix="/api/v1")
app.include_router(scheduler.router, prefix="/api/v1")
app.include_router(charge_requests.router, prefix="/api/v1")

# Redirect (public, no /api/v1 prefix)
app.include_router(redirect.router)

# Internal callback router (no /api/v1 prefix)
app.include_router(callbacks.router)


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }

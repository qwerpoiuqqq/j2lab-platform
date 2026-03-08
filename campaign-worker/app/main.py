"""FastAPI application entry point for campaign-worker.

Campaign automation worker that handles:
- Campaign registration on superap.io via Playwright
- Keyword rotation every 10 minutes via APScheduler
- Campaign status synchronization
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

import app.models  # noqa: F401  # Ensure ORM mappers are registered before scheduler start
from app.core.config import settings
from app.core.database import engine
from app.modules.registry import register_default_modules
from app.routers.internal import router as internal_router
from app.services.keyword_rotator import start_scheduler, stop_scheduler

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info(
        "%s v%s starting on port %d",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.WORKER_PORT,
    )

    # Register campaign setup modules (landmark, steps, place_info)
    register_default_modules()

    # Start APScheduler for keyword rotation
    start_scheduler()
    logger.info("Application started")

    yield

    # Shutdown: stop scheduler and dispose engine connections
    stop_scheduler()
    await engine.dispose()
    logger.info("%s shutting down", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None,
)

# Register routers
app.include_router(internal_router)

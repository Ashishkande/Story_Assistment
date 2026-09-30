"""FastAPI application entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.platform import router as platform_router
from app.api.stories import router as stories_router
from app.config import get_settings
from app.db.models import Base
from app.db.session import async_engine

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup if they don't exist."""
    logger.info("Starting Agentic Serial Story Writer API")

    if settings.app_env != "production":
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database tables ready")

    yield

    logger.info("Shutting down")
    await async_engine.dispose()


app = FastAPI(
    title="Agentic Serial Story Writer",
    description="Generate 200-episode serial stories with human-in-the-loop control.",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------

_origins = [
    origin.strip()
    for origin in settings.cors_origins.split(",")
    if origin.strip()
]

logger.info("CORS allowed origins: %s", _origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# API Routes
# ---------------------------------------------------------

api_router = APIRouter(prefix="/api")

api_router.include_router(stories_router)
api_router.include_router(platform_router)

app.include_router(api_router)


# ---------------------------------------------------------
# Health
# ---------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "0.1.0",
    }

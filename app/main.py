"""FastAPI application entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastapi import APIRouter

from app.api.platform import router as platform_router
from app.api.stories import router as stories_router
from app.db.models import Base
from app.db.session import async_engine
from app.config import get_settings

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup (if they don't exist)."""
    logger.info("Starting Agentic Serial Story Writer API")
    # Production containers apply Alembic before uvicorn starts.
    # Development still creates missing tables so local runs do not need the CLI.
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

_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api")
api_router.include_router(stories_router)
api_router.include_router(platform_router)
app.include_router(stories_router)
app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}

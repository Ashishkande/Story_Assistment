"""Database session factory."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

settings = get_settings()

# Async engine (used by FastAPI)
async_engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine, class_=AsyncSession, expire_on_commit=False
)

# Sync engine (used by Alembic migrations & CLI)
sync_engine = create_engine(
    settings.database_url_sync,
    echo=False,
    pool_pre_ping=True,
)
SyncSessionLocal = sessionmaker(bind=sync_engine, autoflush=False, autocommit=False)


async def get_async_session() -> AsyncSession:
    """FastAPI dependency – yields an async DB session."""
    async with AsyncSessionLocal() as session:
        yield session


def get_sync_session() -> Session:
    """CLI/script helper – yields a sync DB session."""
    with SyncSessionLocal() as session:
        yield session

from __future__ import annotations

from typing import AsyncGenerator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import pool
from api.core.settings import settings
from contextlib import contextmanager

_use_null_pool = settings.is_testing()
_async_engine_kwargs = {
    "echo": settings.DEBUG,
    "future": True,
}
_sync_engine_kwargs = {
    "echo": settings.DEBUG,
}
if _use_null_pool:
    _async_engine_kwargs["poolclass"] = pool.NullPool
    _sync_engine_kwargs["poolclass"] = pool.NullPool

# Create async engine for PostgreSQL
engine = create_async_engine(
    settings.DATABASE_URL,
    **_async_engine_kwargs,
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# Create sync engine for Celery workers (converting asyncpg to psycopg2 if needed)
sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
sync_engine = create_engine(
    sync_url,
    **_sync_engine_kwargs,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=sync_engine
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting async database sessions in FastAPI routes.
    """
    async with AsyncSessionLocal() as session:
        yield session

@contextmanager
def get_sync_db():
    """
    Context manager for getting synchronous database sessions in Celery workers.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

"""資料庫連線 / Database engine and session factory (SQLAlchemy 2.0 async)."""
from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI 依賴 / FastAPI dependency."""
    async with get_sessionmaker()() as session:
        yield session


def reset_db_caches() -> None:
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()

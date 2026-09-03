"""Redis 連線 / Redis client (快取、速率限制、任務佇列 / cache, rate limits, job queue)."""
from __future__ import annotations

from functools import lru_cache

import redis
import redis.asyncio as aioredis

from ..config import get_settings


@lru_cache
def get_redis() -> aioredis.Redis:
    return aioredis.from_url(get_settings().redis_url, decode_responses=True)


@lru_cache
def get_sync_redis() -> redis.Redis:
    return redis.from_url(get_settings().redis_url)


def reset_redis_caches() -> None:
    get_redis.cache_clear()
    get_sync_redis.cache_clear()

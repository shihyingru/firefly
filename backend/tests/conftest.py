"""
測試基礎 / Test fixtures.

需要本機 PostgreSQL(含 pgvector)與 Redis:
  TEST_DATABASE_URL(預設 postgresql+asyncpg://postgres@127.0.0.1:5432/firefly_test)
  TEST_REDIS_URL(預設 redis://127.0.0.1:6379/15)
Requires local PostgreSQL (with pgvector) and Redis; see env vars above.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

BACKEND = Path(__file__).resolve().parents[1]
TEST_DB = os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://postgres@127.0.0.1:5432/firefly_test")
TEST_REDIS = os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:6379/15")

os.environ["DATABASE_URL"] = TEST_DB
os.environ["REDIS_URL"] = TEST_REDIS
os.environ["FIREFLY_INLINE_JOBS"] = "1"
os.environ["FIREFLY_SOURCE_ADAPTER"] = "mock"
# 測試一律用雜湊嵌入,與 ml extra 是否安裝無關。setdefault 保留外部覆寫,
# 供 e5 煙霧測試以 FIREFLY_EMBEDDER=e5 刻意跑真模型。
# Tests always use the hashed embedder, whether or not the ml extra is installed.
# setdefault keeps the override so the e5 smoke test can opt in deliberately.
os.environ.setdefault("FIREFLY_EMBEDDER", "hash")
os.environ.setdefault("DEVICE_TOKEN_PEPPER", "test-pepper")
os.environ.setdefault("LINE_ID_HMAC_KEY", "test-hmac")


def _alembic(cmd: str) -> None:
    env = {**os.environ, "ALEMBIC_DATABASE_URL": TEST_DB}
    subprocess.run([sys.executable, "-m", "alembic", cmd, "head" if cmd == "upgrade" else "base"], cwd=BACKEND, env=env, check=True, capture_output=True)


@pytest.fixture(scope="session", autouse=True)
def migrated_db():
    _alembic("downgrade")
    _alembic("upgrade")
    yield


@pytest_asyncio.fixture(autouse=True)
async def clean_state():
    """每個測試前清空資料表與 Redis / truncate tables and flush Redis before each test."""
    from sqlalchemy import text

    from firefly.db import get_sessionmaker
    from firefly.services.redis_client import get_redis

    async with get_sessionmaker()() as s:
        await s.execute(text("TRUNCATE vote, cluster_flag, context_card, post_snapshot, cluster, contributor, audit_log, domain_signal, finance_record RESTART IDENTITY CASCADE"))
        await s.commit()
    await get_redis().flushdb()
    yield
    # 每個測試各自的事件迴圈:釋放綁定舊迴圈的連線池 / per-test loops: dispose pools bound to the old loop
    from firefly.db import get_engine, reset_db_caches
    from firefly.services.redis_client import reset_redis_caches

    await get_redis().aclose()
    await get_engine().dispose()
    reset_db_caches()
    reset_redis_caches()


@pytest_asyncio.fixture
async def client():
    from firefly.main import create_app

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def db():
    from firefly.db import get_sessionmaker

    async with get_sessionmaker()() as s:
        yield s

#!/usr/bin/env python3
"""
示範資料 / Demo seed(單機驗證用,不碰任何真實平台)。

三則模擬貼文走完整管線:Stage 0 快照 → Stage 2 聚類 → Stage 1 指紋 → Stage 3 確定性起草 → candidate 卡。
Three mock posts run through the full pipeline: snapshot → clustering → fingerprints → deterministic card.

執行 / Run(需 DATABASE_URL、REDIS_URL,並先 alembic upgrade head):
  FIREFLY_EMBEDDER=hash python3 scripts/seed_demo.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
os.environ.setdefault("FIREFLY_INLINE_JOBS", "1")
os.environ.setdefault("FIREFLY_SOURCE_ADAPTER", "mock")
os.environ.setdefault("FIREFLY_EMBEDDER", "hash")  # 無 e5 模型時的替代 / fallback without the e5 model

from firefly.db import get_sessionmaker  # noqa: E402
from firefly.models import Cluster  # noqa: E402
from firefly.pipeline.adapters import seed_mock_post  # noqa: E402
from firefly.pipeline.jobs import _process_url  # noqa: E402
from sqlalchemy import select  # noqa: E402

BASE = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
POSTS = [
    ("https://www.threads.com/@demo_a/post/DEMO0001", "demo_a", "這款產品真的太神了!大家快去看 👉 https://example-shop.tld/x\n#好物 #推薦", BASE),
    ("https://www.threads.com/@demo_b/post/DEMO0002", "demo_b", "這款產品真的太神了!!大家快去看 👉 https://example-shop.tld/x\n#好物 #推薦", BASE + timedelta(minutes=3)),
    ("https://www.threads.com/@demo_c/post/DEMO0003", "demo_c", "這款產品真的太神了!大家快去看 👉 https://example-shop.tld/x 🔥\n#好物 #推薦", BASE + timedelta(minutes=7)),
]


async def main() -> None:
    for url, handle, text, at in POSTS:
        seed_mock_post(url, handle, text, at)
        print(url, "->", await _process_url(url))
    async with get_sessionmaker()() as s:
        cluster = await s.scalar(select(Cluster).order_by(Cluster.created_at.desc()))
        if cluster is None:
            print("no cluster formed (θ_join not reached with the active embedder); see config/firefly.yaml clustering.theta_join")
            return
        print("cluster_id", cluster.id, "posts", cluster.post_count, "accounts", cluster.account_count)
        print("card_id   ", cluster.current_card_id)
        print("lookup URL", POSTS[0][0])


if __name__ == "__main__":
    asyncio.run(main())

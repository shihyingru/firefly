#!/usr/bin/env python3
"""
示範資料 / Demo seed(單機驗證用,不碰任何真實平台)。

建立三則模擬貼文、一個叢集與一張 candidate 脈絡卡,讓 /lookup、/cards、/votes、/queue 可以端到端試用。
Creates three mock posts, one cluster and one candidate card so /lookup, /cards, /votes, /queue can be tried end-to-end.

執行 / Run(需 DATABASE_URL、REDIS_URL,並先 alembic upgrade head):
  FIREFLY_INLINE_JOBS=1 python3 scripts/seed_demo.py
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

from sqlalchemy import select  # noqa: E402

from firefly.db import get_sessionmaker  # noqa: E402
from firefly.models import CardState, Cluster, ClusterStatus, ContextCard, PostSnapshot  # noqa: E402
from firefly.pipeline.adapters import seed_mock_post  # noqa: E402
from firefly.pipeline.jobs import _process_url  # noqa: E402
from firefly.services.audit import audit  # noqa: E402

BASE = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
POSTS = [
    ("https://www.threads.com/@demo_a/post/DEMO0001", "demo_a", "這款產品真的太神了!大家快去看 👉 https://example-shop.tld/x\n#好物 #推薦", BASE),
    ("https://www.threads.com/@demo_b/post/DEMO0002", "demo_b", "這款產品真的太神了~大家快去看 👉 https://example-shop.tld/x\n#好物 #推薦", BASE + timedelta(minutes=3)),
    ("https://www.threads.com/@demo_c/post/DEMO0003", "demo_c", "這款產品真的太神了!!大家快去看 👉 https://example-shop.tld/x\n#好物", BASE + timedelta(minutes=7)),
]


async def main() -> None:
    for url, handle, text, at in POSTS:
        seed_mock_post(url, handle, text, at)
        await _process_url(url)
    async with get_sessionmaker()() as s:
        snaps = (await s.scalars(select(PostSnapshot).where(PostSnapshot.source_url.in_([p[0] for p in POSTS])))).all()
        cluster = Cluster(status=ClusterStatus.active, post_count=len(snaps), account_count=len({x.author_handle for x in snaps}), last_post_at=max(x.posted_at for x in snaps))
        s.add(cluster)
        await s.flush()
        for x in snaps:
            x.cluster_id = cluster.id
        earliest = min(snaps, key=lambda x: x.posted_at)
        card = ContextCard(
            cluster_id=cluster.id,
            version=1,
            state=CardState.candidate,
            fields={
                "earliest_seen": {"at": earliest.posted_at.isoformat(), "url": earliest.source_url},
                "original_source": {"url": earliest.source_url, "traced": True},
                "account_count": cluster.account_count,
                "timing_chart": [{"t": x.posted_at.isoformat(), "n": 1} for x in sorted(snaps, key=lambda x: x.posted_at)],
                "archive_links": [],
                "domain_note": {"matches": [], "list_version": "0"},
                "sample_excerpt": earliest.content_text[:140],
            },
            validation_passed_at=datetime.now(timezone.utc),
        )
        s.add(card)
        await s.flush()
        cluster.current_card_id = card.id
        await audit(s, "context_card", str(card.id), "state_changed", {"from": "draft", "to": "candidate", "i_c": None, "vote_count": 0, "source": "seed_demo"})
        await s.commit()
        print("cluster_id", cluster.id)
        print("card_id   ", card.id)
        print("lookup URL", POSTS[0][0])


if __name__ == "__main__":
    asyncio.run(main())

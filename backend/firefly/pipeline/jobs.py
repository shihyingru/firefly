"""
管線任務入口 / Pipeline job entry points(RQ 同步函式包 async)。

Wave 1.1:Stage 0 快照。Stage 1–3 於 Wave 1.2 接在 `process_url` 之後。
Wave 1.1: Stage 0 snapshot. Stages 1–3 are chained after `process_url` in Wave 1.2.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from ..db import get_sessionmaker
from ..models import FetchStatus, PostSnapshot
from ..services.audit import audit
from ..services.hashing import content_hash
from ..services.lookup import invalidate_url_cache
from ..services.urlnorm import detect_platform
from .adapters import get_adapter


def process_url(normalized_url: str) -> str:
    return asyncio.run(_process_url(normalized_url))


async def _process_url(normalized_url: str) -> str:
    platform = detect_platform(normalized_url)
    adapter = get_adapter(platform.value)
    fetched = adapter.fetch(normalized_url)
    async with get_sessionmaker()() as session:
        snap = await session.scalar(select(PostSnapshot).where(PostSnapshot.source_url == normalized_url))
        if snap is None:
            snap = PostSnapshot(source_url=normalized_url, platform=platform)
            session.add(snap)
        snap.fetched_at = datetime.now(UTC)
        if fetched is None:
            snap.fetch_status = FetchStatus.unfetchable
            await audit(session, "post_snapshot", str(snap.id), "unfetchable", {"adapter": adapter.name})
            await session.commit()
            await invalidate_url_cache(normalized_url)
            return "unfetchable"
        snap.author_handle = fetched.author_handle
        snap.content_text = fetched.content_text
        snap.content_hash = content_hash(fetched.content_text)
        snap.posted_at = fetched.posted_at
        snap.external_links = fetched.external_links
        snap.fetch_status = FetchStatus.ok
        await audit(session, "post_snapshot", str(snap.id), "fetched", {"adapter": adapter.name, "has_posted_at": fetched.posted_at is not None})
        await session.commit()
    await invalidate_url_cache(normalized_url)
    # Wave 1.2 hook: stage1/2/3 will be invoked here.
    return "ok"

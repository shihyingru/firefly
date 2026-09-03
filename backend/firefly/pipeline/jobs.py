"""
管線任務入口 / Pipeline job entry points(RQ 同步函式包 async)。

process_url:Stage 0 快照 →(策略 A 同伴搜尋)→ Stage 2 聚類 → Stage 1 指紋(隨叢集刷新)→ Stage 3 起草。
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

from sqlalchemy import select

from ..db import get_sessionmaker
from ..models import Cluster, FetchStatus, PostSnapshot
from ..services.audit import audit
from ..services.hashing import content_hash
from ..services.lookup import invalidate_url_cache
from ..services.urlnorm import detect_platform
from .adapters import get_adapter
from .archive import archive_url
from .stage2_cluster import assign_or_form, cluster_posts, refresh_cluster
from .stage3_card import current_card, draft_card, needs_redraft


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
        snap.fetched_at = datetime.now(timezone.utc)
        if fetched is None:
            snap.fetch_status = FetchStatus.unfetchable
            await audit(session, "post_snapshot", str(snap.id), "unfetchable", {"adapter": adapter.name})
            await session.commit()
            await invalidate_url_cache(normalized_url)
            return "unfetchable"
        new_hash = content_hash(fetched.content_text)
        if snap.content_hash != new_hash:
            snap.embedding = None  # 內容變更 → 重新嵌入 / content changed → re-embed
        snap.author_handle = fetched.author_handle
        snap.content_text = fetched.content_text
        snap.content_hash = new_hash
        snap.posted_at = fetched.posted_at
        snap.external_links = fetched.external_links
        snap.fetch_status = FetchStatus.ok
        snap.archive_url = archive_url(normalized_url)
        await audit(session, "post_snapshot", str(snap.id), "fetched", {"adapter": adapter.name, "has_posted_at": fetched.posted_at is not None, "archived": snap.archive_url is not None})
        await session.flush()

        # 策略 A:查詢觸發同伴搜尋(只在真實 Threads adapter 且有 token 時)/ strategy A, real adapter only
        if os.environ.get("FIREFLY_INGEST_SIBLINGS") == "1":
            from .ingest import sibling_search
            from .threads_client import HttpThreadsAPI

            for sib in await sibling_search(session, HttpThreadsAPI(), snap):
                await assign_or_form(session, sib)

        cluster, event = await assign_or_form(session, snap)
        await session.commit()
        await invalidate_url_cache(normalized_url)
        if cluster is None:
            return "isolated"
        await maybe_draft(session, cluster, event)
        await session.commit()
    for p in await _urls_of(cluster.id):
        await invalidate_url_cache(p)
    return event


async def maybe_draft(session, cluster: Cluster, event: str) -> bool:
    card = await current_card(session, cluster)
    reason = needs_redraft(cluster, card, event)
    if reason is None:
        return False
    new = await draft_card(session, cluster, reason)
    return new is not None


async def _urls_of(cluster_id) -> list[str]:
    async with get_sessionmaker()() as s:
        return [p.source_url for p in await cluster_posts(s, cluster_id)]


def recluster_refresh(cluster_id: str) -> str:
    """維護用:重新計算叢集統計並視需要重起草 / maintenance: refresh stats and redraft if needed."""
    return asyncio.run(_recluster_refresh(cluster_id))


async def _recluster_refresh(cluster_id: str) -> str:
    async with get_sessionmaker()() as session:
        cluster = await session.get(Cluster, cluster_id)
        if cluster is None:
            return "missing"
        await refresh_cluster(session, cluster)
        drafted = await maybe_draft(session, cluster, "refresh")
        await session.commit()
        return "drafted" if drafted else "unchanged"

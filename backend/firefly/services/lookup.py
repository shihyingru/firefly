"""
查詢服務 / Lookup service(文件 03 查詢路徑、文件 06 /lookup)。

流程 / Flow: 正規化 → 快取 → 快照 → 叢集 → 卡片;未命中則排程 Stage 0 任務並回 processing。
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import CardState, Cluster, ContextCard, FetchStatus, PostSnapshot
from ..workers.queue import dispatch_process_url
from .cards import card_public_view
from .hashing import url_key
from .redis_client import get_redis

CACHE_TTL = 300


@dataclass
class LookupResult:
    status: str  # displayed | candidate | no_signal | processing | unfetchable
    http: int
    card: dict | None = None
    cluster_id: str | None = None
    retry_after: int | None = None

    def body(self) -> dict:
        if self.status == "processing":
            return {"status": "processing", "retry_after": self.retry_after or 5}
        if self.status == "unfetchable":
            return {"status": "unfetchable"}
        return {"status": self.status, "cluster_id": self.cluster_id, "card": self.card}


async def lookup(session: AsyncSession, normalized_url: str) -> LookupResult:
    r = get_redis()
    ck = f"card:{url_key(normalized_url)}"
    cached = await r.get(ck)
    if cached:
        d = json.loads(cached)
        return LookupResult(d["status"], 200, d.get("card"), d.get("cluster_id"))

    snap = await session.scalar(select(PostSnapshot).where(PostSnapshot.source_url == normalized_url))
    if snap is None:
        session.add(PostSnapshot(source_url=normalized_url, platform=_platform(normalized_url), fetch_status=FetchStatus.pending))
        await session.commit()
        await dispatch_process_url(normalized_url)
        return LookupResult("processing", 202, retry_after=5)
    if snap.fetch_status == FetchStatus.pending:
        return LookupResult("processing", 202, retry_after=5)
    if snap.fetch_status == FetchStatus.unfetchable:
        return LookupResult("unfetchable", 422)
    if snap.cluster_id is None:
        return LookupResult("no_signal", 200, None, None)

    cluster = await session.get(Cluster, snap.cluster_id)
    card = None
    if cluster and cluster.current_card_id:
        card = await session.get(ContextCard, cluster.current_card_id)
    if card is None or card.state in (CardState.draft, CardState.not_displayed):
        # 叢集已成立但卡片未就緒:起草中 / cluster exists, card not ready: drafting (doc 14: silent, not wrong)
        return LookupResult("processing", 202, retry_after=10, cluster_id=str(snap.cluster_id))
    view = card_public_view(card)
    result = LookupResult(card.state.value, 200, view, str(cluster.id))
    await r.set(ck, json.dumps({"status": result.status, "card": view, "cluster_id": result.cluster_id}), ex=CACHE_TTL)
    return result


def _platform(url: str):
    from .urlnorm import detect_platform

    return detect_platform(url)


async def invalidate_url_cache(normalized_url: str) -> None:
    await get_redis().delete(f"card:{url_key(normalized_url)}")

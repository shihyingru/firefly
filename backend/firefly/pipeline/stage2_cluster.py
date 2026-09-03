"""
Stage 2:語意聚類 / Semantic clustering(文件 04)。

- 歸屬:新貼文向既有叢集質心做近鄰檢索,cosine ≥ θ_join 歸入;否則為孤立點。
- 成簇:孤立點彼此相似達標且數量 ≥ K → 成立新叢集。
- 生命週期:active → dormant(dormant_days 無新增)→ archived;dormant 復活 → 卡片複審。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_config
from ..models import Cluster, ClusterStatus, FetchStatus, PostSnapshot
from ..services.audit import audit
from .embedding import cosine, get_embedder
from .stage1_fingerprint import build_signal_set


def _mean(vectors: list[list[float]]) -> list[float]:
    n = len(vectors)
    dim = len(vectors[0])
    acc = [0.0] * dim
    for v in vectors:
        for i, x in enumerate(v):
            acc[i] += x
    m = [x / n for x in acc]
    norm = sum(x * x for x in m) ** 0.5 or 1.0
    return [x / norm for x in m]


async def ensure_embedding(snap: PostSnapshot) -> None:
    if snap.embedding is None and snap.content_text:
        snap.embedding = get_embedder().embed([snap.content_text])[0]


async def assign_or_form(session: AsyncSession, snap: PostSnapshot) -> tuple[Cluster | None, str]:
    """回傳 (cluster, event);event ∈ {assigned, formed, isolated, revived}。/ returns (cluster, event)."""
    cfg = get_config().clustering
    await ensure_embedding(snap)
    if snap.embedding is None:
        return None, "isolated"
    vec = list(snap.embedding)

    # 1) 近鄰叢集 / nearest cluster by centroid
    stmt = (
        select(Cluster, Cluster.centroid.cosine_distance(vec).label("d"))
        .where(Cluster.status.in_((ClusterStatus.forming, ClusterStatus.active, ClusterStatus.dormant)), Cluster.centroid.is_not(None))
        .order_by(Cluster.centroid.cosine_distance(vec))
        .limit(1)
    )
    row = (await session.execute(stmt)).first()
    if row is not None:
        cluster, d = row
        if 1.0 - float(d) >= cfg.theta_join:
            event = "revived" if cluster.status == ClusterStatus.dormant else "assigned"
            snap.cluster_id = cluster.id
            cluster.status = ClusterStatus.active
            await _refresh(session, cluster)
            return cluster, event

    # 2) 孤立點成簇 / form from isolated points
    iso_stmt = (
        select(PostSnapshot)
        .where(
            PostSnapshot.cluster_id.is_(None),
            PostSnapshot.fetch_status == FetchStatus.ok,
            PostSnapshot.embedding.is_not(None),
            PostSnapshot.id != snap.id,
            PostSnapshot.embedding.cosine_distance(vec) <= 1.0 - cfg.theta_join,
        )
        .order_by(PostSnapshot.embedding.cosine_distance(vec))
        .limit(200)
    )
    siblings = list((await session.scalars(iso_stmt)).all())
    # 互相似度:成員兩兩皆 ≥ θ_join 的簡化版——以新貼文為錨,再過濾與彼此相似者 / mutual-similarity (anchor-based)
    members = [snap]
    for s in siblings:
        if all(cosine(list(s.embedding), list(m.embedding)) >= cfg.theta_join for m in members):
            members.append(s)
    if len(members) < cfg.k_min_posts:
        return None, "isolated"
    cluster = Cluster(status=ClusterStatus.active, centroid=_mean([list(m.embedding) for m in members]))
    session.add(cluster)
    await session.flush()
    for m in members:
        m.cluster_id = cluster.id
    await _refresh(session, cluster)
    await audit(session, "cluster", str(cluster.id), "formed", {"post_count": cluster.post_count, "account_count": cluster.account_count, "theta_join": cfg.theta_join, "k": cfg.k_min_posts, "embedder": get_embedder().name})
    return cluster, "formed"


async def cluster_posts(session: AsyncSession, cluster_id: uuid.UUID) -> list[PostSnapshot]:
    return list((await session.scalars(select(PostSnapshot).where(PostSnapshot.cluster_id == cluster_id, PostSnapshot.fetch_status == FetchStatus.ok))).all())


async def _refresh(session: AsyncSession, cluster: Cluster) -> None:
    await session.flush()
    posts = await cluster_posts(session, cluster.id)
    cluster.post_count = len(posts)
    cluster.account_count = len({p.author_handle for p in posts if p.author_handle})
    times = [p.posted_at for p in posts if p.posted_at]
    cluster.last_post_at = max(times) if times else cluster.last_post_at
    cluster.updated_at = datetime.now(timezone.utc)
    vecs = [list(p.embedding) for p in posts if p.embedding is not None]
    if vecs:
        cluster.centroid = _mean(vecs)
    cluster.signal_summary = await build_signal_set(session, posts, get_embedder().name)


async def refresh_cluster(session: AsyncSession, cluster: Cluster) -> None:
    await _refresh(session, cluster)


async def lifecycle_sweep(session: AsyncSession, now: datetime | None = None) -> dict:
    """active → dormant → archived(文件 04 生命週期)。/ lifecycle transitions."""
    cfg = get_config().clustering
    now = now or datetime.now(timezone.utc)
    dormant_cut = now - timedelta(days=cfg.dormant_days)
    archive_cut = now - timedelta(days=cfg.dormant_days + cfg.archive_after_dormant_days)
    r1 = await session.execute(
        update(Cluster).where(Cluster.status == ClusterStatus.active, Cluster.updated_at < dormant_cut).values(status=ClusterStatus.dormant)
    )
    r2 = await session.execute(
        update(Cluster).where(Cluster.status == ClusterStatus.dormant, Cluster.updated_at < archive_cut).values(status=ClusterStatus.archived)
    )
    n1, n2 = r1.rowcount or 0, r2.rowcount or 0
    if n1 or n2:
        await audit(session, "cluster", None, "lifecycle_sweep", {"to_dormant": n1, "to_archived": n2})
    return {"to_dormant": n1, "to_archived": n2}


async def count_active_clusters(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count()).select_from(Cluster).where(Cluster.status == ClusterStatus.active)) or 0)

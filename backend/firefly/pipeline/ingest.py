"""
攝入 adapter / Ingestion adapters(D-006):A 查詢觸發同伴搜尋、B 標籤巡檢、C 網域回查。
皆走官方 keyword_search,只取公開貼文;關鍵詞/標籤清單版本化(config);日額度留餘裕。
"""
from __future__ import annotations

import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_config
from ..models import DomainSignal, FetchStatus, Platform, PostSnapshot
from ..services.audit import audit
from ..services.hashing import content_hash
from ..services.urlnorm import InvalidURL, extract_urls, normalize_url
from .threads_client import ThreadsAPI, ThreadsMedia

_CJK_RUN = re.compile(r"[一-鿿]{4,}")
_HASHTAG = re.compile(r"#([^\s#]{2,30})")
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_-]{3,}")
STOP = {"https", "http", "www", "com", "this", "that", "with", "from", "have", "your"}


def extract_keywords(text: str, max_terms: int = 3) -> list[str]:
    """關鍵詞:hashtag 優先,其次最長的中文連續段、最常見英文詞。/ hashtags first, then longest CJK runs, then frequent words."""
    text = re.sub(r"https?://\S+", " ", text or "")
    terms: list[str] = []
    terms += [h for h in _HASHTAG.findall(text)]
    runs = sorted(set(_CJK_RUN.findall(text)), key=len, reverse=True)
    terms += [r[:12] for r in runs]
    words = Counter(w.lower() for w in _WORD.findall(text) if w.lower() not in STOP)
    terms += [w for w, _ in words.most_common(3)]
    seen, out = set(), []
    for t in terms:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out[:max_terms]


async def upsert_media(session: AsyncSession, m: ThreadsMedia) -> PostSnapshot | None:
    """搜尋結果 → 快照(公開貼文、公開代號)。/ search result → snapshot."""
    if not m.permalink:
        return None
    try:
        url = normalize_url(m.permalink)
    except InvalidURL:
        return None
    snap = await session.scalar(select(PostSnapshot).where(PostSnapshot.source_url == url))
    if snap is None:
        snap = PostSnapshot(source_url=url, platform=Platform.threads)
        session.add(snap)
    if snap.fetch_status != FetchStatus.ok:
        snap.author_handle = m.username
        snap.content_text = m.text
        snap.content_hash = content_hash(m.text)
        snap.posted_at = m.timestamp
        links = extract_urls(m.text)
        if m.link_attachment_url:
            links.append(m.link_attachment_url)
        snap.external_links = links
        snap.fetch_status = FetchStatus.ok
        await session.flush()
    return snap


async def sibling_search(session: AsyncSession, api: ThreadsAPI, snap: PostSnapshot) -> list[PostSnapshot]:
    """策略 A / strategy A."""
    cfg = get_config().ingestion
    terms = extract_keywords(snap.content_text or "")[: cfg.sibling_search_per_lookup]
    found: list[PostSnapshot] = []
    for t in terms:
        for m in api.keyword_search(t):
            s = await upsert_media(session, m)
            if s is not None and s.id != snap.id:
                found.append(s)
    await audit(session, "ingest", None, "sibling_search", {"terms": len(terms), "results": len(found)})
    return found


async def tag_patrol(session: AsyncSession, api: ThreadsAPI) -> list[PostSnapshot]:
    """策略 B / strategy B."""
    found: list[PostSnapshot] = []
    for tag in get_config().ingestion.tags:
        for m in api.keyword_search(tag, mode="TAG"):
            s = await upsert_media(session, m)
            if s is not None:
                found.append(s)
    await audit(session, "ingest", None, "tag_patrol", {"tags": len(get_config().ingestion.tags), "results": len(found)})
    return found


async def domain_lookback(session: AsyncSession, api: ThreadsAPI) -> list[PostSnapshot]:
    """策略 C / strategy C."""
    domains = (await session.scalars(select(DomainSignal.domain).where(DomainSignal.removed_at.is_(None)))).all()
    found: list[PostSnapshot] = []
    for d in sorted(set(domains)):
        for m in api.keyword_search(d):
            s = await upsert_media(session, m)
            if s is not None:
                found.append(s)
    await audit(session, "ingest", None, "domain_lookback", {"domains": len(set(domains)), "results": len(found)})
    return found

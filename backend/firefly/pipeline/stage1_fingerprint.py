"""
Stage 1:指紋偵測 / Fingerprint detection(文件 04)。

三類訊號各自獨立;只列證據與計算方式,不做加總、不下結論。
Three signal families, scored independently; evidence + method only, never aggregated into a verdict.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import REPO_ROOT, get_config
from ..models import DomainSignal, PostSnapshot

METHOD_DOC = "docs/zh-TW/04-AI管線規格.md#stage-1指紋偵測"
METHOD_CODE = "backend/firefly/pipeline/stage1_fingerprint.py"

EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF☀-➿\U0001F900-\U0001F9FF]")
HASHTAG_RE = re.compile(r"(?:^|\s)#\S+")
URL_RE = re.compile(r"https?://\S+")


@lru_cache
def load_rules() -> dict:
    p = Path(get_config().fingerprint.rules_path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    if not p.exists():
        return {"version": 0, "rules": []}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {"version": 0, "rules": []}


# ---------- 排版指紋 / formatting ----------
def _rule_short_lines(text: str, p: dict) -> bool:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < p.get("min_lines", 4):
        return False
    body = [ln for ln in lines if not HASHTAG_RE.fullmatch(" " + ln)]
    if any(len(ln) > p.get("max_chars_per_line", 30) for ln in body):
        return False
    if p.get("require_emoji") and not EMOJI_RE.search(text):
        return False
    if p.get("trailing_hashtag") and not lines[-1].lstrip().startswith("#"):
        return False
    return True


def _rule_link_only(text: str, p: dict) -> bool:
    links = URL_RE.findall(text)
    rest = URL_RE.sub("", text).strip()
    return len(links) == p.get("exact_links", 1) and len(rest) <= p.get("max_text_chars", 20)


RULE_IMPL = {"short_lines_emoji_hashtag_tail": _rule_short_lines, "repeated_link_only": _rule_link_only}


def formatting_signals(text: str) -> list[dict]:
    rules = load_rules()
    hits = []
    for r in rules.get("rules", []):
        impl = RULE_IMPL.get(r["id"])
        if impl and impl(text or "", r.get("params", {})):
            hits.append({"rule_id": r["id"], "source": r.get("source"), "rules_version": rules.get("version")})
    return hits


# ---------- 網域指紋 / domain ----------
def _domain_of(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


async def domain_signals(session: AsyncSession, links: list[str]) -> dict:
    domains = sorted({_domain_of(u) for u in links if u})
    matches: list[dict] = []
    versions: set[str] = set()
    if domains:
        rows = (
            await session.scalars(
                select(DomainSignal).where(DomainSignal.domain.in_(domains), DomainSignal.removed_at.is_(None))
            )
        ).all()
        for r in rows:
            matches.append({"domain": r.domain, "source_list": r.source_list, "list_version": r.list_version, "evidence_url": r.evidence_url})
            versions.add(r.list_version)
    return {"checked_domains": domains, "matches": matches, "list_version": max(versions) if versions else None}


# ---------- 時序指紋 / timing ----------
def timing_signals(posts: list[PostSnapshot]) -> dict:
    """同步性:T 分鐘窗口內最多幾個相異帳號;timing_chart 為分桶計數。只用非空 posted_at(D-004)。
    Synchrony: max distinct accounts within a T-minute window; chart is bucketed counts. Non-null posted_at only."""
    cfg = get_config().fingerprint
    timed = sorted([p for p in posts if p.posted_at is not None], key=lambda p: p.posted_at)
    untimed = len(posts) - len(timed)
    if not timed:
        return {"window_minutes": cfg.sync_window_minutes, "max_accounts_in_window": 0, "window_start": None, "chart": [], "n_timed": 0, "n_untimed": untimed}
    win = timedelta(minutes=cfg.sync_window_minutes)
    best, best_start = 0, timed[0].posted_at
    for i, a in enumerate(timed):
        accounts = {p.author_handle or f"?{p.id}" for p in timed[i:] if p.posted_at - a.posted_at <= win}
        if len(accounts) > best:
            best, best_start = len(accounts), a.posted_at
    bucket = timedelta(minutes=cfg.chart_bucket_minutes)
    counts: dict[datetime, int] = defaultdict(int)
    for p in timed:
        t = p.posted_at.astimezone(timezone.utc)
        floored = t - timedelta(minutes=t.minute % cfg.chart_bucket_minutes, seconds=t.second, microseconds=t.microsecond)
        counts[floored] += 1
    chart = [{"t": k.isoformat(), "n": v} for k, v in sorted(counts.items())]
    return {
        "window_minutes": cfg.sync_window_minutes,
        "max_accounts_in_window": best,
        "window_start": best_start.isoformat(),
        "bucket_minutes": int(bucket.total_seconds() // 60),
        "chart": chart,
        "n_timed": len(timed),
        "n_untimed": untimed,
    }


async def build_signal_set(session: AsyncSession, posts: list[PostSnapshot], embedder_name: str | None = None) -> dict:
    """SignalSet:三類訊號 + 原始數據 + 計算方式連結;皆可重跑。/ three families + raw data + method links; replayable."""
    fmt = [{"post_id": str(p.id), "hits": formatting_signals(p.content_text or "")} for p in posts]
    links = [u for p in posts for u in (p.external_links or [])]
    dom = await domain_signals(session, links)
    tim = timing_signals(posts)
    handles = {p.author_handle for p in posts if p.author_handle}
    return {
        "post_count": len(posts),
        "account_count": len(handles),
        "formatting": {"per_post": fmt, "hit_rate": (sum(1 for f in fmt if f["hits"]) / len(posts)) if posts else 0.0},
        "domain": dom,
        "timing": tim,
        "embedder": embedder_name,
        "method": {"doc": METHOD_DOC, "code": METHOD_CODE},
    }

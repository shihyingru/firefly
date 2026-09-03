"""
Stage 3:脈絡卡起草(確定性優先)/ Context-card drafting, deterministic-first(文件 04 v0.2,D-001、D-002、D-004)。

七個白名單欄位中六個由程式計算;original_source 預設為最早貼文,LLM(可選、預設關閉)只能從封閉候選集合挑選。
每張卡起草後經 card_schema 程式後驗證;失敗整卡退回;連續失敗進人工檢視佇列(審計事件 needs_human_review)。
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_config
from ..models import CardState, Cluster, ContextCard, PostSnapshot
from ..services.audit import audit
from .card_schema import (
    UNCONFIRMED_ZH,
    UNTRACED_ZH,
    ValidationContext,
    strip_to_whitelist,
    validate_card_fields,
)
from .llm import AnthropicChooser, SourceChooser
from .stage2_cluster import cluster_posts


def build_candidate_set(posts: list[PostSnapshot], min_shared_authors: int) -> list[str]:
    """候選集合:叢集內貼文 URL + 被 ≥N 個相異帳號分享的外部連結。/ post URLs + external links shared by ≥N distinct authors."""
    urls = [p.source_url for p in sorted(posts, key=lambda p: (p.posted_at is None, p.posted_at or datetime.max.replace(tzinfo=timezone.utc)))]
    by_link: dict[str, set[str]] = defaultdict(set)
    for p in posts:
        for u in p.external_links or []:
            by_link[u].add(p.author_handle or str(p.id))
    shared = sorted(u for u, authors in by_link.items() if len(authors) >= min_shared_authors)
    return urls + [u for u in shared if u not in urls]


def deterministic_fields(posts: list[PostSnapshot], signal_set: dict, excerpt_max: int) -> dict:
    timed = [p for p in posts if p.posted_at is not None]
    if timed:
        earliest = min(timed, key=lambda p: p.posted_at)
        earliest_seen = {"at": earliest.posted_at.isoformat(), "url": earliest.source_url}
        original = {"url": earliest.source_url, "traced": True, "method": "earliest_post"}
        excerpt_src = earliest
    else:
        earliest_seen = {"at": None, "url": None, "note": UNCONFIRMED_ZH}
        original = {"url": None, "traced": False, "note": UNTRACED_ZH}
        excerpt_src = next((p for p in posts if p.content_text), None)
    excerpt = (excerpt_src.content_text or "")[:excerpt_max] if excerpt_src else ""
    return {
        "earliest_seen": earliest_seen,
        "original_source": original,
        "account_count": signal_set["account_count"],
        "timing_chart": signal_set["timing"]["chart"],
        "archive_links": [{"url": p.source_url, "archive_url": p.archive_url} for p in posts if p.archive_url],
        "domain_note": {"matches": signal_set["domain"]["matches"], "list_version": signal_set["domain"]["list_version"]},
        "sample_excerpt": excerpt,
    }


def _posts_as_data(posts: list[PostSnapshot]) -> list[dict]:
    return [{"url": p.source_url, "author": p.author_handle, "posted_at": p.posted_at.isoformat() if p.posted_at else None, "text": p.content_text or "", "links": p.external_links or []} for p in posts]


async def draft_card(session: AsyncSession, cluster: Cluster, reason: str, chooser: SourceChooser | None = None) -> ContextCard | None:
    """起草 + 驗證 + 入庫。回傳新卡或 None(退回)。/ draft + validate + persist; returns the card or None."""
    cfg = get_config().card
    posts = await cluster_posts(session, cluster.id)
    if not posts:
        return None
    signal_set = cluster.signal_summary or {}
    if not signal_set:
        return None
    fields = deterministic_fields(posts, signal_set, cfg.sample_excerpt_max_chars)
    ctx = ValidationContext(
        post_urls={p.source_url for p in posts},
        archive_urls={p.archive_url for p in posts if p.archive_url},
        candidate_urls=set(build_candidate_set(posts, cfg.original_source_min_shared_authors)),
        signal_account_count=signal_set["account_count"],
        signal_chart=signal_set["timing"]["chart"],
        post_texts=[p.content_text or "" for p in posts],
    )

    llm_model = None
    prompt_ref = None
    if cfg.llm_enabled or chooser is not None:
        chooser = chooser or AnthropicChooser()
        candidates = build_candidate_set(posts, cfg.original_source_min_shared_authors)
        res = chooser.choose(candidates, _posts_as_data(posts))
        # 全量審計:prompt、模型、原始輸出(文件 04、12)/ full audit: prompt, model, raw output
        log = await audit(session, "cluster", str(cluster.id), "llm_call", {"model": res.model, "prompt": res.prompt, "raw_output": res.raw_output, "refused": res.refused, "choice": res.choice})
        llm_model, prompt_ref = res.model, str(log.id)
        if res.choice is not None:
            fields["original_source"] = {"url": candidates[res.choice], "traced": True, "method": "llm_choice"}

    fields = strip_to_whitelist(fields)
    errors = validate_card_fields(fields, ctx)
    if errors and llm_model:
        # LLM 提議未過驗證 → 退回 LLM 提議,改用確定性結果(文件 04:任一欄位失敗整卡退回重生)
        await audit(session, "cluster", str(cluster.id), "validation_failed", {"stage": "llm_choice", "errors": errors})
        fields = strip_to_whitelist(deterministic_fields(posts, signal_set, cfg.sample_excerpt_max_chars))
        errors = validate_card_fields(fields, ctx)
    if errors:
        await audit(session, "cluster", str(cluster.id), "validation_failed", {"stage": "deterministic", "errors": errors})
        await _maybe_human_review(session, cluster)
        return None

    version = int(await session.scalar(select(func.coalesce(func.max(ContextCard.version), 0)).where(ContextCard.cluster_id == cluster.id)) or 0) + 1
    card = ContextCard(
        cluster_id=cluster.id,
        version=version,
        fields=fields,
        llm_model=llm_model,
        prompt_ref=prompt_ref,
        validation_passed_at=datetime.now(timezone.utc),
        state=CardState.candidate,  # Phase A:查詢可見 + 待仲裁標註 / query-visible + awaiting-arbitration
    )
    session.add(card)
    await session.flush()
    prev = cluster.current_card_id
    cluster.current_card_id = card.id
    if prev:
        old = await session.get(ContextCard, prev)
        if old and old.state in (CardState.candidate, CardState.displayed):
            old.state = CardState.not_displayed
            await audit(session, "context_card", str(old.id), "state_changed", {"from": "candidate", "to": "not_displayed", "reason": "superseded", "i_c": old.quality_score, "vote_count": old.vote_count})
    await audit(session, "context_card", str(card.id), "state_changed", {"from": "draft", "to": "candidate", "reason": reason, "version": version, "i_c": None, "vote_count": 0, "llm_model": llm_model})
    return card


async def _maybe_human_review(session: AsyncSession, cluster: Cluster) -> None:
    cfg = get_config().card
    from ..models import AuditLog  # local import to avoid cycles at module import time

    n = int(await session.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.entity_type == "cluster", AuditLog.entity_id == str(cluster.id), AuditLog.event == "validation_failed")) or 0)
    if n >= cfg.max_validation_retries:
        await audit(session, "cluster", str(cluster.id), "needs_human_review", {"validation_failures": n})


def needs_redraft(cluster: Cluster, card: ContextCard | None, event: str) -> str | None:
    """觸發規則:叢集成立、無卡、dormant 復活、同文帳號數跨閾值。/ trigger: formed, no card, revived, threshold crossed."""
    if card is None:
        return "no_card"
    if event == "revived":
        return "revived"
    thresholds = get_config().card.redraft_thresholds
    prev = int(card.fields.get("account_count", 0))
    now = cluster.account_count
    crossed = [t for t in thresholds if prev < t <= now]
    return f"account_count_crossed_{crossed[-1]}" if crossed else None


async def current_card(session: AsyncSession, cluster: Cluster) -> ContextCard | None:
    return await session.get(ContextCard, cluster.current_card_id) if cluster.current_card_id else None


def card_id_str(card: ContextCard | None) -> str | None:
    return str(card.id) if card else None


__all__ = ["draft_card", "needs_redraft", "current_card", "build_candidate_set", "deterministic_fields", "card_id_str", "uuid"]

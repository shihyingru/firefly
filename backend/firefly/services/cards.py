"""卡片讀取與投票 / Card read + vote services."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import CardState, ContextCard, Contributor, Vote
from .contributors import is_eligible


def card_public_view(card: ContextCard) -> dict:
    """對外輸出:白名單欄位 + arbitration 摘要。永不含個別投票。/ Public view: whitelist fields + arbitration."""
    return {
        "card_id": str(card.id),
        "cluster_id": str(card.cluster_id),
        "version": card.version,
        "state": card.state.value,
        "fields": card.fields,
        "arbitration": {
            "i_c": card.quality_score,
            "vote_count": card.vote_count,
            "spectrum_coverage": card.spectrum_coverage,
            "label": _label(card.state),
        },
    }


def _label(state: CardState) -> dict:
    """文件 14 失效模式表的對外呈現 / doc-14 failure-mode labels."""
    if state == CardState.candidate:
        return {"zh": "脈絡待仲裁", "en": "Context awaiting arbitration"}
    if state == CardState.displayed:
        return {"zh": "已通過跨光譜仲裁", "en": "Passed cross-spectrum arbitration"}
    return {"zh": "", "en": ""}


async def get_visible_card(session: AsyncSession, card_id: uuid.UUID) -> ContextCard | None:
    """not_displayed / draft 對外視為不存在(失效時沉默)。/ hidden states look non-existent (fail silent)."""
    card = await session.get(ContextCard, card_id)
    if card is None or card.state not in (CardState.candidate, CardState.displayed):
        return None
    return card


async def cast_vote(session: AsyncSession, contributor: Contributor, card: ContextCard, helpful: bool) -> Vote:
    """冪等覆寫 / idempotent upsert. weight=0 表示尚未達資格(文件 14 T1 第二層)。"""
    weight = 1.0 if is_eligible(contributor) else 0.0
    stmt = pg_insert(Vote).values(
        contributor_id=contributor.id, card_id=card.id, helpful=helpful, weight=weight
    ).on_conflict_do_update(
        index_elements=[Vote.contributor_id, Vote.card_id],
        set_={"helpful": helpful, "weight": weight, "updated_at": func.now()},
    )
    await session.execute(stmt)
    card.vote_count = int(
        await session.scalar(select(func.count()).select_from(Vote).where(Vote.card_id == card.id, Vote.weight > 0)) or 0
    )
    await session.flush()
    return await session.get(Vote, (contributor.id, card.id))


async def phase_a_queue(session: AsyncSession, contributor: Contributor, limit: int) -> list[ContextCard]:
    """D-010:排除已投卡,有效票最少優先,同數隨機。/ exclude voted, fewest valid votes first, random ties."""
    voted = select(Vote.card_id).where(Vote.contributor_id == contributor.id)
    stmt = (
        select(ContextCard)
        .where(ContextCard.state == CardState.candidate, ContextCard.id.not_in(voted))
        .order_by(ContextCard.vote_count.asc(), func.random())
        .limit(limit)
    )
    return list((await session.scalars(stmt)).all())

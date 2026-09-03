"""
橋接引擎批次重算 / Bridging engine batch recompute(文件 05)。

Phase A(活躍仲裁者 < phase_a_max_active_arbiters):
  只累積投票矩陣;計算 i_c 與光譜覆蓋供儀表板參考,**不做顯示裁決**(卡片維持 candidate)。
Phase B:
  candidate → displayed:i_c ≥ θ_helpful 且有效票 ≥ N_min;displayed → candidate:i_c < θ_helpful − 遲滯帶。
  光譜失衡(coverage 不足)→ 不做裁決(文件 14 失效模式:沉默)。
所有狀態變更寫入 audit_log(時間、前後狀態、i_c、投票數);立場向量僅存 contributor.stance_vector,永不對外。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_config
from ..models import CardState, ContextCard, Contributor, Vote
from ..services.audit import audit
from .matrix import Rating, burst_zscore, factorize, spectrum_coverage

ACTIVE_WINDOW_DAYS = 30
MIN_COVERAGE = 0.2  # TODO(calibrate) 光譜失衡門檻 / spectrum-imbalance threshold


async def count_active_arbiters(session: AsyncSession, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=ACTIVE_WINDOW_DAYS)
    return int(await session.scalar(select(func.count(func.distinct(Vote.contributor_id))).where(Vote.weight > 0, Vote.updated_at >= since)) or 0)


async def current_phase(session: AsyncSession) -> str:
    return "A" if await count_active_arbiters(session) < get_config().bridging.phase_a_max_active_arbiters else "B"


async def detect_bursts(session: AsyncSession, now: datetime | None = None) -> int:
    """單卡投票速率 z-score 異常 → 該時窗投票降權(weight×0.25)並審計(只公開模式,不公開人)。"""
    cfg = get_config().bridging
    now = now or datetime.now(timezone.utc)
    win = timedelta(minutes=cfg.burst_window_minutes)
    flagged = 0
    card_ids = (await session.scalars(select(Vote.card_id).distinct())).all()
    for cid in card_ids:
        votes = (await session.scalars(select(Vote).where(Vote.card_id == cid, Vote.weight > 0))).all()
        if len(votes) < 10:
            continue
        first = min(v.created_at for v in votes)
        n_windows = max(3, int((now - first) / win) + 1)

        def _idx(v, n=n_windows):  # 以 now 為錨的時窗索引;最後一窗 = 最近 window_minutes / windows anchored at now
            return max(0, n - 1 - int((now - v.created_at) / win))

        counts = [0] * n_windows
        for v in votes:
            counts[_idx(v)] += 1
        z = burst_zscore(counts)
        if z >= cfg.burst_zscore_threshold:
            latest = [v for v in votes if _idx(v) == n_windows - 1]
            for v in latest:
                v.weight = round(v.weight * 0.25, 4)
            flagged += 1
            await audit(session, "context_card", str(cid), "burst_downweighted", {"window_minutes": cfg.burst_window_minutes, "votes_in_window": len(latest), "zscore": round(z, 2)})
    return flagged


async def recompute(session: AsyncSession, apply_display: bool | None = None) -> dict:
    """批次全量重算。apply_display=None 時依 Phase 決定;Phase A 永不裁決。/ full recompute; Phase A never decides."""
    cfg = get_config().bridging
    phase = await current_phase(session)
    if apply_display is None:
        apply_display = phase == "B"
    await detect_bursts(session)

    all_votes = (await session.scalars(select(Vote).where(Vote.weight > 0))).all()
    # 投票者剪枝(Community Notes 慣例):投票數 < min_votes_per_rater 的代號不進分解;單卡灌票代號因此權重趨零(文件 14 T1)
    per_user: dict = {}
    for v in all_votes:
        per_user[v.contributor_id] = per_user.get(v.contributor_id, 0) + 1
    votes = [v for v in all_votes if per_user[v.contributor_id] >= cfg.min_votes_per_rater]
    users = sorted({v.contributor_id for v in votes}, key=str)
    cards = sorted({v.card_id for v in votes}, key=str)
    u_idx = {u: i for i, u in enumerate(users)}
    c_idx = {c: i for i, c in enumerate(cards)}
    ratings = [Rating(u_idx[v.contributor_id], c_idx[v.card_id], 1.0 if v.helpful else 0.0, v.weight) for v in votes]
    res = factorize(ratings, len(users), len(cards), cfg.factor_dim, cfg.lambda_intercept, cfg.lambda_factor)

    # 立場向量:僅引擎內部 / stance vectors: engine-internal only
    contribs = {c.id: c for c in (await session.scalars(select(Contributor).where(Contributor.id.in_(users)))).all()} if users else {}
    for u, i in u_idx.items():
        contribs[u].stance_vector = [float(x) for x in res.f_u[i]]

    raters_by_card: dict = {c: [] for c in cards}
    for v in votes:
        raters_by_card[v.card_id].append(u_idx[v.contributor_id])
    changes = 0
    card_rows = {c.id: c for c in (await session.scalars(select(ContextCard).where(ContextCard.id.in_(cards)))).all()} if cards else {}
    for cid, j in c_idx.items():
        card = card_rows[cid]
        i_c = float(res.i_c[j])
        n_valid = len(raters_by_card[cid])
        cov = spectrum_coverage(res.f_u[np.array(raters_by_card[cid])], cfg.n_min_votes) if n_valid else None
        card.quality_score = round(i_c, 4)
        card.vote_count = n_valid
        card.spectrum_coverage = cov
        if not apply_display:
            continue
        old = card.state
        new = old
        if old == CardState.candidate and n_valid >= cfg.n_min_votes and i_c >= cfg.theta_helpful and (cov or 0.0) >= MIN_COVERAGE:
            new = CardState.displayed
        elif old == CardState.displayed and i_c < cfg.theta_helpful - cfg.hysteresis:
            new = CardState.candidate
        if new != old:
            card.state = new
            changes += 1
            await audit(session, "context_card", str(card.id), "state_changed", {"from": old.value, "to": new.value, "i_c": card.quality_score, "vote_count": n_valid, "spectrum_coverage": cov, "theta_helpful": cfg.theta_helpful, "lambda_intercept": cfg.lambda_intercept, "lambda_factor": cfg.lambda_factor})
    summary = {"phase": phase, "apply_display": apply_display, "users": len(users), "cards": len(cards), "votes": len(votes), "iterations": res.iterations, "state_changes": changes, "mu": round(res.mu, 4)}
    await audit(session, "bridging", None, "recompute", summary)
    await session.flush()
    return summary

"""橋接引擎 / bridging engine: simulated-data factorization, Sybil collapse, Phase A/B behaviour, hysteresis."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from firefly.bridging.engine import current_phase, recompute
from firefly.bridging.matrix import Rating, burst_zscore, factorize, spectrum_coverage
from firefly.models import (
    CardState,
    Cluster,
    ClusterStatus,
    ContextCard,
    Contributor,
    ContributorOrigin,
    Vote,
)

FIELDS = {"earliest_seen": {"at": None, "url": None, "note": "未能確認"}, "original_source": {"url": None, "traced": False, "note": "未能追溯"}, "account_count": 3, "timing_chart": [], "archive_links": [], "domain_note": {"matches": [], "list_version": None}, "sample_excerpt": ""}


def _simulate(n_per_faction=40, sybils=0, seed=1):
    """兩個陣營 + 三張卡:橋接卡(雙方都認可)、陣營卡(僅 A 認可)、劣質卡(雙方都不認可)。"""
    rng = np.random.default_rng(seed)
    ratings = []
    users = 0
    for faction in (0, 1):
        for _ in range(n_per_faction):
            u = users
            users += 1
            ratings.append(Rating(u, 0, float(rng.random() < 0.9)))  # bridging
            ratings.append(Rating(u, 1, float(rng.random() < (0.9 if faction == 0 else 0.1))))  # partisan
            ratings.append(Rating(u, 2, float(rng.random() < 0.1)))  # bad
    for _ in range(sybils):
        # 養號型灌票:也對其他卡投「合理」票以通過剪枝,再集中拉抬陣營卡(文件 14 T2)
        # sleeper-style brigade: rate other cards plausibly to pass pruning, then boost the partisan card
        ratings += [Rating(users, 0, 1.0), Rating(users, 1, 1.0), Rating(users, 2, 0.0)]
        users += 1
    return ratings, users


def test_factorization_separates_bridging_from_partisan():
    ratings, n = _simulate()
    res = factorize(ratings, n, 3, dim=1)
    i_bridge, i_partisan, i_bad = res.i_c
    assert i_bridge > 0.40 > i_partisan and i_bad < i_partisan
    # 陣營在第一維分離 / factions separate along the first factor
    signs = np.sign(res.f_u[:, 0])
    s0 = np.sign(signs[:40].mean())
    assert np.mean(signs[:40] == s0) >= 0.9 and np.mean(signs[40:80] == s0) <= 0.1


def test_sybil_gain_is_sublinear_and_collapses():
    base, n0 = _simulate()
    r30, n30 = _simulate(sybils=30)
    r300, n300 = _simulate(sybils=300)
    p0 = factorize(base, n0, 3).i_c[1]
    p30 = factorize(r30, n30, 3).i_c[1]
    res300 = factorize(r300, n300, 3)
    p300 = res300.i_c[1]
    gain30, gain300 = p30 - p0, p300 - p0
    assert gain300 < gain30 * 10 * 0.5, (gain30, gain300)  # 10 倍票數,增益遠低於 10 倍 / 10x votes, far less than 10x gain
    sy = np.sign(res300.f_u[80:, 0])
    assert abs(sy.mean()) > 0.9  # 行為一致的代號群塌縮為同一立場向量 / sock puppets collapse to one sign
    assert p300 < res300.i_c[0]  # 橋接卡仍高於被灌票的陣營卡 / bridging card still wins


def test_spectrum_coverage_and_burst():
    assert spectrum_coverage(np.array([[1.0], [-1.0], [0.5], [-0.2], [0.1]]), 5) == 0.8
    assert spectrum_coverage(np.array([[1.0], [1.0], [1.0], [1.0], [1.0]]), 5) == 0.0
    assert spectrum_coverage(np.array([[1.0]]), 5) is None
    assert burst_zscore([2, 3, 2, 3, 40]) > 3 and burst_zscore([2, 3, 2, 3, 3]) <= 1.5


async def _seed(db, n_users=6):
    cluster = Cluster(status=ClusterStatus.active)
    db.add(cluster)
    await db.flush()
    card = ContextCard(cluster_id=cluster.id, version=1, fields=FIELDS, state=CardState.candidate)
    db.add(card)
    users = [Contributor(origin=ContributorOrigin.device, origin_key_hash=f"h{i}-{uuid.uuid4().hex}") for i in range(n_users)]
    db.add_all(users)
    await db.flush()
    return card, users


@pytest.mark.asyncio
async def test_phase_a_computes_but_never_decides(db):
    card, users = await _seed(db)
    other = ContextCard(cluster_id=card.cluster_id, version=2, fields=FIELDS, state=CardState.candidate)
    db.add(other)
    await db.flush()
    for u in users:
        db.add(Vote(contributor_id=u.id, card_id=card.id, helpful=True, weight=1.0))
        db.add(Vote(contributor_id=u.id, card_id=other.id, helpful=False, weight=1.0))
    await db.commit()
    assert await current_phase(db) == "A"
    s = await recompute(db)
    await db.commit()
    await db.refresh(card)
    assert s["phase"] == "A" and s["apply_display"] is False and s["state_changes"] == 0
    assert card.state == CardState.candidate and card.quality_score is not None and card.vote_count == 6
    assert users[0].stance_vector is not None and len(users[0].stance_vector) == 1


@pytest.mark.asyncio
async def test_phase_b_display_and_hysteresis(db, monkeypatch):
    from firefly.config import get_config

    cfg = get_config().bridging
    monkeypatch.setattr(cfg, "phase_a_max_active_arbiters", 0)  # 強制 Phase B / force Phase B
    card, users = await _seed(db, n_users=8)
    # 光譜平衡:需要投票者在立場上分裂,先給一張陣營卡塑造立場 / shape stances with a partisan card first
    partisan = ContextCard(cluster_id=card.cluster_id, version=2, fields=FIELDS, state=CardState.not_displayed)
    bad = ContextCard(cluster_id=card.cluster_id, version=3, fields=FIELDS, state=CardState.not_displayed)
    db.add_all([partisan, bad])
    await db.flush()
    for k, u in enumerate(users):
        db.add(Vote(contributor_id=u.id, card_id=card.id, helpful=True, weight=1.0))
        db.add(Vote(contributor_id=u.id, card_id=partisan.id, helpful=(k % 2 == 0), weight=1.0))
        db.add(Vote(contributor_id=u.id, card_id=bad.id, helpful=False, weight=1.0))
    await db.commit()
    s = await recompute(db)
    await db.commit()
    await db.refresh(card)
    assert s["phase"] == "B" and card.state == CardState.displayed and card.quality_score >= cfg.theta_helpful

    # 跌破 θ − 遲滯帶 → 退回 candidate / drop below θ − hysteresis → back to candidate
    from sqlalchemy import update

    await db.execute(update(Vote).where(Vote.card_id == card.id).values(helpful=False))
    await db.commit()
    await recompute(db)
    await db.commit()
    await db.refresh(card)
    assert card.state == CardState.candidate


@pytest.mark.asyncio
async def test_burst_downweights_latest_window(db):
    from firefly.bridging.engine import detect_bursts

    card, users = await _seed(db, n_users=1)
    extra = [Contributor(origin=ContributorOrigin.device, origin_key_hash=f"b{i}-{uuid.uuid4().hex}") for i in range(60)]
    db.add_all(extra)
    await db.flush()
    t0 = datetime.now(timezone.utc) - timedelta(hours=6)
    for i, u in enumerate(extra):
        # 前 5 小時每小時 2 票,最後一小時 50 票 / 2 per hour for 5 hours, then 50 in the last hour
        at = t0 + timedelta(hours=min(i // 2, 4)) if i < 10 else t0 + timedelta(hours=5, minutes=(i % 50) + 1)
        db.add(Vote(contributor_id=u.id, card_id=card.id, helpful=True, weight=1.0, created_at=at))
    await db.commit()
    card_id = card.id
    assert await detect_bursts(db) == 1
    await db.commit()
    db.expire_all()
    votes = (await db.execute(Vote.__table__.select().where(Vote.card_id == card_id))).all()
    assert sum(1 for v in votes if v.weight < 1.0) == 50

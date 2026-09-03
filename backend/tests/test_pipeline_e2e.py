"""Stage 0-3 端到端 / end-to-end: mock posts → cluster → deterministic card → /lookup candidate."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from firefly.models import AuditLog, Cluster, ContextCard, PostSnapshot
from firefly.pipeline.adapters import seed_mock_post
from firefly.pipeline.jobs import _process_url

T0 = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
BASE = "這款產品真的太神了!大家快去看 👉 https://shop.example.tld/x\n#好物 #推薦"


def _url(i):
    return f"https://www.threads.com/@acct{i}/post/P{i:03d}"


@pytest.fixture(autouse=True)
def hash_embedder(monkeypatch):
    monkeypatch.setenv("FIREFLY_EMBEDDER", "hash")
    from firefly.pipeline import embedding

    embedding.get_embedder.cache_clear()
    yield
    embedding.get_embedder.cache_clear()


@pytest.mark.asyncio
async def test_three_similar_posts_form_cluster_and_card(client, db):
    for i in range(3):
        seed_mock_post(_url(i), f"acct{i}", BASE.replace("!", "!" * (i + 1)), T0 + timedelta(minutes=3 * i))
        r = await client.post("/v1/lookup", json={"url": _url(i)})
        assert r.status_code == 202
    r = await client.post("/v1/lookup", json={"url": _url(0)})
    assert r.status_code == 200 and r.json()["status"] == "candidate", r.json()
    f = r.json()["card"]["fields"]
    assert f["account_count"] == 3
    assert f["earliest_seen"]["url"] == _url(0) and f["original_source"]["method"] == "earliest_post"
    assert sum(b["n"] for b in f["timing_chart"]) == 3
    assert f["sample_excerpt"].startswith("這款產品真的太神了!")
    assert f["domain_note"]["matches"] == []
    cluster = await db.scalar(select(Cluster))
    assert cluster.post_count == 3 and cluster.signal_summary["timing"]["max_accounts_in_window"] == 3
    assert cluster.signal_summary["embedder"] == "hash-ngram"
    events = [a.event for a in (await db.scalars(select(AuditLog))).all()]
    assert "formed" in events and "state_changed" in events

    # 第 4 則不相似 → 孤立、無訊號 / 4th dissimilar → isolated, no_signal
    other = "https://www.threads.com/@zed/post/Z1"
    seed_mock_post(other, "zed", "今天去爬山,風景很美,天氣也很好。回家路上買了一杯咖啡。", T0)
    await client.post("/v1/lookup", json={"url": other})
    r = await client.post("/v1/lookup", json={"url": other})
    assert r.json()["status"] == "no_signal"

    # 第 4 個相似帳號加入 → 跨越閾值前不重起草(3→4 未跨 5)/ 4th similar joins; no redraft (3→4 crosses nothing)
    seed_mock_post(_url(9), "acct9", BASE, T0 + timedelta(minutes=10))
    await _process_url(_url(9))
    assert len((await db.scalars(select(ContextCard))).all()) == 1
    snap = await db.scalar(select(PostSnapshot).where(PostSnapshot.source_url == _url(9)))
    assert snap.cluster_id == cluster.id


@pytest.mark.asyncio
async def test_untimed_posts_yield_unconfirmed_and_untraced(client, db):
    for i in range(3):
        seed_mock_post(_url(i), f"acct{i}", BASE, None)
        await client.post("/v1/lookup", json={"url": _url(i)})
    r = await client.post("/v1/lookup", json={"url": _url(0)})
    f = r.json()["card"]["fields"]
    assert f["earliest_seen"] == {"at": None, "url": None, "note": "未能確認"}
    assert f["original_source"] == {"url": None, "traced": False, "note": "未能追溯"}
    assert f["timing_chart"] == [] and f["account_count"] == 3


@pytest.mark.asyncio
async def test_redraft_on_threshold_and_supersede(client, db, monkeypatch):
    from firefly.config import get_config

    monkeypatch.setattr(get_config().card, "redraft_thresholds", [3, 4])
    for i in range(3):
        seed_mock_post(_url(i), f"acct{i}", BASE, T0)
        await _process_url(_url(i))
    seed_mock_post(_url(3), "acct3", BASE, T0)
    await _process_url(_url(3))
    cards = (await db.scalars(select(ContextCard).order_by(ContextCard.version))).all()
    assert [c.version for c in cards] == [1, 2]
    assert cards[0].state.value == "not_displayed" and cards[1].state.value == "candidate"
    assert cards[1].fields["account_count"] == 4

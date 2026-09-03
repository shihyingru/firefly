"""端到端 API 測試 / End-to-end API tests for Wave 1.1(文件 06)。"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from firefly.models import CardState, Cluster, ClusterStatus, ContextCard, Contributor, PostSnapshot, Vote
from firefly.pipeline.adapters import seed_mock_post

URL = "https://www.threads.com/@alice/post/AAA111"


async def _device(client) -> str:
    r = await client.post("/v1/devices", json={})
    assert r.status_code == 201
    return r.json()["device_token"]


async def _seed_cluster_with_card(db, url: str) -> ContextCard:
    snap = await db.scalar(select(PostSnapshot).where(PostSnapshot.source_url == url))
    cluster = Cluster(status=ClusterStatus.active, post_count=3, account_count=3)
    db.add(cluster)
    await db.flush()
    snap.cluster_id = cluster.id
    card = ContextCard(
        cluster_id=cluster.id,
        version=1,
        state=CardState.candidate,
        fields={
            "earliest_seen": {"at": "2026-09-01T00:00:00+00:00", "url": url},
            "original_source": {"url": url, "traced": True},
            "account_count": 3,
            "timing_chart": [{"t": "2026-09-01T00:00:00+00:00", "n": 3}],
            "archive_links": [],
            "domain_note": {"matches": [], "list_version": "0"},
            "sample_excerpt": "測試貼文",
        },
    )
    db.add(card)
    await db.flush()
    cluster.current_card_id = card.id
    await db.commit()
    return card


@pytest.mark.asyncio
async def test_healthz(client):
    r = await client.get("/healthz")
    assert r.status_code == 200 and r.json()["ok"] is True


@pytest.mark.asyncio
async def test_lookup_processing_then_no_signal_then_card(client, db):
    seed_mock_post(URL, "alice", "測試貼文 內容", datetime(2026, 9, 1, tzinfo=UTC))
    r = await client.post("/v1/lookup", json={"url": "https://threads.net/@alice/post/AAA111?utm_source=x"})
    assert r.status_code == 202 and r.json()["status"] == "processing" and "Retry-After" in r.headers
    r = await client.post("/v1/lookup", json={"url": URL})
    assert r.status_code == 200 and r.json()["status"] == "no_signal"
    await _seed_cluster_with_card(db, URL)
    r = await client.post("/v1/lookup", json={"url": URL})
    body = r.json()
    assert r.status_code == 200 and body["status"] == "candidate"
    assert body["card"]["arbitration"]["label"]["zh"] == "脈絡待仲裁"
    assert set(body["card"]["fields"]) == {"earliest_seen", "original_source", "account_count", "timing_chart", "archive_links", "domain_note", "sample_excerpt"}


@pytest.mark.asyncio
async def test_lookup_unfetchable(client):
    r = await client.post("/v1/lookup", json={"url": "https://www.threads.com/@ghost/post/NOPE"})
    assert r.status_code == 202
    r = await client.post("/v1/lookup", json={"url": "https://www.threads.com/@ghost/post/NOPE"})
    assert r.status_code == 422 and r.json()["status"] == "unfetchable"


@pytest.mark.asyncio
async def test_invalid_url_error_format(client):
    r = await client.post("/v1/lookup", json={"url": "ftp://bad"})
    assert r.status_code == 400
    assert set(r.json()["error"]) >= {"code", "message_zh", "message_en"}


@pytest.mark.asyncio
async def test_vote_idempotent_and_eligibility(client, db):
    seed_mock_post(URL, "alice", "x", None)
    await client.post("/v1/lookup", json={"url": URL})
    card = await _seed_cluster_with_card(db, URL)
    token = await _device(client)
    h = {"Authorization": f"Bearer {token}"}

    r = await client.post(f"/v1/cards/{card.id}/votes", json={"helpful": True}, headers=h)
    assert r.status_code == 200 and r.json() == {"accepted": True, "counted": False}
    r = await client.post(f"/v1/cards/{card.id}/votes", json={"helpful": False}, headers=h)
    assert r.status_code == 200
    votes = (await db.scalars(select(Vote))).all()
    assert len(votes) == 1 and votes[0].helpful is False and votes[0].weight == 0.0

    c = await db.scalar(select(Contributor))
    c.lookup_count = 99
    c.created_at = datetime.now(UTC) - timedelta(days=3)
    await db.commit()
    r = await client.post(f"/v1/cards/{card.id}/votes", json={"helpful": True}, headers=h)
    assert r.json()["counted"] is True
    await db.refresh(card)
    assert card.vote_count == 1

    r = await client.post(f"/v1/cards/{card.id}/votes", json={"helpful": True})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_queue_excludes_voted_and_orders_by_fewest_votes(client, db):
    urls = [f"https://www.threads.com/@u{i}/post/P{i}" for i in range(3)]
    cards = []
    for u in urls:
        seed_mock_post(u, "u", "x", None)
        await client.post("/v1/lookup", json={"url": u})
        cards.append(await _seed_cluster_with_card(db, u))
    cards[0].vote_count = 5
    cards[1].vote_count = 1
    await db.commit()
    token = await _device(client)
    h = {"Authorization": f"Bearer {token}"}
    await client.post(f"/v1/cards/{cards[2].id}/votes", json={"helpful": True}, headers=h)
    r = await client.get("/v1/queue?limit=5", headers=h)
    ids = [c["card_id"] for c in r.json()["cards"]]
    assert ids == [str(cards[1].id), str(cards[0].id)]
    assert r.json()["strategy"] == "phase_a_fewest_votes"
    assert (await client.get("/v1/queue")).status_code == 401


@pytest.mark.asyncio
async def test_hidden_card_is_silent(client, db):
    seed_mock_post(URL, "alice", "x", None)
    await client.post("/v1/lookup", json={"url": URL})
    card = await _seed_cluster_with_card(db, URL)
    card.state = CardState.not_displayed
    await db.commit()
    assert (await client.get(f"/v1/cards/{card.id}")).status_code == 404
    r = await client.post("/v1/lookup", json={"url": URL})
    assert r.status_code == 202


@pytest.mark.asyncio
async def test_flags_require_named_and_audit_has_no_identity(client, db):
    seed_mock_post(URL, "alice", "x", None)
    await client.post("/v1/lookup", json={"url": URL})
    card = await _seed_cluster_with_card(db, URL)
    token = await _device(client)
    h = {"Authorization": f"Bearer {token}"}
    r = await client.post(f"/v1/clusters/{card.cluster_id}/flags", json={"kind": "not_in_cluster"}, headers=h)
    assert r.status_code == 403
    c = await db.scalar(select(Contributor))
    c.named_profile = "螢火測試員"
    await db.commit()
    r = await client.post(f"/v1/clusters/{card.cluster_id}/flags", json={"kind": "not_in_cluster", "note": "不同主題"}, headers=h)
    assert r.status_code == 201
    log = (await client.get("/v1/open/audit-log")).json()["items"]
    flagged = [x for x in log if x["event"] == "flagged"]
    assert flagged and "contributor_id" not in (flagged[0]["payload"] or {})


@pytest.mark.asyncio
async def test_rate_limit_429(client, monkeypatch):
    from firefly import config as cfgmod

    cfg = cfgmod.get_config()
    monkeypatch.setattr(cfg.ratelimit, "anonymous_per_hour", 2)
    for _ in range(2):
        assert (await client.post("/v1/devices", json={})).status_code == 201
    r = await client.post("/v1/devices", json={})
    assert r.status_code == 429 and "Retry-After" in r.headers and r.json()["error"]["code"] == "rate_limited"


@pytest.mark.asyncio
async def test_unknown_card_404(client):
    assert (await client.get(f"/v1/cards/{uuid.uuid4()}")).status_code == 404

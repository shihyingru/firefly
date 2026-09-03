"""Threads Bot(文件 7.2)測試 / tests: webhook verify + signature, mention handling, reply budget, posting log."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from firefly.bots import threads as tb
from firefly.models import AuditLog
from firefly.pipeline.adapters import seed_mock_post
from firefly.pipeline.threads_client import FakeThreadsAPI, ThreadsMedia

APP_SECRET = "app-secret"
VERIFY = "verify-me"
URL = "https://www.threads.com/@alice/post/AAA111"


@pytest.fixture(autouse=True)
def threads_env(monkeypatch):
    from firefly.config import get_config, get_settings

    monkeypatch.setattr(get_settings(), "threads_app_secret", APP_SECRET)
    monkeypatch.setattr(get_settings(), "threads_webhook_verify_token", VERIFY)
    monkeypatch.setattr(get_config().threads, "enabled", True)
    fake = FakeThreadsAPI()
    monkeypatch.setattr(tb, "_api_override", fake)
    return fake


def _mention(mid, text, replied_to=None):
    return ThreadsMedia(mid, text, "someone", datetime(2026, 9, 2, tzinfo=timezone.utc), f"https://www.threads.com/@someone/post/{mid}", None, replied_to, None)


async def _seed_card(client, db):
    from tests.test_api_core import _seed_cluster_with_card

    seed_mock_post(URL, "alice", "測試貼文 內容", datetime(2026, 9, 1, tzinfo=timezone.utc))
    await client.post("/v1/lookup", json={"url": URL})
    return await _seed_cluster_with_card(db, URL)


@pytest.mark.asyncio
async def test_webhook_verification(client):
    r = await client.get("/v1/threads/webhook", params={"hub.mode": "subscribe", "hub.verify_token": VERIFY, "hub.challenge": "12345"})
    assert r.status_code == 200 and r.text == "12345"
    r = await client.get("/v1/threads/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "1"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_webhook_signature_and_mention_dispatch(client, db, threads_env):
    card = await _seed_card(client, db)
    body = json.dumps({"entry": [{"changes": [{"field": "mentions", "value": {"id": "m1", "text": f"@firefly_tw {URL}", "username": "someone"}}]}]}).encode()
    r = await client.post("/v1/threads/webhook", content=body, headers={"content-type": "application/json", "X-Hub-Signature-256": "sha256=bad"})
    assert r.status_code == 400
    sig = "sha256=" + hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    r = await client.post("/v1/threads/webhook", content=body, headers={"content-type": "application/json", "X-Hub-Signature-256": sig})
    assert r.status_code == 200 and r.json()["handled"] == 1
    assert len(threads_env.replies) == 1
    to, text = threads_env.replies[0]
    assert to == "m1" and "3 個帳號" in text and f"/cards/{card.id}" in text and len(text) < 500
    logs = (await db.scalars(select(AuditLog).where(AuditLog.event == "threads_reply"))).all()
    assert len(logs) == 1 and logs[0].payload["rule"] == "threads_reply_v1" and logs[0].payload["published"] is True
    assert "someone" not in json.dumps(logs[0].payload)  # 發文 log 不記提及者 / posting log carries no mentioner identity


@pytest.mark.asyncio
async def test_pending_then_reply_and_dedup(db, threads_env):
    seed_mock_post(URL, "alice", "x", None)
    m = _mention("m2", f"看看 {URL}")
    assert await tb.handle_mention(db, threads_env, m) == "pending"  # 第一次:快照排程中 / first: snapshot scheduled
    assert threads_env.replies == []
    assert await tb.handle_mention(db, threads_env, m) == "no_signal"
    assert threads_env.replies[-1][1].startswith("目前查無協同訊號")
    assert await tb.handle_mention(db, threads_env, m) == "duplicate"
    assert len(threads_env.replies) == 1


@pytest.mark.asyncio
async def test_target_from_replied_to_and_no_target(db, threads_env):
    threads_env.permalinks["parent1"] = "https://www.threads.com/@ghost/post/NOPE"
    assert await tb.handle_mention(db, threads_env, _mention("m3", "@firefly_tw 幫我看", replied_to="parent1")) == "pending"
    assert await tb.handle_mention(db, threads_env, _mention("m3", "@firefly_tw 幫我看", replied_to="parent1")) == "unfetchable"
    assert await tb.handle_mention(db, threads_env, _mention("m4", "@firefly_tw")) == "no_target"
    assert "附上一則公開貼文的連結" in threads_env.replies[-1][1]


@pytest.mark.asyncio
async def test_reply_budget_cap(db, threads_env, monkeypatch):
    from firefly.config import get_config

    monkeypatch.setattr(get_config().threads, "daily_reply_cap", 2)
    monkeypatch.setattr(get_config().threads, "quota_margin", 0.0)
    for i in range(2):
        await tb.handle_mention(db, threads_env, _mention(f"b{i}", "@firefly_tw"))
    assert len(threads_env.replies) == 2
    seed_mock_post(URL, "alice", "x", None)
    # 超量:未知貼文不觸發新快照/新卡 / over cap: unknown post triggers nothing
    assert await tb.handle_mention(db, threads_env, _mention("b9", URL)) == "over_cap_silent"
    assert len(threads_env.replies) == 2


@pytest.mark.asyncio
async def test_poll_route_and_disabled_flag(db, threads_env, monkeypatch):
    threads_env.mentions_results = [_mention("p1", "@firefly_tw")]
    assert await tb.poll_mentions(threads_env) == {"no_target": 1}
    from firefly.config import get_config

    monkeypatch.setattr(get_config().threads, "enabled", False)
    assert await tb.poll_mentions(threads_env) == {"disabled": True}
    assert await tb.handle_mention(db, threads_env, _mention("p2", URL)) == "disabled"


@pytest.mark.asyncio
async def test_card_page_renders(client, db):
    card = await _seed_card(client, db)
    r = await client.get(f"/cards/{card.id}")
    assert r.status_code == 200 and "脈絡卡" in r.text and "測試貼文" in r.text and f"/v1/cards/{card.id}/votes" in r.text
    from firefly.models import CardState

    card.state = CardState.not_displayed
    await db.commit()
    assert (await client.get(f"/cards/{card.id}")).status_code == 404

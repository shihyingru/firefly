"""D-014 選項 D / option D: day-0 reply, consent enrol (encrypted, Redis-only, TTL), daily push, final message, blocked drop, cap, self-serve."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select, text

from firefly.bots import line_client
from firefly.bots import line_onboarding as ob
from firefly.bots.line_client import FakeLineClient
from firefly.models import Contributor
from firefly.pipeline.adapters import seed_mock_post
from firefly.services.hashing import line_user_hash

SECRET = "test-line-secret"
USER = "Uonboard0123456789abcdef0123456789"
URLS = [f"https://www.threads.com/@a{i}/post/Q{i}" for i in range(3)]


def _sign(body: bytes) -> str:
    return base64.b64encode(hmac.new(SECRET.encode(), body, hashlib.sha256).digest()).decode()


@pytest.fixture(autouse=True)
def env(monkeypatch):
    from firefly.config import get_config, get_settings

    monkeypatch.setattr(get_settings(), "line_channel_secret", SECRET)
    monkeypatch.setattr(get_settings(), "line_push_enc_key", Fernet.generate_key().decode())
    monkeypatch.setattr(get_config().line, "onboarding_push_enabled", True)
    monkeypatch.setattr(get_config().line, "onboarding_push_days", 3)
    fake = FakeLineClient()
    from firefly.bots import line as line_mod

    monkeypatch.setattr(line_mod, "get_line_client", lambda: fake)
    monkeypatch.setattr(line_client, "get_line_client", lambda: fake)
    return fake


async def _post(client, events):
    body = json.dumps({"events": events}).encode()
    return await client.post("/v1/line/webhook", content=body, headers={"content-type": "application/json", "X-Line-Signature": _sign(body)})


def _ev(t, **kw):
    return {"type": t, "replyToken": "rt", "source": {"type": "user", "userId": USER}, **kw}


async def _seed_cards(client, db, n=3):
    from tests.test_api_core import _seed_cluster_with_card

    cards = []
    for u in URLS[:n]:
        seed_mock_post(u, "x", "y", datetime(2026, 9, 1, tzinfo=timezone.utc))
        await client.post("/v1/lookup", json={"url": u})
        cards.append(await _seed_cluster_with_card(db, u))
    return cards


@pytest.mark.asyncio
async def test_day0_reply_with_queue_and_offer_then_enrol_encrypted(client, db, env):
    await _seed_cards(client, db)
    await _post(client, [_ev("follow")])
    msgs = env.sent[-1][1]
    assert msgs[0]["type"] == "text" and msgs[1]["type"] == "flex" and msgs[1]["contents"]["type"] == "carousel"
    assert len(msgs[1]["contents"]["contents"]) == 3 and msgs[-1]["template"]["type"] == "confirm"
    assert env.pushed == []  # 第 0 天零 push / no push on day 0

    await _post(client, [_ev("postback", postback={"data": "onboard:yes"})])
    from firefly.services.redis_client import get_redis

    r = get_redis()
    key = ob.KEY_PREFIX + line_user_hash(USER)
    data = await r.hgetall(key)
    assert data["sent"] == "0" and USER not in data["tok"] and 0 < await r.ttl(key) <= 3 * 86400 + 3600
    # PostgreSQL 任何表都沒有 userId / no table holds the raw userId
    for table in ("contributor", "audit_log", "vote"):
        rows = (await db.execute(text(f"SELECT to_jsonb(t)::text FROM {table} t"))).scalars().all()
        assert not any(USER in x for x in rows)


@pytest.mark.asyncio
async def test_daily_push_three_days_then_delete(client, db, env):
    await _seed_cards(client, db)
    await _post(client, [_ev("follow"), _ev("postback", postback={"data": "onboard:yes"})])
    from firefly.services.redis_client import get_redis

    r = get_redis()
    key = ob.KEY_PREFIX + line_user_hash(USER)
    s1 = await ob.run_daily_push(db, env, force=True)
    assert s1["pushed"] == 1 and await r.hget(key, "sent") == "1" and env.pushed[-1][0] == USER
    s2 = await ob.run_daily_push(db, env, force=True)
    assert s2["pushed"] == 1
    s3 = await ob.run_daily_push(db, env, force=True)
    assert s3["pushed"] == 1 and s3["finished"] == 1 and await r.exists(key) == 0
    assert any("引導期結束" in m.get("text", "") for m in env.pushed[-1][1])
    # 沒有名單 → 不推播;去重旗標 / nothing enrolled → no push; day flag dedups
    assert (await ob.run_daily_push(db, env, force=True))["pushed"] == 0
    assert (await ob.run_daily_push(db, env))["skipped"] is True
    logs = (await db.scalars(select(__import__("firefly.models", fromlist=["AuditLog"]).AuditLog))).all()
    assert all(USER not in json.dumps(a.payload or {}) for a in logs)


@pytest.mark.asyncio
async def test_blocked_user_dropped_and_no_new_cards_skips(client, db, env):
    await _post(client, [_ev("follow"), _ev("postback", postback={"data": "onboard:yes"})])
    from firefly.services.redis_client import get_redis

    key = ob.KEY_PREFIX + line_user_hash(USER)
    # 沒有卡 → 不消耗推播,名單保留 / no cards → no push, stays enrolled
    assert (await ob.run_daily_push(db, env, force=True))["empty"] == 1 and await get_redis().exists(key) == 1
    await _seed_cards(client, db)
    env.blocked.add(USER)
    s = await ob.run_daily_push(db, env, force=True)
    assert s["dropped"] == 1 and await get_redis().exists(key) == 0


@pytest.mark.asyncio
async def test_unfollow_unenrols_and_self_serve_queue(client, db, env):
    await _seed_cards(client, db)
    await _post(client, [_ev("follow"), _ev("postback", postback={"data": "onboard:yes"}), _ev("unfollow")])
    from firefly.services.redis_client import get_redis

    assert await get_redis().exists(ob.KEY_PREFIX + line_user_hash(USER)) == 0
    await _post(client, [_ev("postback", postback={"data": "queue:today"})])
    assert env.sent[-1][1][0]["type"] == "flex"
    c = await db.scalar(select(Contributor))
    assert c.origin_key_hash == line_user_hash(USER)


@pytest.mark.asyncio
async def test_flag_off_means_no_offer_no_enrol_no_push(client, db, env, monkeypatch):
    from firefly.config import get_config

    monkeypatch.setattr(get_config().line, "onboarding_push_enabled", False)
    await _seed_cards(client, db)
    await _post(client, [_ev("follow")])
    assert all(m.get("template", {}).get("type") != "confirm" for m in env.sent[-1][1])
    await _post(client, [_ev("postback", postback={"data": "onboard:yes"})])
    assert "無法開啟" in env.sent[-1][1][0]["text"]
    assert (await ob.run_daily_push(db, env, force=True)) == {"disabled": True}


@pytest.mark.asyncio
async def test_daily_cap(client, db, env, monkeypatch):
    from firefly.config import get_config

    monkeypatch.setattr(get_config().line, "onboarding_push_daily_cap", 1)
    await _seed_cards(client, db)
    for uid in ("Ucap1" + "0" * 28, "Ucap2" + "0" * 28):
        ev = [{"type": "follow", "replyToken": "rt", "source": {"type": "user", "userId": uid}}, {"type": "postback", "replyToken": "rt", "source": {"type": "user", "userId": uid}, "postback": {"data": "onboard:yes"}}]
        await _post(client, ev)
    s = await ob.run_daily_push(db, env, force=True)
    assert s["pushed"] == 1 and s["capped"] == 1

"""LINE Bot(文件 7.1)測試 / tests: signature, lookup reply, postback vote (HMAC handle), 202 flow."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import select, text

from firefly.bots import line_client
from firefly.bots.line_client import FakeLineClient
from firefly.models import Contributor, Vote
from firefly.pipeline.adapters import seed_mock_post
from firefly.services.hashing import line_user_hash

SECRET = "test-line-secret"
USER = "Uabcdef0123456789abcdef0123456789"
URL = "https://www.threads.com/@alice/post/AAA111"


def _sign(body: bytes) -> str:
    return base64.b64encode(hmac.new(SECRET.encode(), body, hashlib.sha256).digest()).decode()


@pytest.fixture(autouse=True)
def line_env(monkeypatch):
    from firefly.config import get_settings

    monkeypatch.setattr(get_settings(), "line_channel_secret", SECRET)
    fake = FakeLineClient()
    monkeypatch.setattr(line_client, "get_line_client", lambda: fake)
    from firefly.bots import line as line_mod

    monkeypatch.setattr(line_mod, "get_line_client", lambda: fake)
    return fake


async def _post(client, events, sign=True):
    body = json.dumps({"destination": "x", "events": events}).encode()
    headers = {"content-type": "application/json"}
    if sign:
        headers["X-Line-Signature"] = _sign(body)
    return await client.post("/v1/line/webhook", content=body, headers=headers)


def _msg(text_, token="rt1"):
    return {"type": "message", "replyToken": token, "source": {"type": "user", "userId": USER}, "message": {"type": "text", "id": "1", "text": text_}}


def _postback(data, token="rt2"):
    return {"type": "postback", "replyToken": token, "source": {"type": "user", "userId": USER}, "postback": {"data": data}}


async def _seed_card(client, db):
    from tests.test_api_core import _seed_cluster_with_card

    seed_mock_post(URL, "alice", "測試貼文 內容", datetime(2026, 9, 1, tzinfo=timezone.utc))
    await client.post("/v1/lookup", json={"url": URL})
    return await _seed_cluster_with_card(db, URL)


@pytest.mark.asyncio
async def test_bad_signature_rejected(client):
    r = await _post(client, [_msg("hi")], sign=False)
    assert r.status_code == 400 and r.json()["error"]["code"] == "bad_signature"


@pytest.mark.asyncio
async def test_follow_and_no_url(client, line_env):
    await _post(client, [{"type": "follow", "replyToken": "rt0", "source": {"type": "user", "userId": USER}}, _msg("你好")])
    assert [m[0]["type"] for _, m in line_env.sent] == ["text", "text"]
    assert "螢火" in line_env.sent[0][1][0]["text"]


@pytest.mark.asyncio
async def test_lookup_processing_then_card_then_vote(client, db, line_env):
    seed_mock_post(URL, "alice", "測試貼文 內容", datetime(2026, 9, 1, tzinfo=timezone.utc))
    await _post(client, [_msg(f"看這個 {URL}?utm_source=line")])
    first = line_env.sent[-1][1][0]
    assert first["type"] == "template" and first["template"]["actions"][0]["data"] == f"relookup:{URL}"

    await _post(client, [_postback(f"relookup:{URL}")])
    assert line_env.sent[-1][1][0]["text"].startswith("目前查無協同訊號")

    from tests.test_api_core import _seed_cluster_with_card

    card = await _seed_cluster_with_card(db, URL)
    await _post(client, [_msg(URL)])
    fm = line_env.sent[-1][1][0]
    assert fm["type"] == "flex" and "3 個帳號" in fm["altText"]
    footer = fm["contents"]["footer"]["contents"]
    assert footer[0]["action"]["data"] == f"vote:{card.id}:1" and footer[2]["action"]["uri"].endswith(f"/cards/{card.id}")

    await _post(client, [_postback(f"vote:{card.id}:0")])
    assert line_env.sent[-1][1][0]["text"].startswith("謝謝你的仲裁")
    votes = (await db.scalars(select(Vote))).all()
    assert len(votes) == 1 and votes[0].helpful is False
    c = await db.scalar(select(Contributor))
    assert c.origin.value == "line_hash" and c.origin_key_hash == line_user_hash(USER) and c.lookup_count == 3

    # 冪等覆寫 / idempotent overwrite
    await _post(client, [_postback(f"vote:{card.id}:1")])
    db.expire_all()
    votes = (await db.scalars(select(Vote))).all()
    assert len(votes) == 1 and votes[0].helpful is True


@pytest.mark.asyncio
async def test_raw_line_user_id_never_stored(client, db, line_env):
    await _seed_card(client, db)
    await _post(client, [_msg(URL)])
    for table in ("contributor", "vote", "audit_log", "post_snapshot", "context_card", "cluster"):
        rows = (await db.execute(text(f"SELECT to_jsonb(t)::text FROM {table} t"))).scalars().all()
        assert not any(USER in r for r in rows), f"raw LINE userId found in {table}"


@pytest.mark.asyncio
async def test_disabled_flag_short_circuits(client, monkeypatch, line_env):
    from firefly.config import get_config

    monkeypatch.setattr(get_config().line, "enabled", False)
    r = await _post(client, [_msg("x")], sign=False)
    assert r.status_code == 200 and r.json()["disabled"] is True and line_env.sent == []

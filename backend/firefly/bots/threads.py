"""
Threads 回覆機器人(文件 7.2)/ Threads reply bot.

觸發 / Triggers:
- webhook:GET 驗證(hub.challenge)、POST 事件(X-Hub-Signature-256 以 app secret 驗證)→ 交給 handle_mention
- 輪詢備援:poll_mentions() 每 N 分鐘呼叫 /me/mentions(2026-09-03 實測可用)

規則 / Rules:
- 目標貼文:提及文字中的 URL → replied_to / root_post 的 permalink → 皆無則回覆使用說明
- 回覆組裝:摘要文字(< reply_max_chars)+ 卡片頁連結;同叢集重複觸發回既有連結
- 額度:每日回覆上限計數器(Redis);超量時只回既有連結,不觸發新卡起草
- 起草中(202):暫存待重試,下次輪詢再試;超過重試上限即放棄(沉默)
- 發文 log:每則回覆寫入 audit_log(event=threads_reply,附生成規則與時間)— 文件 12/15
- 風險開關:threads.enabled=false 時 POST 事件與輪詢皆不動作
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.errors import ApiError
from ..config import get_config, get_settings
from ..db import get_db, get_sessionmaker
from ..pipeline.threads_client import HttpThreadsAPI, ThreadsAPI, ThreadsMedia
from ..services.audit import audit
from ..services.lookup import lookup as do_lookup
from ..services.redis_client import get_redis
from ..services.urlnorm import InvalidURL, extract_urls, normalize_url

router = APIRouter(prefix="/v1/threads")
RULE_ID = "threads_reply_v1"


# ---------- webhook ----------
def verify_meta_signature(body: bytes, header: str | None, app_secret: str | None = None) -> bool:
    secret = app_secret if app_secret is not None else get_settings().threads_app_secret
    if not secret or not header or not header.startswith("sha256="):
        return False
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, header[len("sha256="):])


@router.get("/webhook")
async def webhook_verify(hub_mode: str = Query(default="", alias="hub.mode"), hub_verify_token: str = Query(default="", alias="hub.verify_token"), hub_challenge: str = Query(default="", alias="hub.challenge")):
    expected = get_settings().threads_webhook_verify_token
    if hub_mode == "subscribe" and expected and hmac.compare_digest(hub_verify_token, expected):
        return PlainTextResponse(hub_challenge)
    raise ApiError(403, "webhook_verify_failed", "驗證失敗", "Verification failed")


@router.post("/webhook")
async def webhook_receive(request: Request, session: AsyncSession = Depends(get_db), x_hub_signature_256: str | None = Header(default=None)):
    body = await request.body()
    if not verify_meta_signature(body, x_hub_signature_256):
        raise ApiError(400, "bad_signature", "簽章驗證失敗", "Signature verification failed")
    if not get_config().threads.enabled:
        return {"ok": True, "disabled": True}
    payload = json.loads(body or b"{}")
    api = get_threads_api()
    handled = 0
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "mentions":
                continue
            v = change.get("value") or {}
            media = ThreadsMedia(str(v.get("id") or v.get("media_id") or ""), v.get("text") or "", v.get("username"), None, v.get("permalink"), None, (v.get("replied_to") or {}).get("id") if isinstance(v.get("replied_to"), dict) else None, (v.get("root_post") or {}).get("id") if isinstance(v.get("root_post"), dict) else None)
            if media.id:
                await handle_mention(session, api, media)
                handled += 1
    await session.commit()
    return {"ok": True, "handled": handled}


# ---------- core ----------
_api_override: ThreadsAPI | None = None


def get_threads_api() -> ThreadsAPI:
    return _api_override or HttpThreadsAPI()


class ReplyBudget:
    KEY = "threads:reply_budget:{day}"

    def _key(self) -> str:
        return self.KEY.format(day=datetime.now(timezone.utc).strftime("%Y%m%d"))

    async def try_consume(self) -> bool:
        cfg = get_config().threads
        cap = int(cfg.daily_reply_cap * (1 - cfg.quota_margin))
        r = get_redis()
        k = self._key()
        v = await r.incr(k)
        if v == 1:
            await r.expire(k, 86400 + 3600)
        if v > cap:
            await r.decr(k)
            return False
        return True


async def resolve_target_url(api: ThreadsAPI, m: ThreadsMedia) -> str | None:
    for u in extract_urls(m.text):
        try:
            return normalize_url(u)
        except InvalidURL:
            continue
    for mid in (m.replied_to_id, m.root_post_id):
        if mid:
            link = api.media_permalink(mid)
            if link:
                try:
                    return normalize_url(link)
                except InvalidURL:
                    pass
    return None


def compose_reply(status: str, card: dict | None, card_url: str | None) -> str:
    cfg = get_config().threads
    if status in ("candidate", "displayed") and card:
        f = card["fields"]
        es = f["earliest_seen"]
        earliest = es["at"][:16].replace("T", " ") if es.get("at") else "未能確認"
        label = card["arbitration"]["label"]["zh"]
        text = f"脈絡卡|{f['account_count']} 個帳號發布了相同或近似的內容。最早出現:{earliest}。{label}。\n完整卡片與投票:{card_url}"
    elif status == "no_signal":
        text = "目前查無協同訊號。分享前,可以先找找原始出處。"
    elif status == "unfetchable":
        text = "無法取得這則貼文的內容(非公開或已刪除)。"
    else:
        text = "請在提及時附上一則公開貼文的連結,我會回覆它的脈絡卡。"
    return text[: cfg.reply_max_chars]


async def handle_mention(session: AsyncSession, api: ThreadsAPI, m: ThreadsMedia) -> str:
    """回傳結果代碼 / returns an outcome code (for tests and the posting log)."""
    if not get_config().threads.enabled:
        return "disabled"
    r = get_redis()
    if await r.sismember("threads:handled", m.id):
        return "duplicate"
    target = await resolve_target_url(api, m)
    budget_ok = await ReplyBudget().try_consume()  # 每則回覆皆計入日上限 / every reply counts toward the daily cap
    if target is None:
        if not budget_ok:
            return "over_cap_silent"
        await _publish(session, api, m, compose_reply("no_target", None, None), "no_target")
        return "no_target"
    if not budget_ok:
        # 超量:只回既有卡片連結,不觸發新卡 / over cap: existing card link only, never a new draft
        res = await do_lookup(session, target) if await _known(session, target) else None
        if res and res.status in ("candidate", "displayed"):
            await _publish(session, api, m, compose_reply(res.status, res.card, _card_url(res.card)), "over_cap_existing")
            return "over_cap_existing"
        return "over_cap_silent"
    res = await do_lookup(session, target)
    if res.status == "processing":
        n = await r.hincrby("threads:pending", m.id, 1)
        if n > get_config().threads.pending_retry_limit:
            await r.hdel("threads:pending", m.id)
            await r.sadd("threads:handled", m.id)
            return "gave_up"
        await r.decr(ReplyBudget()._key())  # 未回覆,退回額度 / not replied, refund
        return "pending"
    await _publish(session, api, m, compose_reply(res.status, res.card, _card_url(res.card) if res.card else None), res.status)
    return res.status


async def _known(session: AsyncSession, url: str) -> bool:
    from sqlalchemy import select

    from ..models import PostSnapshot

    return (await session.scalar(select(PostSnapshot.id).where(PostSnapshot.source_url == url))) is not None


def _card_url(card: dict | None) -> str | None:
    return f"{get_settings().public_base_url.rstrip('/')}/cards/{card['card_id']}" if card else None


async def _publish(session: AsyncSession, api: ThreadsAPI, m: ThreadsMedia, text: str, reason: str) -> None:
    posted_id = api.reply(m.id, text)
    r = get_redis()
    await r.sadd("threads:handled", m.id)
    await r.hdel("threads:pending", m.id)
    # 發文 log 全公開:由系統於 T 時依規則 R 生成(文件 12、15)。不記提及者身分。
    await audit(session, "threads_post", posted_id, "threads_reply", {"rule": RULE_ID, "reason": reason, "text": text, "generated_at": datetime.now(timezone.utc).isoformat(), "published": posted_id is not None})


async def poll_mentions(api: ThreadsAPI | None = None) -> dict:
    """輪詢路線 / polling route(cron 或 worker 每 mention_poll_interval_seconds 呼叫一次)。"""
    if not get_config().threads.enabled:
        return {"disabled": True}
    api = api or get_threads_api()
    outcomes: dict[str, int] = {}
    async with get_sessionmaker()() as session:
        for m in api.mentions():
            code = await handle_mention(session, api, m)
            outcomes[code] = outcomes.get(code, 0) + 1
        await session.commit()
    return outcomes

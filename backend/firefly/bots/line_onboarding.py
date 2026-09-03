"""
D-014 選項 D:引導期推播 + 之後自取 / onboarding push, then self-serve.

- 第 0 天:follow 事件以 reply 回今天的佇列 + 「接下來 N 天每天傳給我」按鈕(零儲存)。
- 使用者按下按鈕(明確同意)→ 加密 userId 存 Redis,TTL = N 天 + 1 小時。**不進 PostgreSQL。**
- 每日任務:對名單內每人 push 佇列;第 N 次附自取說明並刪除;push 失敗(封鎖)即刪除;每日人數上限。
- 之後:富選單 postback `queue:today` 以 reply 回佇列(選項 B,零儲存)。
- 審計只記人次總數,不記個人。/ audit records aggregate counts only.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_config, get_settings
from ..models import Contributor
from ..services.audit import audit
from ..services.cards import card_public_view, phase_a_queue
from ..services.redis_client import get_redis
from . import line_flex as flex
from .line_client import LineClient, PushFailed

KEY_PREFIX = "line:onboard:"
TAIPEI = timezone(timedelta(hours=8))


def _fernet() -> Fernet | None:
    k = get_settings().line_push_enc_key
    return Fernet(k.encode()) if k else None


def enabled() -> bool:
    return get_config().line.onboarding_push_enabled and _fernet() is not None


async def queue_messages(session: AsyncSession, contributor: Contributor, final: bool = False) -> list[dict]:
    """今日佇列訊息(carousel);沒有卡時回說明。/ today's queue as a carousel; explains when empty."""
    cfg = get_config().line
    cards = await phase_a_queue(session, contributor, cfg.queue_size)
    msgs: list[dict] = []
    if cards:
        msgs.append({"type": "flex", "altText": f"今日仲裁佇列:{len(cards)} 張卡", "contents": {"type": "carousel", "contents": [flex.card_bubble(card_public_view(c)) for c in cards]}})
    else:
        msgs.append({"type": "text", "text": "今天沒有新的待仲裁卡片。謝謝你。"})
    if final:
        msgs.append({"type": "text", "text": "引導期結束。之後請按選單的「今日佇列」自取每日 5 張卡。你的推播資料已刪除。"})
    return msgs


def onboarding_offer_message() -> dict:
    n = get_config().line.onboarding_push_days
    return {
        "type": "template",
        "altText": "要每天收到仲裁佇列嗎?",
        "template": {
            "type": "confirm",
            "text": f"接下來 {n} 天,每天傳 5 張卡給你?之後改由選單自取。同意後系統會加密保存你的推播代號 {n} 天,到期自動刪除。",
            "actions": [
                {"type": "postback", "label": "好", "data": "onboard:yes", "displayText": "好"},
                {"type": "postback", "label": "不用", "data": "onboard:no", "displayText": "不用"},
            ],
        },
    }


async def enroll(session: AsyncSession, contributor: Contributor, line_user_id: str) -> bool:
    """明確同意後登錄;回傳是否成功。/ enrol after explicit consent."""
    f = _fernet()
    if not enabled() or f is None:
        return False
    cfg = get_config().line
    r = get_redis()
    key = KEY_PREFIX + contributor.origin_key_hash
    await r.hset(key, mapping={"tok": f.encrypt(line_user_id.encode()).decode(), "sent": 0, "enrolled": datetime.now(timezone.utc).isoformat()})
    await r.expire(key, cfg.onboarding_push_days * 86400 + 3600)
    await audit(session, "line", None, "onboarding_enrolled", {"days": cfg.onboarding_push_days})
    return True


async def unenroll(contributor_hash: str) -> None:
    await get_redis().delete(KEY_PREFIX + contributor_hash)


async def run_daily_push(session: AsyncSession, client: LineClient, force: bool = False) -> dict:
    """每日一次(排程器每 5 分鐘呼叫,依本地時刻與 Redis 旗標去重)。/ once per day; scheduler calls it every 5 min."""
    cfg = get_config().line
    if not enabled():
        return {"disabled": True}
    r = get_redis()
    now_local = datetime.now(TAIPEI)
    day_flag = f"line:onboard:done:{now_local:%Y%m%d}"
    if not force and (now_local.hour != cfg.onboarding_push_hour_local or await r.exists(day_flag)):
        return {"skipped": True}
    f = _fernet()
    stats = {"pushed": 0, "finished": 0, "dropped": 0, "capped": 0, "empty": 0}
    from sqlalchemy import select

    async for key in r.scan_iter(KEY_PREFIX + "*", count=200):
        if key.startswith("line:onboard:done:"):
            continue
        if stats["pushed"] >= cfg.onboarding_push_daily_cap:
            stats["capped"] += 1
            continue
        data = await r.hgetall(key)
        try:
            user_id = f.decrypt(data["tok"].encode()).decode()
        except (InvalidToken, KeyError):
            await r.delete(key)
            stats["dropped"] += 1
            continue
        contributor = await session.scalar(select(Contributor).where(Contributor.origin_key_hash == key[len(KEY_PREFIX):]))
        if contributor is None:
            await r.delete(key)
            stats["dropped"] += 1
            continue
        sent = int(data.get("sent", 0)) + 1
        final = sent >= cfg.onboarding_push_days
        msgs = await queue_messages(session, contributor, final=final)
        if len(msgs) == 1 and msgs[0]["type"] == "text" and not final:
            stats["empty"] += 1  # 沒有新卡就不推播,不消耗則數 / no new cards → no push
            continue
        try:
            await client.push(user_id, msgs)
        except PushFailed:
            await r.delete(key)
            stats["dropped"] += 1
            continue
        finally:
            del user_id
        stats["pushed"] += 1
        if final:
            await r.delete(key)
            stats["finished"] += 1
        else:
            await r.hset(key, "sent", sent)
    await r.set(day_flag, "1", ex=86400)
    await audit(session, "line", None, "onboarding_push_run", stats)
    return stats

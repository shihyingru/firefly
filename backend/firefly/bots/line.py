"""
LINE Bot(文件 7.1)/ LINE bot webhook.

- 訊息含 URL → 正規化 → lookup → Flex 卡片(或處理中/查無/無法取得)
- postback vote:<card_id>:<1|0> → 以 LINE userId 的 HMAC 代號投票(D-011);原始 userId 不落地
- postback relookup:<url> → 再查一次(D-008)
- 只用 reply token;不 push
- 「明日佇列」push 需要保存可推播的識別碼,與文件 08 衝突,待決議(見文件 17 D-014 提案)
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_config
from ..db import get_db
from ..services import contributors as contrib_svc
from ..services import ratelimit
from ..services.cards import cast_vote, get_visible_card
from ..services.lookup import lookup as do_lookup
from ..services.urlnorm import InvalidURL, extract_urls, normalize_url
from . import line_flex as flex
from .line_client import get_line_client, verify_signature

router = APIRouter(prefix="/v1/line")


@router.post("/webhook")
async def webhook(request: Request, session: AsyncSession = Depends(get_db), x_line_signature: str | None = Header(default=None)):
    body = await request.body()
    if not get_config().line.enabled:
        return {"ok": True, "disabled": True}
    if not verify_signature(body, x_line_signature):
        from ..api.errors import ApiError

        raise ApiError(400, "bad_signature", "簽章驗證失敗", "Signature verification failed")
    payload = await request.json()
    client = get_line_client()
    for ev in payload.get("events", []):
        messages = await handle_event(session, ev)
        token = ev.get("replyToken")
        if messages and token:
            await client.reply(token, messages)
    return {"ok": True}


async def handle_event(session: AsyncSession, ev: dict) -> list[dict]:
    etype = ev.get("type")
    user_id = (ev.get("source") or {}).get("userId")
    if etype == "follow":
        return [flex.welcome_message()]
    if not user_id:
        return []
    contributor = await contrib_svc.get_or_create_line_contributor(session, user_id)
    del user_id  # 原始 userId 到此為止 / raw userId goes no further
    rate = await ratelimit.check_contributor(str(contributor.id))
    if not rate.allowed:
        return [{"type": "text", "text": "請稍後再試。"}]

    if etype == "message" and (ev.get("message") or {}).get("type") == "text":
        urls = extract_urls(ev["message"].get("text", ""))
        if not urls:
            return [flex.no_url_message()]
        return await _lookup_reply(session, contributor, urls[0])

    if etype == "postback":
        data = (ev.get("postback") or {}).get("data", "")
        if data.startswith("vote:"):
            _, card_id, val = data.split(":", 2)
            try:
                card = await get_visible_card(session, uuid.UUID(card_id))
            except ValueError:
                card = None
            if card is None:
                return [{"type": "text", "text": "這張卡片目前無法投票。"}]
            v = await cast_vote(session, contributor, card, val == "1")
            await session.commit()
            return [flex.thanks_message(v.weight > 0)]
        if data.startswith("relookup:"):
            return await _lookup_reply(session, contributor, data[len("relookup:"):])
    return []


async def _lookup_reply(session: AsyncSession, contributor, raw_url: str) -> list[dict]:
    try:
        url = normalize_url(raw_url)
    except InvalidURL:
        return [flex.no_url_message()]
    await contrib_svc.record_lookup(session, contributor)
    await session.commit()
    res = await do_lookup(session, url)
    if res.status == "processing":
        return [flex.processing_message(url)]
    if res.status == "unfetchable":
        return [flex.unfetchable_message()]
    if res.status == "no_signal":
        return [flex.no_signal_message(contributor.lookup_count)]
    return [flex.card_message(res.card)]

"""LINE Messaging API 客戶端 / client. 只用 reply(免費);不主動 push(文件 7.1)。/ reply only; no proactive push."""
from __future__ import annotations

import base64
import hashlib
import hmac
from functools import lru_cache
from typing import Protocol

import httpx

from ..config import get_settings

REPLY_URL = "https://api.line.me/v2/bot/message/reply"
PUSH_URL = "https://api.line.me/v2/bot/message/push"


class PushFailed(Exception):
    """push 失敗(含被封鎖)/ push failed (incl. blocked)."""


def verify_signature(body: bytes, signature: str | None, channel_secret: str | None = None) -> bool:
    secret = channel_secret if channel_secret is not None else get_settings().line_channel_secret
    if not secret or not signature:
        return False
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(digest).decode(), signature)


class LineClient(Protocol):
    async def reply(self, reply_token: str, messages: list[dict]) -> None: ...
    async def push(self, user_id: str, messages: list[dict]) -> None: ...


class HttpLineClient:
    async def reply(self, reply_token: str, messages: list[dict]) -> None:
        token = get_settings().line_channel_access_token
        async with httpx.AsyncClient(timeout=10) as c:
            await c.post(REPLY_URL, json={"replyToken": reply_token, "messages": messages[:5]}, headers={"Authorization": f"Bearer {token}"})

    async def push(self, user_id: str, messages: list[dict]) -> None:
        """唯一的 push 場景:D-014 引導期。/ the only push scenario: D-014 onboarding."""
        token = get_settings().line_channel_access_token
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(PUSH_URL, json={"to": user_id, "messages": messages[:5]}, headers={"Authorization": f"Bearer {token}"})
        if r.status_code != 200:
            raise PushFailed(str(r.status_code))


class FakeLineClient:
    """測試用:記錄送出的訊息 / tests: records outgoing messages."""

    def __init__(self):
        self.sent: list[tuple[str, list[dict]]] = []
        self.pushed: list[tuple[str, list[dict]]] = []
        self.blocked: set[str] = set()

    async def reply(self, reply_token: str, messages: list[dict]) -> None:
        self.sent.append((reply_token, messages))

    async def push(self, user_id: str, messages: list[dict]) -> None:
        if user_id in self.blocked:
            raise PushFailed("403")
        self.pushed.append((user_id, messages))


@lru_cache
def get_line_client() -> LineClient:
    return HttpLineClient()

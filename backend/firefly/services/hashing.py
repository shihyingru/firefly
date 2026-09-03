"""單向雜湊 / One-way hashes. 原值(裝置 token、LINE userId)永不落地 / raw values never stored."""
from __future__ import annotations

import hashlib
import hmac
import secrets

from ..config import get_settings


def new_device_token() -> str:
    return secrets.token_urlsafe(32)


def device_token_hash(token: str) -> str:
    """裝置 token → 儲存用雜湊(pepper 防表查)/ device token → stored hash (peppered)."""
    s = get_settings()
    return hmac.new(s.device_token_pepper.encode(), token.encode(), hashlib.sha256).hexdigest()


def line_user_hash(line_user_id: str) -> str:
    """LINE userId → HMAC-SHA256 代號(D-011)。同一 userId 恆得同一代號;無密鑰者無法反查。"""
    s = get_settings()
    return hmac.new(s.line_id_hmac_key.encode(), line_user_id.encode(), hashlib.sha256).hexdigest()


def ip_bucket_key(ip: str) -> str:
    """IP → 防濫用暫存鍵(僅 Redis,TTL ≤ 24h;文件 08)。/ IP → abuse-control key (Redis only, TTL ≤ 24h)."""
    s = get_settings()
    return hmac.new(s.device_token_pepper.encode(), ("ip:" + ip).encode(), hashlib.sha256).hexdigest()[:32]


def url_key(normalized_url: str) -> str:
    return hashlib.sha256(normalized_url.encode()).hexdigest()[:32]


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode()).hexdigest()

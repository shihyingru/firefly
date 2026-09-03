"""
速率限制 / Rate limiting(文件 06:匿名 60/hr、貢獻者 300/hr;429 附 Retry-After)。

固定視窗計數存 Redis。IP 只用於未帶 token 的請求,鍵為 HMAC 桶,TTL 不超過 24h(文件 08)。
Fixed-window counters in Redis. IP is used only for token-less requests, as an HMAC bucket with TTL ≤ 24h (doc 08).
"""
from __future__ import annotations

from dataclasses import dataclass

from ..config import get_config
from .hashing import ip_bucket_key
from .redis_client import get_redis


@dataclass
class RateResult:
    allowed: bool
    remaining: int
    retry_after: int


async def check_rate(scope: str, identity: str, limit: int) -> RateResult:
    cfg = get_config().ratelimit
    r = get_redis()
    key = f"rl:{scope}:{identity}"
    window = cfg.window_seconds
    n = await r.incr(key)
    if n == 1:
        await r.expire(key, min(window, cfg.ip_retention_seconds))
    ttl = await r.ttl(key)
    if n > limit:
        return RateResult(False, 0, max(ttl, 1))
    return RateResult(True, limit - n, 0)


async def check_anonymous(ip: str) -> RateResult:
    return await check_rate("anon", ip_bucket_key(ip), get_config().ratelimit.anonymous_per_hour)


async def check_contributor(contributor_id: str) -> RateResult:
    return await check_rate("contrib", contributor_id, get_config().ratelimit.contributor_per_hour)

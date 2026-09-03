"""FastAPI 依賴 / dependencies: DB、貢獻者解析、速率限制。"""
from __future__ import annotations

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_db
from ..models import Contributor
from ..services import ratelimit
from ..services.contributors import resolve_device_token
from .errors import forbidden, too_many, unauthorized


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


async def optional_contributor(
    session: AsyncSession = Depends(get_db), authorization: str | None = Header(default=None)
) -> Contributor | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    return await resolve_device_token(session, token)


async def require_contributor(c: Contributor | None = Depends(optional_contributor)) -> Contributor:
    if c is None:
        raise unauthorized()
    return c


async def require_named(c: Contributor = Depends(require_contributor)) -> Contributor:
    if not c.named_profile:
        raise forbidden("此操作需要具名貢獻者", "Named contributor required")
    return c


async def rate_limited(request: Request, c: Contributor | None = Depends(optional_contributor)) -> None:
    """匿名以 IP 桶計數(僅 Redis、24h 內過期),貢獻者以代號計數。/ anon by IP bucket (Redis only), contributors by id."""
    res = await (ratelimit.check_contributor(str(c.id)) if c else ratelimit.check_anonymous(client_ip(request)))
    if not res.allowed:
        raise too_many(res.retry_after)


def require_service_token(x_service_token: str | None = Header(default=None)) -> None:
    if x_service_token != get_settings().service_token:
        raise unauthorized()

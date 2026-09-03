"""貢獻者服務 / Contributor service: 核發裝置代號、解析 token、資格門檻(D-009)。"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_config
from ..models import Contributor, ContributorOrigin
from .hashing import device_token_hash, line_user_hash, new_device_token


async def issue_device(session: AsyncSession) -> tuple[Contributor, str]:
    """POST /devices(D-007):回傳 (contributor, 原始 token)。原始 token 只回給客戶端一次。"""
    token = new_device_token()
    c = Contributor(origin=ContributorOrigin.device, origin_key_hash=device_token_hash(token))
    session.add(c)
    await session.flush()
    return c, token


async def resolve_device_token(session: AsyncSession, token: str) -> Contributor | None:
    return await session.scalar(select(Contributor).where(Contributor.origin_key_hash == device_token_hash(token)))


async def get_or_create_line_contributor(session: AsyncSession, line_user_id: str) -> Contributor:
    """LINE 使用者 → 貢獻者(HMAC 代號,D-011)。原始 userId 不落地。"""
    h = line_user_hash(line_user_id)
    c = await session.scalar(select(Contributor).where(Contributor.origin_key_hash == h))
    if c is None:
        c = Contributor(origin=ContributorOrigin.line_hash, origin_key_hash=h)
        session.add(c)
        await session.flush()
    return c


async def record_lookup(session: AsyncSession, c: Contributor) -> None:
    """只加計數,不記 URL(D-009)/ count only, never the URL."""
    now = datetime.now(UTC)
    c.lookup_count += 1
    if c.first_lookup_at is None:
        c.first_lookup_at = now
    c.last_active_at = now


def is_eligible(c: Contributor, now: datetime | None = None) -> bool:
    """投票計入權重的資格(文件 05/14 T1):累積查詢 + 帳齡。/ Vote-weight eligibility."""
    cfg = get_config().eligibility
    now = now or datetime.now(UTC)
    if c.lookup_count < cfg.min_lookups:
        return False
    created = c.created_at or now
    return (now - created).total_seconds() >= cfg.min_account_age_hours * 3600

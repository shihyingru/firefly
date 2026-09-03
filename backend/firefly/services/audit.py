"""審計 log / Audit log writer. 全表公開:payload 不得含個人層級資料。/ Public table: no individual-level data."""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditLog

PRIVATE_KEYS = {"contributor_id", "device_token", "ip", "line_user_id", "token"}


async def audit(session: AsyncSession, entity_type: str, entity_id: str | None, event: str, payload: dict[str, Any] | None = None) -> AuditLog:
    if payload:
        leaked = PRIVATE_KEYS & set(payload)
        if leaked:
            raise ValueError(f"audit payload must not contain private keys: {sorted(leaked)}")
    row = AuditLog(entity_type=entity_type, entity_id=entity_id, event=event, payload=payload)
    session.add(row)
    await session.flush()
    return row

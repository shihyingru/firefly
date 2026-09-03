"""開放資料端點 / Open-data endpoints(文件 06、12)。Wave 1 先提供 audit-log 與已顯示卡片。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import AuditLog, CardState, ContextCard
from ..services.cards import card_public_view

router = APIRouter(prefix="/v1/open")


@router.get("/audit-log")
async def audit_log(since_id: int = Query(default=0, ge=0), limit: int = Query(default=200, ge=1, le=1000), session: AsyncSession = Depends(get_db)):
    rows = (await session.scalars(select(AuditLog).where(AuditLog.id > since_id).order_by(AuditLog.id).limit(limit))).all()
    return {"items": [{"id": r.id, "entity_type": r.entity_type, "entity_id": r.entity_id, "event": r.event, "payload": r.payload, "created_at": r.created_at.isoformat()} for r in rows]}


@router.get("/cards.jsonl")
async def cards_jsonl(session: AsyncSession = Depends(get_db)):
    """全量已顯示卡片(Phase A 期間亦含 candidate,以 state 區分)。/ all displayed cards (and candidates, by state)."""
    import json

    from fastapi.responses import PlainTextResponse

    rows = (await session.scalars(select(ContextCard).where(ContextCard.state.in_((CardState.displayed, CardState.candidate))))).all()
    return PlainTextResponse("\n".join(json.dumps(card_public_view(r), ensure_ascii=False) for r in rows), media_type="application/x-ndjson")

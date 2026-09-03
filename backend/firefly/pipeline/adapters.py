"""
Stage 0 來源 adapter / Source adapters for Stage 0.

規則 / Rules:
- 只走官方 API,只取公開貼文(文件 09、13;D-005)。/ Official APIs only, public posts only.
- 每個 adapter 回傳 FetchedPost 或 None(unfetchable)。/ Each adapter returns FetchedPost or None.
- MockAdapter 供測試與單機示範:貼文由 Redis `mock:post:<url>` 提供。/ MockAdapter for tests and demos.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from ..services.redis_client import get_sync_redis
from ..services.urlnorm import extract_urls


@dataclass
class FetchedPost:
    source_url: str
    author_handle: str | None
    content_text: str
    posted_at: datetime | None  # D-004: 可能為空 / may be None
    external_links: list[str] = field(default_factory=list)
    raw_ref: str | None = None  # 供審計:來源方法 / for audit: which method produced it


class SourceAdapter(Protocol):
    name: str

    def fetch(self, normalized_url: str) -> FetchedPost | None: ...


class MockAdapter:
    name = "mock"

    def fetch(self, normalized_url: str) -> FetchedPost | None:
        raw = get_sync_redis().get(f"mock:post:{normalized_url}")
        if not raw:
            return None
        d = json.loads(raw)
        posted = d.get("posted_at")
        return FetchedPost(
            source_url=normalized_url,
            author_handle=d.get("author_handle"),
            content_text=d.get("content_text", ""),
            posted_at=datetime.fromisoformat(posted) if posted else None,
            external_links=extract_urls(d.get("content_text", "")),
            raw_ref="mock",
        )


def seed_mock_post(normalized_url: str, author_handle: str, content_text: str, posted_at: datetime | None) -> None:
    get_sync_redis().set(
        f"mock:post:{normalized_url}",
        json.dumps({"author_handle": author_handle, "content_text": content_text, "posted_at": posted_at.isoformat() if posted_at else None}),
    )


def get_adapter(platform: str) -> SourceAdapter:
    """依平台與設定選 adapter。Threads 真實 adapter 於 Wave 1.2 加入(oEmbed,需 App Review)。"""
    import os

    if os.environ.get("FIREFLY_SOURCE_ADAPTER", "mock") == "mock":
        return MockAdapter()
    from .threads_adapter import ThreadsOEmbedAdapter  # noqa: WPS433 (lazy, optional)

    return ThreadsOEmbedAdapter()

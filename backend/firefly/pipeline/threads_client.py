"""
Threads 官方 API 客戶端 / Threads official API client(文件 09、13:只走 API、只取公開貼文)。

- oEmbed(單一 URL,需 App Review「Threads oEmbed Read」)
- keyword_search / TAG search(需 threads_keyword_search 審核)
- /me/mentions 輪詢(已於 2026-09-03 實測可用)
- 額度計數:Redis 日計數器,留 20% 餘裕(文件 7.2、14 T4)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

import httpx

from ..config import get_config, get_settings
from ..services.redis_client import get_sync_redis

GRAPH = "https://graph.threads.net/v1.0"
MEDIA_FIELDS = "id,text,username,timestamp,permalink,shortcode,topic_tag,link_attachment_url,media_type"
MENTION_FIELDS = MEDIA_FIELDS + ",replied_to,root_post"


@dataclass
class ThreadsMedia:
    id: str
    text: str
    username: str | None
    timestamp: datetime | None
    permalink: str | None
    link_attachment_url: str | None = None
    replied_to_id: str | None = None
    root_post_id: str | None = None


class ThreadsAPI(Protocol):
    def oembed(self, url: str) -> dict | None: ...
    def keyword_search(self, q: str, mode: str | None = None, limit: int = 25) -> list[ThreadsMedia]: ...
    def mentions(self, limit: int = 25) -> list[ThreadsMedia]: ...
    def media_permalink(self, media_id: str) -> str | None: ...
    def reply(self, reply_to_id: str, text: str) -> str | None: ...


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00").replace("+0000", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _media(d: dict) -> ThreadsMedia:
    rt, rp = d.get("replied_to") or {}, d.get("root_post") or {}
    return ThreadsMedia(
        str(d.get("id")), d.get("text") or "", d.get("username"), _parse_ts(d.get("timestamp")), d.get("permalink"),
        d.get("link_attachment_url"), rt.get("id") if isinstance(rt, dict) else None, rp.get("id") if isinstance(rp, dict) else None,
    )


class SearchBudget:
    """關鍵字搜尋日額度(Redis)/ daily keyword-search budget."""

    KEY = "threads:search_budget:{day}"

    def _key(self) -> str:
        return self.KEY.format(day=datetime.now(timezone.utc).strftime("%Y%m%d"))

    def try_consume(self, n: int = 1) -> bool:
        r = get_sync_redis()
        k = self._key()
        v = r.incrby(k, n)
        if v == n:
            r.expire(k, 86400 + 3600)
        if v > get_config().ingestion.keyword_search_daily_budget:
            r.decrby(k, n)
            return False
        return True

    def used_today(self) -> int:
        return int(get_sync_redis().get(self._key()) or 0)


class HttpThreadsAPI:
    def __init__(self, user_token: str | None = None, app_token: str | None = None):
        s = get_settings()
        self.user_token = user_token or s.threads_user_token
        self.app_token = app_token or (f"TH|{s.threads_app_id}|{s.threads_app_secret}" if s.threads_app_id and s.threads_app_secret else None)
        self.http = httpx.Client(timeout=20)
        self.budget = SearchBudget()

    def oembed(self, url: str) -> dict | None:
        if not self.app_token:
            return None
        r = self.http.get(f"{GRAPH}/oembed", params={"url": url, "access_token": self.app_token})
        return r.json() if r.status_code == 200 else None

    def keyword_search(self, q: str, mode: str | None = None, limit: int = 25) -> list[ThreadsMedia]:
        if not self.user_token or not self.budget.try_consume():
            return []
        params = {"q": q, "search_type": "RECENT", "fields": MEDIA_FIELDS, "limit": limit, "access_token": self.user_token}
        if mode:
            params["search_mode"] = mode
        r = self.http.get(f"{GRAPH}/keyword_search", params=params)
        if r.status_code != 200:
            return []
        return [_media(d) for d in r.json().get("data", [])]

    def mentions(self, limit: int = 25) -> list[ThreadsMedia]:
        if not self.user_token:
            return []
        r = self.http.get(f"{GRAPH}/me/mentions", params={"fields": MENTION_FIELDS, "limit": limit, "access_token": self.user_token})
        if r.status_code != 200:
            return []
        return [_media(d) for d in r.json().get("data", [])]

    def media_permalink(self, media_id: str) -> str | None:
        """母貼文 permalink。非本人貼文可能無權限(2026-09-03 實測)→ None。/ may be forbidden for others' posts → None."""
        if not self.user_token:
            return None
        r = self.http.get(f"{GRAPH}/{media_id}", params={"fields": "id,permalink", "access_token": self.user_token})
        return r.json().get("permalink") if r.status_code == 200 else None

    def reply(self, reply_to_id: str, text: str) -> str | None:
        """兩步發布:建立容器(reply_to_id)→ publish。回傳新貼文 id。/ two-step publish; returns the new media id."""
        if not self.user_token:
            return None
        r = self.http.post(f"{GRAPH}/me/threads", params={"media_type": "TEXT", "text": text, "reply_to_id": reply_to_id, "access_token": self.user_token})
        if r.status_code != 200 or "id" not in r.json():
            return None
        r2 = self.http.post(f"{GRAPH}/me/threads_publish", params={"creation_id": r.json()["id"], "access_token": self.user_token})
        return str(r2.json().get("id")) if r2.status_code == 200 else None


class FakeThreadsAPI:
    """測試用 / for tests: canned results."""

    def __init__(self, search_results: dict[str, list[ThreadsMedia]] | None = None, oembed_results: dict[str, dict] | None = None, mentions_results: list[ThreadsMedia] | None = None):
        self.search_results = search_results or {}
        self.oembed_results = oembed_results or {}
        self.mentions_results = mentions_results or []
        self.permalinks: dict[str, str] = {}
        self.replies: list[tuple[str, str]] = []
        self.calls: list[tuple] = []

    def oembed(self, url: str) -> dict | None:
        self.calls.append(("oembed", url))
        return self.oembed_results.get(url)

    def keyword_search(self, q: str, mode: str | None = None, limit: int = 25) -> list[ThreadsMedia]:
        self.calls.append(("search", q, mode))
        return self.search_results.get(q, [])

    def mentions(self, limit: int = 25) -> list[ThreadsMedia]:
        self.calls.append(("mentions",))
        return self.mentions_results

    def media_permalink(self, media_id: str) -> str | None:
        self.calls.append(("permalink", media_id))
        return self.permalinks.get(media_id)

    def reply(self, reply_to_id: str, text: str) -> str | None:
        self.calls.append(("reply", reply_to_id, text))
        self.replies.append((reply_to_id, text))
        return f"r{len(self.replies)}"


_TAG_RE = re.compile(r"<[^>]+>")


def oembed_text(html: str) -> str:
    """從 oEmbed html 取純文字 / plain text from oEmbed html."""
    text = _TAG_RE.sub(" ", html or "")
    return re.sub(r"\s+", " ", text).strip()

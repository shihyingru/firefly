"""Stage 0 Threads adapter:oEmbed(官方 API)。無時間戳 → posted_at=None(D-004)。/ oEmbed-only; posted_at is None."""
from __future__ import annotations

from ..services.urlnorm import extract_urls, threads_post_parts
from .adapters import FetchedPost
from .threads_client import HttpThreadsAPI, ThreadsAPI, oembed_text


class ThreadsOEmbedAdapter:
    name = "threads-oembed"

    def __init__(self, api: ThreadsAPI | None = None):
        self.api = api or HttpThreadsAPI()

    def fetch(self, normalized_url: str) -> FetchedPost | None:
        parts = threads_post_parts(normalized_url)
        if parts is None:
            return None
        data = self.api.oembed(normalized_url)
        if not data:
            return None
        text = oembed_text(data.get("html", ""))
        return FetchedPost(
            source_url=normalized_url,
            author_handle=data.get("author_name") or parts[0],
            content_text=text,
            posted_at=None,
            external_links=extract_urls(text),
            raw_ref="threads-oembed",
        )

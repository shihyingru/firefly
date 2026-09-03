"""URL 正規化 / URL normalization: strip tracking params, canonical host, detect platform."""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ..models import Platform

TRACKING_PARAMS = {"fbclid", "igshid", "igsh", "gclid", "ref", "ref_src", "xmt", "hl", "_rdr", "mibextid"}
TRACKING_PREFIXES = ("utm_",)
THREADS_HOSTS = {"threads.net", "www.threads.net", "threads.com", "www.threads.com"}
FACEBOOK_HOSTS = {"facebook.com", "www.facebook.com", "m.facebook.com", "fb.com"}
URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


class InvalidURL(ValueError):
    pass


def extract_urls(text: str) -> list[str]:
    """從文字抽出所有 URL / all URLs in a text."""
    return [m.group(0).rstrip(".,);]") for m in URL_RE.finditer(text or "")]


def normalize_url(raw: str) -> str:
    """正規化:https、小寫主機、去追蹤參數、去 fragment、Threads 主機統一為 www.threads.com。
    Normalize: https, lowercase host, drop tracking params and fragment, canonical Threads host."""
    raw = (raw or "").strip()
    if not raw:
        raise InvalidURL("empty")
    if "://" not in raw:
        raw = "https://" + raw
    parts = urlsplit(raw)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise InvalidURL("unsupported scheme or missing host")
    host = parts.hostname.lower() if parts.hostname else ""
    if host in THREADS_HOSTS:
        host = "www.threads.com"
    path = re.sub(r"/{2,}", "/", parts.path) or "/"
    if len(path) > 1:
        path = path.rstrip("/")
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=False)
        if k.lower() not in TRACKING_PARAMS and not k.lower().startswith(TRACKING_PREFIXES)
    ]
    query.sort()
    return urlunsplit(("https", host, path, urlencode(query), ""))


def detect_platform(normalized_url: str) -> Platform:
    host = urlsplit(normalized_url).hostname or ""
    if host in THREADS_HOSTS:
        return Platform.threads
    if host in FACEBOOK_HOSTS:
        return Platform.facebook
    return Platform.other


def threads_post_parts(normalized_url: str) -> tuple[str, str] | None:
    """回傳 (handle, shortcode) / returns (handle, shortcode) for a Threads post URL."""
    m = re.match(r"^/@([^/]+)/post/([A-Za-z0-9_-]+)$", urlsplit(normalized_url).path)
    return (m.group(1), m.group(2)) if m else None

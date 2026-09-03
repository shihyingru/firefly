"""Wayback 存證 / Wayback Machine archiving(Stage 0)。盡力而為,失敗回 None,永不拋例外。/ best-effort, never raises."""
from __future__ import annotations

import httpx

from ..config import get_config, get_settings

SPN = "https://web.archive.org/save/"


def archive_url(url: str) -> str | None:
    cfg = get_config().stage0
    if not cfg.archive_enabled:
        return None
    s = get_settings()
    headers = {"User-Agent": "firefly-archiver/0.1 (+https://github.com/shihyingru/firefly)", "Accept": "application/json"}
    if s.wayback_access_key and s.wayback_secret_key:
        headers["Authorization"] = f"LOW {s.wayback_access_key}:{s.wayback_secret_key}"
    try:
        with httpx.Client(timeout=cfg.archive_timeout_seconds, follow_redirects=True) as c:
            if "Authorization" in headers:
                r = c.post(SPN, data={"url": url}, headers=headers)
                if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json"):
                    job = r.json().get("job_id")
                    if job:
                        return f"https://web.archive.org/web/2/{url}"  # 最新快照指標 / latest-snapshot pointer
            r = c.get(SPN + url, headers=headers)
            loc = r.headers.get("content-location") or r.headers.get("location")
            if loc and "/web/" in loc:
                return "https://web.archive.org" + loc if loc.startswith("/") else loc
            if r.status_code == 200:
                return f"https://web.archive.org/web/2/{url}"
    except Exception:  # noqa: BLE001
        return None
    return None

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from firefly.models import DomainSignal, PostSnapshot
from firefly.pipeline.ingest import (
    domain_lookback,
    extract_keywords,
    sibling_search,
    tag_patrol,
    upsert_media,
)
from firefly.pipeline.threads_client import FakeThreadsAPI, SearchBudget, ThreadsMedia

T0 = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def _m(i, text="這款產品真的太神了 #好物"):
    return ThreadsMedia(id=str(i), text=text, username=f"s{i}", timestamp=T0, permalink=f"https://www.threads.com/@s{i}/post/S{i}")


def test_extract_keywords_prefers_hashtags_then_cjk_runs():
    assert extract_keywords("這款產品真的太神了!快去看 https://x.y/z #好物 #推薦")[:2] == ["好物", "推薦"]
    assert set(extract_keywords("This product is amazing amazing product")) == {"amazing", "product"}
    assert extract_keywords("") == []


@pytest.mark.asyncio
async def test_sibling_search_creates_snapshots_with_timestamps(db):
    api = FakeThreadsAPI(search_results={"好物": [_m(1), _m(2)]})
    snap = PostSnapshot(source_url="https://www.threads.com/@a/post/A", platform="threads", content_text="太神了 #好物", fetch_status="ok")
    db.add(snap)
    await db.flush()
    found = await sibling_search(db, api, snap)
    assert [s.author_handle for s in found] == ["s1", "s2"] and all(s.posted_at == T0 for s in found)
    assert api.calls == [("search", "好物", None)]
    # 冪等 / idempotent
    assert (await upsert_media(db, _m(1))).id == found[0].id


@pytest.mark.asyncio
async def test_tag_patrol_and_domain_lookback(db, monkeypatch):
    from firefly.config import get_config

    monkeypatch.setattr(get_config().ingestion, "tags", ["新聞"])
    db.add(DomainSignal(domain="farm.example", source_list="DTL", list_version="1"))
    await db.flush()
    api = FakeThreadsAPI(search_results={"新聞": [_m(3)], "farm.example": [_m(4, "看 https://farm.example/p")]})
    assert len(await tag_patrol(db, api)) == 1 and ("search", "新聞", "TAG") in api.calls
    found = await domain_lookback(db, api)
    assert len(found) == 1 and found[0].external_links == ["https://farm.example/p"]
    assert len((await db.scalars(select(PostSnapshot))).all()) == 2


def test_search_budget(monkeypatch):
    from firefly.config import get_config

    monkeypatch.setattr(get_config().ingestion, "keyword_search_daily_budget", 2)
    b = SearchBudget()
    assert b.try_consume() and b.try_consume() and not b.try_consume() and b.used_today() == 2

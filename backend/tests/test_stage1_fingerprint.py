from datetime import datetime, timedelta, timezone

import pytest

from firefly.models import DomainSignal, PostSnapshot
from firefly.pipeline.stage1_fingerprint import domain_signals, formatting_signals, timing_signals


def _p(handle, at, text="x"):
    return PostSnapshot(author_handle=handle, posted_at=at, content_text=text)


def test_formatting_rule_hits_and_misses():
    farm = "今天天氣真好 ☀️\n大家快去看\n真的太神了\n超推薦\n#好物 #推薦"
    assert [h["rule_id"] for h in formatting_signals(farm)] == ["short_lines_emoji_hashtag_tail"]
    assert formatting_signals("這是一段很長很長的正常敘述文字,沒有特別排版,也沒有標籤或表情符號,只是單純的一段話而已。") == []
    assert [h["rule_id"] for h in formatting_signals("看 https://ex.org/p")] == ["repeated_link_only"]


def test_timing_sync_ignores_missing_timestamps():
    t0 = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    posts = [_p("a", t0), _p("b", t0 + timedelta(minutes=5)), _p("c", t0 + timedelta(minutes=50)), _p("d", t0 + timedelta(hours=5)), _p("e", None)]
    s = timing_signals(posts)
    assert s["max_accounts_in_window"] == 3 and s["n_timed"] == 4 and s["n_untimed"] == 1
    assert [c["n"] for c in s["chart"]] == [2, 1, 1]
    assert timing_signals([_p("a", None)])["chart"] == []


@pytest.mark.asyncio
async def test_domain_signals_match_active_only(db):
    db.add(DomainSignal(domain="farm.example", source_list="DTL report", list_version="2026-01", evidence_url="https://dtl.example/r"))
    db.add(DomainSignal(domain="removed.example", source_list="DTL report", list_version="2026-01", removed_at=datetime.now(timezone.utc)))
    await db.commit()
    d = await domain_signals(db, ["https://www.farm.example/a?b=1", "https://removed.example/x", "https://clean.example/"])
    assert [m["domain"] for m in d["matches"]] == ["farm.example"] and d["list_version"] == "2026-01"
    assert d["checked_domains"] == ["clean.example", "farm.example", "removed.example"]

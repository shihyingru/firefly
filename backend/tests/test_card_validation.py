"""文件 04 後驗證 / doc-04 post-validation unit tests."""
import copy

from firefly.pipeline.card_schema import (
    UNTRACED_ZH,
    ValidationContext,
    strip_to_whitelist,
    validate_card_fields,
)

URL_A = "https://www.threads.com/@a/post/A"
URL_B = "https://www.threads.com/@b/post/B"
CHART = [{"t": "2026-09-01T12:00:00+00:00", "n": 2}]
GOOD = {
    "earliest_seen": {"at": "2026-09-01T12:00:00+00:00", "url": URL_A},
    "original_source": {"url": URL_A, "traced": True, "method": "earliest_post"},
    "account_count": 2,
    "timing_chart": CHART,
    "archive_links": [{"url": URL_A, "archive_url": "https://web.archive.org/web/2/x"}],
    "domain_note": {"matches": [], "list_version": None},
    "sample_excerpt": "這款產品真的太神了",
}


def ctx():
    return ValidationContext(post_urls={URL_A, URL_B}, archive_urls={"https://web.archive.org/web/2/x"}, candidate_urls={URL_A, URL_B}, signal_account_count=2, signal_chart=CHART, post_texts=["這款產品真的太神了 👉 x", "另一則"])


def test_good_card_passes():
    assert validate_card_fields(GOOD, ctx()) == []


def test_extra_field_rejected_and_stripped():
    bad = {**GOOD, "verdict": "假訊息"}
    assert any("schema" in e for e in validate_card_fields(bad, ctx()))
    assert set(strip_to_whitelist(bad)) == set(GOOD)


def test_url_outside_candidate_set_rejected():
    bad = copy.deepcopy(GOOD)
    bad["original_source"]["url"] = "https://evil.example/x"
    assert any("candidate set" in e for e in validate_card_fields(bad, ctx()))


def test_numbers_must_match_signalset():
    bad = copy.deepcopy(GOOD)
    bad["account_count"] = 32
    assert any("account_count" in e for e in validate_card_fields(bad, ctx()))
    bad = copy.deepcopy(GOOD)
    bad["timing_chart"] = []
    assert any("timing_chart" in e for e in validate_card_fields(bad, ctx()))


def test_excerpt_must_be_verbatim():
    bad = copy.deepcopy(GOOD)
    bad["sample_excerpt"] = "這款產品可疑"
    assert any("verbatim" in e for e in validate_card_fields(bad, ctx()))


def test_forbidden_terms_rejected_outside_excerpt():
    bad = copy.deepcopy(GOOD)
    bad["domain_note"]["matches"] = [{"domain": "x.example", "source_list": "這些是側翼網軍", "list_version": "1"}]
    errs = validate_card_fields(bad, ctx())
    assert any("forbidden term" in e for e in errs)
    # 逐字節錄含敏感詞是資料,不是裁決 / a verbatim excerpt containing such a word is data, not a verdict
    ok = copy.deepcopy(GOOD)
    ok["sample_excerpt"] = "另一則"
    assert validate_card_fields(ok, ValidationContext(**{**ctx().__dict__, "post_texts": ["另一則 假訊息"]})) == []


def test_untraced_shape():
    u = copy.deepcopy(GOOD)
    u["original_source"] = {"url": None, "traced": False, "note": UNTRACED_ZH}
    assert validate_card_fields(u, ctx()) == []
    u["original_source"] = {"url": None, "traced": False}
    assert validate_card_fields(u, ctx())

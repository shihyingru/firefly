"""卡片欄位白名單守衛(文件 04,D-002)。Wave 1.2 加入完整 JSON schema 與後驗證;此處先鎖定欄位集合。
Card whitelist guard (doc 04, D-002). Wave 1.2 adds the full JSON schema + post-validation; this pins the field set."""
import uuid

from firefly.models import CardState, ContextCard
from firefly.services.cards import card_public_view

WHITELIST = {"earliest_seen", "original_source", "account_count", "timing_chart", "archive_links", "domain_note", "sample_excerpt"}


def test_public_view_never_exposes_individual_votes():
    card = ContextCard(id=uuid.uuid4(), cluster_id=uuid.uuid4(), version=1, state=CardState.candidate, fields={k: None for k in WHITELIST}, vote_count=0)
    view = card_public_view(card)
    assert set(view["fields"]) == WHITELIST
    assert set(view["arbitration"]) == {"i_c", "vote_count", "spectrum_coverage", "label"}

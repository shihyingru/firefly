"""
脈絡卡欄位白名單 JSON schema 與程式後驗證 / Card whitelist JSON schema + programmatic post-validation(文件 04、14 T5)。

驗證任一項失敗 → 整卡退回。/ Any failure rejects the whole card.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from jsonschema import Draft202012Validator

from ..config import get_config

WHITELIST = ("earliest_seen", "original_source", "account_count", "timing_chart", "archive_links", "domain_note", "sample_excerpt")

UNTRACED_ZH = "未能追溯"
UNCONFIRMED_ZH = "未能確認"

CARD_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": list(WHITELIST),
    "properties": {
        "earliest_seen": {
            "type": "object",
            "additionalProperties": False,
            "required": ["at", "url"],
            "properties": {"at": {"type": ["string", "null"]}, "url": {"type": ["string", "null"]}, "note": {"type": "string", "enum": [UNCONFIRMED_ZH]}},
        },
        "original_source": {
            "type": "object",
            "additionalProperties": False,
            "required": ["url", "traced"],
            "properties": {"url": {"type": ["string", "null"]}, "traced": {"type": "boolean"}, "note": {"type": "string", "enum": [UNTRACED_ZH]}, "method": {"type": "string", "enum": ["earliest_post", "shared_link", "llm_choice"]}},
        },
        "account_count": {"type": "integer", "minimum": 0},
        "timing_chart": {
            "type": "array",
            "items": {"type": "object", "additionalProperties": False, "required": ["t", "n"], "properties": {"t": {"type": "string"}, "n": {"type": "integer", "minimum": 0}}},
        },
        "archive_links": {
            "type": "array",
            "items": {"type": "object", "additionalProperties": False, "required": ["url", "archive_url"], "properties": {"url": {"type": "string"}, "archive_url": {"type": "string"}}},
        },
        "domain_note": {
            "type": "object",
            "additionalProperties": False,
            "required": ["matches", "list_version"],
            "properties": {
                "matches": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["domain", "source_list", "list_version"], "properties": {"domain": {"type": "string"}, "source_list": {"type": "string"}, "list_version": {"type": "string"}, "evidence_url": {"type": ["string", "null"]}}}},
                "list_version": {"type": ["string", "null"]},
            },
        },
        "sample_excerpt": {"type": "string"},
    },
}
_validator = Draft202012Validator(CARD_SCHEMA)

# 禁止事項:形容詞裁決、意圖推測、立場描述(中/英/日)。命中即退回。/ forbidden verdict/intent/stance terms (zh/en/ja)
FORBIDDEN_TERMS = [
    # zh
    "可疑", "操弄", "操縱", "假帳號", "假訊息", "假新聞", "造假", "側翼", "境外", "認知作戰", "帶風向", "網軍", "洗腦", "抹黑", "惡意", "陰謀", "煽動", "詐騙", "立場", "親中", "反中", "綠", "藍", "白", "統派", "獨派", "闢謠",
    # en
    "suspicious", "manipulat", "fake", "bot", "troll", "propaganda", "disinformation", "misinformation", "malicious", "coordinated inauthentic", "astroturf", "shill", "partisan", "left-wing", "right-wing", "pro-", "anti-", "conspiracy", "debunk",
    # ja
    "疑わしい", "操作", "偽", "工作員", "プロパガンダ", "陰謀", "デマ", "悪意",
]
_FORBIDDEN_RE = re.compile("|".join(re.escape(t) for t in FORBIDDEN_TERMS), re.IGNORECASE)


@dataclass
class ValidationContext:
    post_urls: set[str]
    archive_urls: set[str]
    candidate_urls: set[str]
    signal_account_count: int
    signal_chart: list[dict]
    post_texts: list[str]
    errors: list[str] = field(default_factory=list)


def _walk_strings(obj, path="$"):
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_strings(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_strings(v, f"{path}[{i}]")


def validate_card_fields(fields: dict, ctx: ValidationContext) -> list[str]:
    """回傳錯誤清單;空清單 = 通過。/ returns error list; empty = pass."""
    errors: list[str] = []
    for e in _validator.iter_errors(fields):
        errors.append(f"schema: {e.json_path}: {e.message}")
    if errors:
        return errors
    cfg = get_config().card
    allowed = ctx.post_urls | ctx.archive_urls | ctx.candidate_urls

    es = fields["earliest_seen"]
    if es["url"] is not None and es["url"] not in ctx.post_urls:
        errors.append("earliest_seen.url not in snapshot store")
    if es["url"] is None and es.get("note") != UNCONFIRMED_ZH:
        errors.append("earliest_seen without url must say 未能確認")

    os_ = fields["original_source"]
    if os_["traced"]:
        if os_["url"] is None or os_["url"] not in allowed:
            errors.append("original_source.url not in candidate set")
    else:
        if os_["url"] is not None or os_.get("note") != UNTRACED_ZH:
            errors.append("untraced original_source must have url=null and note=未能追溯")

    if fields["account_count"] != ctx.signal_account_count:
        errors.append(f"account_count {fields['account_count']} != SignalSet {ctx.signal_account_count}")
    if fields["timing_chart"] != ctx.signal_chart:
        errors.append("timing_chart differs from SignalSet")
    for a in fields["archive_links"]:
        if a["url"] not in ctx.post_urls or a["archive_url"] not in ctx.archive_urls:
            errors.append("archive_links entry not in snapshot store")

    ex = fields["sample_excerpt"]
    if len(ex) > cfg.sample_excerpt_max_chars:
        errors.append("sample_excerpt too long")
    if ex and not any(ex in t for t in ctx.post_texts):
        errors.append("sample_excerpt is not a verbatim substring of a cluster post")

    # 禁止用語:掃描 sample_excerpt 以外的所有字串(節錄是逐字資料)/ scan every string except the verbatim excerpt
    for path, s in _walk_strings({k: v for k, v in fields.items() if k != "sample_excerpt"}):
        if path.endswith(".url") or path.endswith(".archive_url") or path.endswith(".evidence_url") or path.endswith(".t") or path.endswith(".at"):
            continue
        m = _FORBIDDEN_RE.search(s)
        if m:
            errors.append(f"forbidden term '{m.group(0)}' at {path}")
    return errors


def strip_to_whitelist(obj: dict) -> dict:
    """超出白名單欄位即丟棄(文件 04)/ drop anything outside the whitelist (doc 04)."""
    return {k: obj[k] for k in WHITELIST if k in obj}

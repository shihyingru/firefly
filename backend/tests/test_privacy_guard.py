"""文件 08「明確不存」守衛:資料模型不得出現 IP、國籍、真實身分、原始平台識別碼欄位。
Doc-08 guard: the data model must not contain IP, nationality, real-identity, or raw platform-id columns."""
from firefly.models import FORBIDDEN_COLUMN_FRAGMENTS, Base


def test_no_forbidden_columns():
    offenders = []
    for table in Base.metadata.tables.values():
        for col in table.columns:
            name = col.name.lower()
            if any(frag in name for frag in FORBIDDEN_COLUMN_FRAGMENTS):
                offenders.append(f"{table.name}.{col.name}")
    assert offenders == []


def test_contributor_keeps_only_counts_not_urls():
    cols = {c.name for c in Base.metadata.tables["contributor"].columns}
    assert "lookup_count" in cols and "first_lookup_at" in cols
    assert not any("url" in c or "history" in c for c in cols)

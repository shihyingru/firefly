"""
資料模型(文件 08)/ Data model (doc 08).

硬約束 / Hard constraints:
- 「明確不存」:IP、國籍、真實姓名、聯絡方式、任何平台原始識別碼。本模組沒有這些欄位;tests/test_privacy_guard.py 會檢查。
  "Never stored": IP, nationality, real name, contact info, any raw platform identifier. No such columns exist here;
  tests/test_privacy_guard.py enforces it.
- 貢獻者只存 lookup_count 整數(D-009),不存查詢過的 URL。/ Contributors keep only an integer lookup_count (D-009).
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .config import get_config


class Base(DeclarativeBase):
    pass


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Platform(str, enum.Enum):
    threads = "threads"
    facebook = "facebook"
    other = "other"


class FetchStatus(str, enum.Enum):
    pending = "pending"
    ok = "ok"
    unfetchable = "unfetchable"


class ClusterStatus(str, enum.Enum):
    forming = "forming"
    active = "active"
    dormant = "dormant"
    archived = "archived"


class CardState(str, enum.Enum):
    draft = "draft"
    candidate = "candidate"
    displayed = "displayed"
    not_displayed = "not_displayed"


class ContributorOrigin(str, enum.Enum):
    line_hash = "line_hash"
    device = "device"
    threads_link = "threads_link"


class FlagKind(str, enum.Enum):
    not_in_cluster = "not_in_cluster"
    additional_source = "additional_source"


class FinanceKind(str, enum.Enum):
    donation = "donation"
    b2b = "b2b"
    grant = "grant"
    expense = "expense"


class PostSnapshot(Base):
    """貼文快照 / Post snapshot. 永久保存(證據性質);申訴可遮蔽 content_text。"""

    __tablename__ = "post_snapshot"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    source_url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)  # 正規化後 / normalized
    platform: Mapped[Platform] = mapped_column(Enum(Platform, name="platform"), nullable=False)
    author_handle: Mapped[str | None] = mapped_column(Text)  # 平台公開代號 / public handle only
    content_text: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64))  # 遮蔽後仍可比對 / survives redaction
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # D-004 nullable
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    fetch_status: Mapped[FetchStatus] = mapped_column(
        Enum(FetchStatus, name="fetch_status"), nullable=False, default=FetchStatus.pending
    )
    archive_url: Mapped[str | None] = mapped_column(Text)
    external_links: Mapped[list | None] = mapped_column(JSONB)  # 內文外部連結 / links found in body
    embedding: Mapped[list[float] | None] = mapped_column(Vector(get_config().embedding.dim))
    cluster_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cluster.id", ondelete="SET NULL"))

    cluster: Mapped[Cluster | None] = relationship(back_populates="posts", foreign_keys=[cluster_id])


class Cluster(Base):
    """說法叢集 / Claim cluster."""

    __tablename__ = "cluster"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    status: Mapped[ClusterStatus] = mapped_column(
        Enum(ClusterStatus, name="cluster_status"), nullable=False, default=ClusterStatus.forming
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_post_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    post_count: Mapped[int] = mapped_column(Integer, default=0)
    account_count: Mapped[int] = mapped_column(Integer, default=0)
    signal_summary: Mapped[dict | None] = mapped_column(JSONB)  # 三類指紋原始數據 / raw SignalSet
    centroid: Mapped[list[float] | None] = mapped_column(Vector(get_config().embedding.dim))
    current_card_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    posts: Mapped[list[PostSnapshot]] = relationship(back_populates="cluster", foreign_keys=[PostSnapshot.cluster_id])
    cards: Mapped[list[ContextCard]] = relationship(back_populates="cluster")


class ContextCard(Base):
    """脈絡卡 / Context card. fields 僅含文件 04 白名單七欄位。"""

    __tablename__ = "context_card"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    cluster_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cluster.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    fields: Mapped[dict] = mapped_column(JSONB, nullable=False)
    llm_model: Mapped[str | None] = mapped_column(Text)  # D-001 nullable
    prompt_ref: Mapped[str | None] = mapped_column(Text)  # audit_log id / nullable
    validation_passed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state: Mapped[CardState] = mapped_column(Enum(CardState, name="card_state"), nullable=False, default=CardState.draft)
    quality_score: Mapped[float | None] = mapped_column(Float)  # i_c
    vote_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 有效票 / valid votes
    spectrum_coverage: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    cluster: Mapped[Cluster] = relationship(back_populates="cards")
    votes: Mapped[list[Vote]] = relationship(back_populates="card")

    __table_args__ = (UniqueConstraint("cluster_id", "version", name="uq_card_cluster_version"),)


class Contributor(Base):
    """貢獻者 / Contributor. 匿名為預設;origin_key_hash 為單向雜湊,原值不落地。"""

    __tablename__ = "contributor"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    origin: Mapped[ContributorOrigin] = mapped_column(Enum(ContributorOrigin, name="contributor_origin"), nullable=False)
    origin_key_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    named_profile: Mapped[str | None] = mapped_column(String(64))  # 自選暱稱 / chosen nickname
    stance_vector: Mapped[list[float] | None] = mapped_column(ARRAY(Float))  # 僅引擎內部 / engine-internal only
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    lookup_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # D-009
    first_lookup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    votes: Mapped[list[Vote]] = relationship(back_populates="contributor")


class Vote(Base):
    """投票 / Vote. (contributor_id, card_id) 唯一 → 覆寫式冪等。永不公開個別投票。"""

    __tablename__ = "vote"

    contributor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contributor.id", ondelete="CASCADE"), primary_key=True
    )
    card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("context_card.id", ondelete="CASCADE"), primary_key=True)
    helpful: Mapped[bool] = mapped_column(Boolean, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)  # 降權後 < 1 / < 1 after down-weighting
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    contributor: Mapped[Contributor] = relationship(back_populates="votes")
    card: Mapped[ContextCard] = relationship(back_populates="votes")


class DomainSignal(Base):
    """網域訊號 / Domain signal. 留痕不硬刪 / never hard-deleted."""

    __tablename__ = "domain_signal"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    source_list: Mapped[str] = mapped_column(Text, nullable=False)
    list_version: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_url: Mapped[str | None] = mapped_column(Text)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_domain_signal_domain", "domain"),)


class ClusterFlag(Base):
    """具名貢獻者對叢集的標記(聚類錯誤/補充出處)。不公開個別紀錄。/ Named-contributor flags. Not public."""

    __tablename__ = "cluster_flag"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    cluster_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cluster.id", ondelete="CASCADE"), nullable=False)
    contributor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contributor.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[FlagKind] = mapped_column(Enum(FlagKind, name="flag_kind"), nullable=False)
    post_url: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    """審計 / Audit log. append-only,全表公開(文件 12)。payload 不得含個人層級資料。"""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64))
    event: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"),)


class FinanceRecord(Base):
    """收支 / Finance record. 只記類別,不記個別捐款人 / counterparty class only."""

    __tablename__ = "finance_record"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    kind: Mapped[FinanceKind] = mapped_column(Enum(FinanceKind, name="finance_kind"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TWD")
    counterparty_class: Mapped[str] = mapped_column(String(64), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# 明確不存清單(文件 08)— 供 tests/test_privacy_guard.py 掃描欄位名稱
# Forbidden-column list (doc 08) — scanned by tests/test_privacy_guard.py
FORBIDDEN_COLUMN_FRAGMENTS = ("ip_", "_ip", "ipaddr", "nationality", "real_name", "full_name", "email", "phone", "line_user_id", "raw_user_id")

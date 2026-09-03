"""
設定載入 / Configuration loading.

兩層 / Two layers:
1. `config/firefly.yaml`:可調參數,版本化、公開(文件 12)。/ tunable parameters, versioned and public (doc 12).
2. 環境變數:連線字串與密鑰,永不入庫。/ environment: connection strings and secrets, never committed.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class ClusteringCfg(BaseModel):
    theta_join: float = 0.92
    k_min_posts: int = 3
    dormant_days: int = 30
    archive_after_dormant_days: int = 90


class EmbeddingCfg(BaseModel):
    backend: str = "e5"
    model: str = "intfloat/multilingual-e5-base"
    dim: int = 768
    query_prefix: str = "query: "
    passage_prefix: str = "passage: "


class BridgingCfg(BaseModel):
    theta_helpful: float = 0.40
    hysteresis: float = 0.05
    n_min_votes: int = 5
    lambda_intercept: float = 0.15
    lambda_factor: float = 0.03
    factor_dim: int = 1
    min_votes_per_rater: int = 2
    phase_a_max_active_arbiters: int = 100
    recompute_interval_minutes: int = 60
    burst_zscore_threshold: float = 3.0
    burst_window_minutes: int = 60


class EligibilityCfg(BaseModel):
    min_lookups: int = 3
    min_account_age_hours: int = 24


class CardCfg(BaseModel):
    sample_excerpt_max_chars: int = 140
    llm_enabled: bool = False
    llm_model: str = "claude-opus-5"
    max_validation_retries: int = 3
    redraft_thresholds: list[int] = Field(default_factory=lambda: [3, 5, 10, 20, 50, 100, 200, 500])
    original_source_min_shared_authors: int = 2


class Stage0Cfg(BaseModel):
    archive_enabled: bool = False
    archive_timeout_seconds: int = 25


class FingerprintCfg(BaseModel):
    sync_window_minutes: int = 60
    chart_bucket_minutes: int = 15
    rules_path: str = "config/fingerprint_rules.yaml"
    domain_signals_path: str = "config/domain_signals.yaml"


class RateLimitCfg(BaseModel):
    anonymous_per_hour: int = 60
    contributor_per_hour: int = 300
    window_seconds: int = 3600
    ip_retention_seconds: int = 86400


class QueueCfg(BaseModel):
    default_limit: int = 5
    max_limit: int = 20
    strategy: str = "phase_a_fewest_votes"


class IngestionCfg(BaseModel):
    keyword_search_daily_budget: int = 1700
    sibling_search_per_lookup: int = 1
    tag_patrol_interval_minutes: int = 60
    tags: list[str] = Field(default_factory=list)
    domain_lookback_interval_minutes: int = 360


class ThreadsCfg(BaseModel):
    enabled: bool = False
    daily_reply_cap: int = 200
    quota_margin: float = 0.2
    mention_poll_interval_seconds: int = 300
    reply_max_chars: int = 480
    pending_retry_limit: int = 6


class LineCfg(BaseModel):
    enabled: bool = True
    onboarding_push_enabled: bool = False  # D-014:公示期結束前維持 false / stays false until the doc-10 notice period ends
    onboarding_push_days: int = 3
    onboarding_push_hour_local: int = 20   # Asia/Taipei
    onboarding_push_daily_cap: int = 100
    queue_size: int = 5


class CorsCfg(BaseModel):
    open_data_origins: list[str] = Field(default_factory=lambda: ["*"])
    write_origins: list[str] = Field(default_factory=list)


class FireflyConfig(BaseModel):
    version: int = 1
    clustering: ClusteringCfg = ClusteringCfg()
    embedding: EmbeddingCfg = EmbeddingCfg()
    bridging: BridgingCfg = BridgingCfg()
    eligibility: EligibilityCfg = EligibilityCfg()
    card: CardCfg = CardCfg()
    stage0: Stage0Cfg = Stage0Cfg()
    fingerprint: FingerprintCfg = FingerprintCfg()
    ratelimit: RateLimitCfg = RateLimitCfg()
    queue: QueueCfg = QueueCfg()
    ingestion: IngestionCfg = IngestionCfg()
    threads: ThreadsCfg = ThreadsCfg()
    line: LineCfg = LineCfg()
    cors: CorsCfg = CorsCfg()


class Settings(BaseSettings):
    """環境變數(密鑰與連線)/ environment (secrets and connections)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres@127.0.0.1:5432/firefly"
    redis_url: str = "redis://127.0.0.1:6379/0"
    firefly_config_path: str = str(REPO_ROOT / "config" / "firefly.yaml")
    device_token_pepper: str = "dev-pepper-change-me"
    line_id_hmac_key: str = "dev-hmac-change-me"
    service_token: str = "dev-service-token-change-me"
    line_channel_secret: str = ""
    line_channel_access_token: str = ""
    line_push_enc_key: str = ""  # Fernet key(base64 32 bytes);D-014 引導期推播用,輪替走 runbook / rotate via runbook
    threads_app_id: str = ""
    threads_app_secret: str = ""
    threads_user_token: str = ""
    threads_webhook_verify_token: str = ""
    public_base_url: str = "http://localhost:8000"
    environment: str = "dev"
    wayback_access_key: str = ""
    wayback_secret_key: str = ""
    anthropic_api_key: str = ""  # 僅 card.llm_enabled=true 時需要 / only when card.llm_enabled


def load_config(path: str | os.PathLike[str] | None = None) -> FireflyConfig:
    """讀取 YAML 設定;檔案不存在時回預設值(僅測試用途)。/ Load YAML; defaults if missing (tests only)."""
    p = Path(path or get_settings().firefly_config_path)
    if not p.exists():
        return FireflyConfig()
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return FireflyConfig.model_validate(data)


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_config() -> FireflyConfig:
    return load_config()


def reset_caches() -> None:
    """測試用:清除快取以重新載入設定。/ Tests: clear caches to reload config."""
    get_settings.cache_clear()
    get_config.cache_clear()

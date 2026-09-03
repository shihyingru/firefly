"""initial schema (doc 08 + D-002/D-004/D-007/D-009)

Revision ID: 0001
Revises:
"""
from __future__ import annotations

from alembic import op
from firefly.config import get_config
from firefly.models import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    dim = get_config().embedding.dim
    op.execute("CREATE INDEX IF NOT EXISTS ix_post_embedding_hnsw ON post_snapshot USING hnsw (embedding vector_cosine_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_cluster_centroid_hnsw ON cluster USING hnsw (centroid vector_cosine_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_post_cluster ON post_snapshot (cluster_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_card_state_votes ON context_card (state, vote_count)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vote_card ON vote (card_id)")
    op.execute(f"COMMENT ON COLUMN post_snapshot.embedding IS 'vector({dim}); dim from config embedding.dim'")


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
    for t in ("platform", "fetch_status", "cluster_status", "card_state", "contributor_origin", "flag_kind", "finance_kind"):
        op.execute(f"DROP TYPE IF EXISTS {t}")

"""
嵌入 / Embeddings(Stage 2)。

- E5Embedder:multilingual-e5-base(D-012),需 `pip install -e "backend[ml]"` 與模型下載。
- HashEmbedder:字元 n-gram 雜湊向量。無模型時的替代(測試、離線示範)。品質低於 e5,θ_join 需另行校準;
  使用中的後端名稱寫入 cluster.signal_summary.embedder,審計可辨。
- E5Embedder: multilingual-e5-base (D-012); needs the `ml` extra and a model download.
- HashEmbedder: hashed char n-grams. Fallback without a model (tests, offline demo). Lower quality; θ_join must be
  recalibrated; the active backend name is recorded in cluster.signal_summary.embedder for auditability.
"""
from __future__ import annotations

import hashlib
import math
import os
import re
from functools import lru_cache
from typing import Protocol

from ..config import get_config


class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


_WS = re.compile(r"\s+")


def _normalize_text(t: str) -> str:
    t = _WS.sub(" ", (t or "").strip().lower())
    t = re.sub(r"https?://\S+", " URL ", t)  # 連結不進語意 / links carry no semantics here
    return t


class HashEmbedder:
    name = "hash-ngram"

    def __init__(self, dim: int):
        self.dim = dim

    def _one(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        t = _normalize_text(text)
        grams = [t[i : i + n] for n in (2, 3) for i in range(max(0, len(t) - n + 1))]
        for g in grams:
            h = int.from_bytes(hashlib.blake2b(g.encode(), digest_size=8).digest(), "little")
            v[h % self.dim] += 1.0 if (h >> 63) else -1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]


class E5Embedder:
    name = "e5"

    def __init__(self, model: str, dim: int, passage_prefix: str):
        from sentence_transformers import SentenceTransformer  # noqa: WPS433 (optional dep)

        self.model = SentenceTransformer(model, device="cpu")
        self.dim = dim
        self.prefix = passage_prefix
        self.name = f"e5:{model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        vecs = self.model.encode([self.prefix + _normalize_text(t) for t in texts], normalize_embeddings=True)
        return [list(map(float, v)) for v in vecs]


@lru_cache
def get_embedder() -> Embedder:
    cfg = get_config().embedding
    backend = os.environ.get("FIREFLY_EMBEDDER", cfg.backend)
    if backend == "e5":
        try:
            return E5Embedder(cfg.model, cfg.dim, cfg.passage_prefix)
        except Exception:  # noqa: BLE001 - model missing/offline → fallback, recorded in audit
            return HashEmbedder(cfg.dim)
    return HashEmbedder(cfg.dim)


def cosine(a: list[float], b: list[float]) -> float:
    return float(sum(x * y for x, y in zip(a, b, strict=True)))

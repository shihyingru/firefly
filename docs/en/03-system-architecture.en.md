# 03 | System Architecture

> Firefly (螢火) | v0.1 | 2026-07-20 | AGPL-3.0

## Goals & Constraints

- Sustainable for a single maintainer: one VPS initially, fully containerized, no on-call dependency
- Amortized AI cost: draft once per cluster, queries hit cache
- Every component re-runnable and verifiable by third parties (AGPL-3.0)

## Component Overview

```
[LINE Bot] [Threads Bot] [Share Target App] [Arbiter Queue] [Extension (later)]
        \        |          |            /
              [API Gateway]
                   |
     +----------------------------------------+
     |            AI Pipeline (doc 04)         |
     | fingerprints → clustering → card draft  |
     +----------------------------------------+
                   |
        [Human arbitration (one-tap votes)]
                   |
        [Bridging scoring engine (doc 05)]
                   |
        [Transparency layer: dashboard / open data / posting log]
```

## Technology Choices (suggested; implementing model may adjust)

| Layer | Choice | Rationale |
|---|---|---|
| API service | Python + FastAPI | Same language as the ML ecosystem; lowest single-maintainer cost |
| Database | PostgreSQL + pgvector | Relational + vector search in one store; no separate vector DB to operate |
| Queue | Redis (RQ/Celery) | Fingerprinting and drafting are async jobs |
| Cache | Redis | Card queries hit cache; LINE/Threads replies return in seconds |
| Embeddings | Multilingual model (self-hostable small model) | Clustering cost near zero |
| Drafting LLM | External API, once per cluster | Amortized cost; prompts and outputs fully written to public audit log |
| Deployment | Docker Compose → single VPS; k8s optional later | Simplicity first |
| Monitoring | Open source (Grafana/Prometheus) | Same metrics serve internal ops and the public transparency layer |

## Data Flow (query path)

1. Entry receives link → gateway normalizes URL → cache lookup
2. Hit: return card directly (p50 < 1s)
3. Miss: snapshot task → fingerprinting → cluster assignment → draft card if cluster has none → return and cache

## Data Flow (arbitration path)

1. Vote written via gateway (with anonymous contributor handle)
2. Bridging engine batch re-scores (hourly initially; incremental at scale)
3. Card display state updated: candidate → displayed / returned

## Key Trade-offs (ADR summary)

- **pgvector in one DB vs dedicated vector store**: former. Sufficient at 10^5–10^6 posts; one less operational surface
- **Batch re-scoring vs realtime**: batch. Bridging requires global matrix factorization; realtime complexity isn't worth it
- **Self-hosted LLM vs API**: API. Once-per-cluster volume can't justify self-hosting; transparency achieved by logging prompts/outputs
- **Stage 3 deterministic-first (2026-09-03)**: whitelist fields are computed by code; the LLM only proposes original_source from a closed candidate set and is off by default. Rationale: smaller injection/hallucination surface; every card is 100% replayable from data
- **Platform dependency risk**: Threads/LINE can both be cut off; the share-target app is the fully self-controlled fallback entry, hence mandatory in Wave 2

## Expansion Path

- Multi-language: embeddings are inherently multilingual; fingerprint rules packaged per language
- Multi-platform: add source adapters at the detection layer (Facebook/YouTube comments etc.); downstream unchanged
- Cross-border deployment: fully Dockerized; other communities can self-host (AGPL guarantees derivative services stay open)

# 04 | AI Pipeline Specification

> Firefly (螢火) | v0.1 | 2026-07-20 | AGPL-3.0
> Principle: the AI is a clerk. No stage of the pipeline may output opinionated inference.

## Stage 0: Ingestion & Preservation

- Input: public post URL (normalized, tracking params stripped)
- Actions: fetch text content, author's public handle, timestamp; submit to Wayback Machine in parallel
- Output: PostSnapshot (with archive_url)
- Failure: non-public/deleted → mark unfetchable; tell the querier "content could not be retrieved"

## Stage 1: Fingerprint Detection

Three signal families, scored independently, never aggregated into a verdict (evidence is listed, not judged):

1. **Formatting fingerprints**: rule engine. Configurable pattern library; initial rules include published farm formulas ("N short lines + emoji + trailing hashtag" etc.); rules managed in YAML, open source, with citations
2. **Domain fingerprints**: link domains matched against public lists (doc 09); list version recorded and cited on cards
3. **Timing fingerprints**: posting-time distribution within a cluster; synchrony metrics (e.g. N accounts within a T-minute window)

Output: SignalSet (each item carries raw data + a link to its computation method; all re-runnable)

## Stage 2: Semantic Clustering

- Embedding: multilingual model (candidates: multilingual-e5 class; finalize via benchmark), vectors into pgvector
- Assignment: nearest-neighbor search against existing clusters; cosine ≥ θ_join (initial 0.92, calibrate empirically) joins; otherwise held as isolated point
- Formation: K isolated points (initial K=3) with mutual similarity above threshold → new cluster
- Lifecycle: active → dormant (30 days no additions) → archived; a dormant cluster reviving triggers card re-review

## Stage 3: Context Card Drafting

- Trigger: cluster formation or major update (account count crosses threshold)
- LLM call: once per cluster; prompt, model version, raw output fully written to the (public) audit log
- **Field whitelist (hard constraint)**:
  - earliest_seen: first appearance time + source link
  - original_source: traceable origin ("could not be traced" stated explicitly when unknown)
  - account_count: number of accounts posting identical/near-identical content
  - timing_chart: synchrony chart (rendered directly from Stage 1 data, not LLM-generated)
  - archive_links: snapshot link list
  - domain_note: domain match result + list version
- **Post-validation (anti-hallucination)**: programmatic checks on the draft — every link must resolve and match the snapshot store; every number must match the SignalSet; any field failing → whole card regenerated; repeated failures go to a human review queue
- **Forbidden**: adjectival verdicts (suspicious/manipulative/fake), intent speculation, stance description. Output validated against a JSON schema; fields outside the whitelist are dropped

## Cost Model

- Fingerprints: rules + SQL, near zero
- Embeddings: self-hosted small model, < NT$1 per thousand posts
- Drafting: one LLM call per cluster; billed by cluster count, not post/query count → 460k posts compressed to 500 clusters costs hundreds of NT$ total
- Queries: fully cached, zero AI cost

## Quality Loop

- Arbitration feedback: card types with high "not helpful" ratios → prompt revision (changes go through public PRs)
- Clustering-error reports: named contributors can flag "this post doesn't belong to this cluster"; threshold triggers re-clustering

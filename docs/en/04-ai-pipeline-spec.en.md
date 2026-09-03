# 04 | AI Pipeline Specification

> Firefly (螢火) | v0.2 | 2026-09-03 | AGPL-3.0
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

## Stage 3: Context Card Drafting (deterministic-first)

> v0.2 change (2026-09-03, maintainer decision): Stage 3 is now "deterministic-first". Six of the seven whitelist fields are computed directly by code; the LLM is not involved. The LLM only proposes a candidate for original_source, and the candidate is restricted to a closed set. Rationale: every whitelist field can be derived from the SignalSet and the snapshot store; shrinking the LLM's role shrinks the prompt-injection and hallucination surface (doc 14 T5).

- Trigger: cluster formation or major update (account count crosses threshold)
- **Field whitelist (hard constraint)** and the producer of each field:

  | Field | Content | Producer |
  |---|---|---|
  | earliest_seen | first appearance time + source link | code: min posted_at in cluster |
  | original_source | traceable origin ("could not be traced" stated explicitly when unknown) | code by default, LLM optional (see below) |
  | account_count | number of accounts posting identical/near-identical content | code: distinct author_handle count in cluster |
  | timing_chart | synchrony chart (data-point array) | code: Stage 1 timing fingerprint |
  | archive_links | snapshot link list | code: archive_url from snapshot store |
  | domain_note | domain match result + list version | code: Stage 1 domain fingerprint |
  | sample_excerpt | **verbatim** excerpt of the earliest post in the cluster; max length set in config | code truncation, never LLM |

  Purpose of sample_excerpt: an arbiter in the queue must know which claim a card refers to. A verbatim quote is not stance inference. The excerpt must not be rewritten or summarized.

- **How original_source is produced**:
  1. Code first builds a "candidate set": every post URL in the cluster, plus every external link found in post bodies
  2. Default value: the candidate with the earliest posted_at; if no post has a recognizable origin, write "could not be traced"
  3. The LLM step is **optional** (feature flag, off by default): the LLM may only pick one URL from the candidate set, or answer "could not be traced". It may not produce a URL outside the set and may not emit any other field
  4. When enabled, one call per cluster; prompt, model version, raw output fully written to the (public) audit log
- **Post-validation (anti-hallucination)**: programmatic checks on the output — every link must exist in the snapshot store or the candidate set; every number must match the SignalSet; sample_excerpt must match the snapshot content_text verbatim; any field failing → whole card regenerated; repeated failures go to a human review queue
- **Forbidden**: adjectival verdicts (suspicious/manipulative/fake), intent speculation, stance description. Output validated against a JSON schema; fields outside the whitelist are dropped

## Cost Model

- Fingerprints: rules + SQL, near zero
- Embeddings: self-hosted small model, < NT$1 per thousand posts
- Drafting: deterministic computation is near zero; with the LLM step off there is no API cost. When on, one call per cluster; billed by cluster count, not post/query count → 460k posts compressed to 500 clusters costs hundreds of NT$ total
- Queries: fully cached, zero AI cost

## Quality Loop

- Arbitration feedback: card types with high "not helpful" ratios → prompt revision (changes go through public PRs)
- Clustering-error reports: named contributors can flag "this post doesn't belong to this cluster"; threshold triggers re-clustering

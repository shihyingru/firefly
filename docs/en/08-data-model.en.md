# 08 | Data Model

> Firefly (螢火) | v0.1 | 2026-07-20 | AGPL-3.0
> Principles: minimal collection; personal data is hashed or never stored; every decision replayable from data.

## Entities

### post_snapshot
| Field | Type | Notes |
|---|---|---|
| id | uuid PK | |
| source_url | text unique | normalized URL |
| platform | enum | threads/facebook/other |
| author_handle | text | public platform handle |
| content_text | text | text at fetch time |
| posted_at | timestamptz nullable | platform-displayed time; null when the source does not provide it (e.g. oEmbed); timing fingerprints use non-null values only |
| fetched_at | timestamptz | |
| archive_url | text | Wayback snapshot |
| embedding | vector(N) | pgvector; N set by config embedding.dim, initially 768 (multilingual-e5-base) |
| cluster_id | uuid FK nullable | |

### cluster
id, status (forming/active/dormant/archived), created_at, post_count, account_count, signal_summary (jsonb: raw data of the three fingerprint families), current_card_id

### context_card
id, cluster_id FK, version, fields (jsonb, the seven doc-04 whitelist fields only, incl. sample_excerpt), llm_model (nullable; empty when the LLM step is off), prompt_ref (audit-log pointer, nullable), validation_passed_at, state (draft/candidate/displayed/not_displayed), quality_score (i_c), vote_count

### contributor
| Field | Notes |
|---|---|
| id | uuid PK |
| origin | enum: line_hash/device/threads_link |
| origin_key_hash | one-way hash (raw LINE userId etc. never lands) |
| named_profile | nullable: self-chosen nickname (named contributors) |
| stance_vector | float[] (bridging-engine output; scoring only, never exposed) |
| created_at / last_active_at | |
| lookup_count / first_lookup_at | integer count and first-lookup time, used only for the voting eligibility threshold (doc 05). **Never** stores looked-up URLs, clusters, or time series |

**Explicitly never stored**: IP (abuse-prevention rolling window only, deleted after 24h), nationality, real names, contact info, any raw platform identifiers.

### vote
contributor_id FK, card_id FK, helpful bool, created_at, weight (<1 after down-weight flags); (contributor_id, card_id) unique → overwrite idempotency

### domain_signal
domain, source_list (provenance, e.g. DTL report), list_version, evidence_url, added_at, removed_at nullable (appeal removals leave traces, no hard delete)

### audit_log
entity_type, entity_id, event, payload (jsonb), created_at — card state changes, prompts/outputs, parameter changes all included; **entire table public**

### finance_record
kind (donation/b2b/grant/expense), amount, currency, counterparty_class (donor identity never recorded, only class), note, occurred_at — feeds the transparency dashboard and open data

## Relations (text form)

```
post_snapshot >—— cluster ——< context_card ——< vote >—— contributor
domain_signal (independent dimension, referenced via signal_summary)
audit_log / finance_record (event streams, append-only)
```

## Collection Boundary — Three Principles (hard constraints; implementation may not relax)

1. **Query aggregates = built-in and allowed**: cluster-level statistics arising from user-initiated queries (e.g. "most-queried clusters this week") are a natural service by-product, published only in aggregate; never linked to any personal or device-level long-term profile
2. **Passive reading tracking = never, including anonymized**: any reporting of "what a user read/scrolled past" is prohibited. Behavioral sequences are themselves fingerprints; anonymization does not hold; clients must not embed browsing probes. If population-level statistics ever become necessary, the only acceptable path is on-device local aggregation + differential-privacy upload, subject to public deliberation via governance (doc 10) before implementation
3. **Literacy diary = purely on-device**: all data and computation for the reading-habit mirror feature (including statistics and comment generation) stays on the device — no upload, no cloud backup, no account login required; comment generation prefers an on-device local model. Presentation follows doc 02 tone rules — lay out distributions and ask questions; never issue a "biased" verdict

## Retention Policy

- post_snapshot: permanent (evidentiary); on successful appeal via governance, content_text may be masked while hash and archive pointer remain
- vote: permanent (anonymous); open-data release is k-anonymized
- Abuse-prevention temporaries (IP, rate windows): 24-hour rolling deletion
- Backups: daily encrypted offsite; restore drill quarterly

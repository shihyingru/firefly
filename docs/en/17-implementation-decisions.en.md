# 17 | Implementation Decision Record

> Firefly (螢火) | v0.1 | 2026-09-03 | AGPL-3.0
> Design decisions made during implementation. Each entry has a date, the decision, the rationale, and affected docs. New decisions are appended; old entries are never rewritten.

| # | Date | Decision | Rationale | Docs |
|---|---|---|---|---|
| D-001 | 2026-09-03 | Stage 3 deterministic-first: whitelist fields computed by code; LLM optional, off by default, may only pick original_source from a closed candidate set | Smaller injection/hallucination surface; cards fully replayable from data | 03, 04, 14 |
| D-002 | 2026-09-03 | Add sample_excerpt to the whitelist (verbatim excerpt of the earliest post, code-truncated) | Arbiters must know which claim a card refers to; a verbatim quote is not stance inference | 04, 06, 08 |
| D-003 | 2026-09-03 | Start Meta App Review (oEmbed Read, threads_keyword_search, threads_manage_mentions) | Verified: all three Threads data paths return no real data before review | 07, 13 |
| D-004 | 2026-09-03 | post_snapshot.posted_at nullable; timing fingerprints use non-null values only; earliest_seen says "could not be confirmed" when no reliable time exists | oEmbed may not provide the post time; the API cannot read another user's post | 04, 08 |
| D-005 | 2026-09-03 | Keep the doc-13 red line: never scrape Threads public web pages | Technically feasible (no login wall observed) but violates platform terms and the neutrality commitment | 09, 13 |
| D-006 | 2026-09-03 | Ingestion strategies A (lookup-triggered sibling search), B (tag patrol), C (domain look-back) | A single URL cannot reach K=3; clusters need an official-API growth source | 03, 04 |
| D-007 | 2026-09-03 | Add POST /devices to issue anonymous device handles | Doc 06 did not define the issuing endpoint | 06 |
| D-008 | 2026-09-03 | On 202, LINE replies "processing" with a "check again" button; no push, no waiting | Reply tokens are single-use; doc 7.1 forbids push | 07 |
| D-009 | 2026-09-03 | Contributor eligibility stores only lookup_count and first_lookup_at; never URLs, clusters, or time series | Doc 05 needs a threshold; doc 08 forbids device-level profiles | 05, 08 |
| D-010 | 2026-09-03 | Phase A queue: exclude already-voted cards, fewest-votes candidate first, random among ties | No stance vectors in Phase A; this is an operational metric allowed by doc 10 | 05, 06 |
| D-011 | 2026-09-03 | LINE userId hash is HMAC-SHA256 with a server secret | On a DB leak, nobody without the secret can map a known userId to a handle | 07 |
| D-012 | 2026-09-03 | Initial embedding model multilingual-e5-base, 768 dims; dimension lives in config | Matches doc 08; runs on CPU; adequate Chinese quality | 08 |
| D-013 | 2026-09-03 | θ_helpful and the regularization constants (λ_intercept, λ_factor) must live together in config and be calibrated together | A threshold without its regularization loses its reference | 05, 12 |
| D-014 | pending | The daily "tomorrow's queue" push (doc 7.1) needs a pushable LINE userId. Only an HMAC handle is stored, which cannot be reversed, so push is impossible. Options: (a) store an encrypted userId for opted-in users (new data item; requires doc-10 30-day notice); (b) replace push with a user-initiated rich-menu "today's queue" pull, zero storage. **Maintainer decision pending; Wave 1.3 ships without push.** | Doc 7.1 conflicts with doc 08 | 07, 08, 10 |
| D-015 | 2026-09-03 | Bridging engine adds rater pruning: handles with < min_votes_per_rater votes (initially 2; Community Notes uses 10) are excluded from factorization; the spectrum-imbalance threshold MIN_COVERAGE is marked TODO(calibrate) | Simulation showed single-card brigading shifts the global intercept; pruning is CN's standard defense | 05, 12 |

Evidence: `docs/verification/threads-probe-phase1.md`, `docs/verification/threads-probe-summary.md`.

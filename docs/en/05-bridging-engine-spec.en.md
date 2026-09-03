# 05 | Bridging Scoring Engine Specification

> Firefly (螢火) | v0.1 | 2026-07-20 | AGPL-3.0
> Base: matrix-factorization scoring from X Community Notes open source (https://github.com/twitter/communitynotes), trimmed to this project's scale

## Model

Each vote is modeled as:

```
r_{u,c} ≈ μ + i_u + i_c + f_u · f_c
```

- r_{u,c}: contributor u's rating of card c (helpful=1 / not helpful=0)
- μ: global intercept
- i_u: contributor leniency (some people upvote everything; absorbed here)
- i_c: **card quality score (the signal we want)**
- f_u · f_c: contributor stance vector × card leaning vector (echo-chamber noise; absorbed and discarded)

Solved by regularized alternating least squares or SGD; dimensionality starts at 1 (same as Community Notes), raised only if insufficient.

## Display Decision

- Card state machine: `draft → candidate → displayed / not_displayed`
- candidate → displayed: i_c ≥ θ_helpful (initial 0.40, following Community Notes' public threshold; calibrate locally) AND valid votes ≥ N_min (initial 5)
- Displayed cards keep being re-scored; falling below θ_helpful − hysteresis band (0.05) → back to candidate (prevents boundary flapping)
- Cards with insufficient votes stay candidate — visible to queriers, labeled "context awaiting arbitration"

## Cold-Start Special Case

While contributors are too few to estimate stance vectors:

1. Phase A (< 100 active arbiters): no display decisions; all cards run as "query-visible + awaiting-arbitration label"; vote matrix accumulates; queue uses "fewest votes first" (doc 06)
2. Phase B: full bridging scoring activates once matrix density suffices; all Phase A votes retained for training
3. Spectrum diversity metric: bimodal coverage of the stance-vector distribution; published on the dashboard; when unmet, cards display "arbitration spectrum not yet balanced"

## Anti-Manipulation Properties

- Sybil: behaviorally identical account groups collapse into one stance vector during factorization; vote-stuffing gains are sublinear
- Burst detection: abnormal per-card vote velocity (z-score) → that window's votes down-weighted and flagged for audit
- Contributor eligibility: voting requires accumulated organic query history (blocks pure registration bots); no real names required
- All down-weighting/flagging rules are open source; parameter changes go through public PRs

## Re-scoring Cadence

- Full batch re-score: hourly (minutes on one machine at initial data volume)
- Card display-state changes written to the (public) audit log: time, before/after state, i_c at that run, vote count

## External Outputs

- Per card, public: i_c, valid vote count, spectrum diversity metric (no individual votes ever)
- Researcher open data: anonymized vote matrix (k-anonymized), quarterly release

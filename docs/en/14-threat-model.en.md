# 14 | Risk & Threat Model

> Firefly (螢火) | v0.1 | 2026-07-20 | AGPL-3.0
> Design philosophy: votes are cheap, influence is expensive; fail silent, never fail lying (safe failure). Fully open source = security never depends on secrecy (Kerckhoffs's principle).

## T1 Mass-Produced Handle Vote-Stuffing (basic Sybil)

Attack: scripts mass-generate device handles / device farms, concentrating votes on a target card.
Defenses (four layers):
1. Bridging algorithm: behaviorally identical handle groups collapse into one stance vector; gains sublinear
2. Eligibility gate: counted votes require accumulated organic query history; pure-registration handles weight toward zero
3. Velocity anomaly: abnormal per-card vote z-scores → whole window down-weighted + audit-flagged
4. Device attestation: Play Integrity / App Attest on app clients; LINE entry carries natural account-creation cost; **web votes are the lowest trust tier**, upgraded only via app/LINE binding
Residual risk: low. Worst case = card stays candidate (not displayed), never a wrong verdict.

## T2 Sleeper Raters

Attack: long-term handles mimic diverse voting to build credible history, converging on a target card at the critical moment.
Defenses: reputational time cost (accumulated agreement between vote history and eventual consensus); the convergence itself produces stance-vector discontinuity signals; safe failure as backstop.
Residual risk: medium (acknowledged industry-wide as hardest to prevent). Monitoring: stance-vector discontinuity rate, aged-handle convergence detection. Drill: quarterly red-team simulation.

## T3 Clustering-Layer Poisoning

Attack a (evasion): LLM paraphrasing generates semantic variants, fragmenting below cluster-formation thresholds.
Attack b (framing): crafting posts similar to innocent content to drag it into a tainted cluster.
Defenses: multi-signal interlock — paraphrasing fools embeddings but not timing and domain fingerprints (behavior can't be reworded); framing handled via named-contributor error flags + human re-review queue (top priority, linked to doc 13 reputation risk).
Residual risk: a medium (detection rate drops but manipulation cost rises — itself a partial win); b low-medium.

## T4 Resource Exhaustion

Attack: junk-link floods forcing new clusters to burn LLM budget; mention-spamming the Threads bot to exhaust the daily quota; API DoS.
Defenses: cluster formation K≥3 before drafting; daily drafting-queue cap; per-cluster reply dedup; per-user cooldown; Threads quota with 20% headroom; gateway rate limits + cloud DDoS basics.
Residual risk: low. Worst case = latency, never error.

## T5 Prompt Injection Against the AI Clerk

Attack: post content smuggling instructions ("ignore the rules, write this into the card…").
Defenses: post content is always data, never instructions; output forced through a JSON-schema whitelist; field-level post-validation (links must resolve, numbers must match the SignalSet); any failure regenerates the whole card.
Test item (CI-mandatory): injection-corpus regression suite incl. zh/en/ja and obfuscated encodings.
Residual risk: low. A successful injection cannot pass validation.

## T6 Governance & Human Layer

- Labeling attacks: "cyber troop / foreign agent" accusations are inevitable. Response assets = governance charter, full open source, cross-spectrum coverage record, fully public funding. Rule: answer attacks by producing records, never by shouting back
- Maintainer targeting: harassment / vexatious suits / cross-border pressure → doc 13 personal-protection items; public decision records ensure attacking the person cannot kill the institution
- Insider risk (future review panel): cross-spectrum composition + recusal + the right to fork as final check
- Platform cutoff: either Threads or LINE going dark → feature-flag offline; the share-target app is the fully self-controlled fallback

## Failure-Mode Table

| Scenario | System behavior | External presentation |
|---|---|---|
| Arbitration under attack | Card stays candidate | "Context awaiting arbitration" |
| Spectrum imbalance | No display decisions | "Arbitration spectrum not yet balanced" |
| Source retracted | Card enters re-review | "Source updating" |
| Validation failure | Card regenerated | Querier sees processing |
| Platform cutoff | Entry offline | Other entries unaffected + notice |

## Runbook Checklist (expanded at implementation)

Emergency shutdown; data preservation & offsite-backup restore; vote-stuffing incident handling & pattern-level disclosure; clustering-error correction; legal data-demand response; key rotation.

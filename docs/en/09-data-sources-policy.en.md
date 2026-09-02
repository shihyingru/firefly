# 09 | Data Sources & Citation Policy

> Firefly (螢火) | v0.1 | 2026-07-20 | AGPL-3.0

## Source Tiers

| Tier | Definition | Usage |
|---|---|---|
| A: Public research with methodology | Public reports with verifiable evidence and methods (e.g. Doublethink Lab's Borderless Group research) | Directly admissible into domain_signal; cards cite report link and list version |
| B: Official platform announcements | Meta CIB takedown announcements etc. | Same as A |
| C: Crowd submissions | Supplementary sources submitted by named contributors | Candidates only; promoted after fingerprint verification or dual-source confirmation |
| D: In-house detection | This system's timing/formatting/clustering signals | Presented as "observed data" with computation methods attached; never cited as external authority |

Not admissible: anonymous tips, stance-based media lists without methodology, any non-public lists provided by government agencies (neutrality red line).

## Citation Rules

- Every external datum on a card carries: source name, link, retrieval date, list version number
- Source updates: A/B tiers checked weekly; version changes written to audit_log
- Source retraction: upstream retraction/correction → affected cards automatically enter the re-review queue, labeled "source updating" meanwhile

## Appeals & Removal

1. Affected parties (domain owners, account holders) file via a public form with identity evidence
2. Initial response within 72 hours; re-review executed by the review panel defined in the governance charter (doc 10)
3. Upheld: domain_signal marked removed_at (trace kept, no hard delete); related cards regenerated
4. Rejected: reasons provided; appeal records (de-identified) enter public statistics
5. Appellant identity never published; only case volume and processing-time statistics are public

## Collection Boundaries

- Public posts only; no login walls bypassed, no private content crawled
- Platform APIs used wherever available; snapshot fetching respects robots and rate etiquette
- Account-level data limited to public platform handles; no cross-platform identity linking

## Licensing of This Project's Output Data

- Context cards and signal open data: CC BY 4.0 (attribution required, commercial use allowed — B2B value lies in quota and SLA, not data exclusivity)
- Code: AGPL-3.0
- Suggested citation format provided in the README

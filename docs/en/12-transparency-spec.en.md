# 12 | Transparency & Disclosure Specification

> Firefly (螢火) | v0.1 | 2026-07-20 | AGPL-3.0
> Principle: total system transparency, total user privacy. Transparency applies to mechanisms and patterns — never to individuals.

## Published Items

| Category | Content | Cadence | Form |
|---|---|---|---|
| Code | All components incl. infra config | Realtime | Public Git repo (AGPL-3.0) |
| Algorithm parameters | Clustering thresholds, display thresholds, down-weight rules | On change (PR + 7-day notice) | Versioned config files |
| AI audit | Every draft's prompt, model version, raw output, validation result | Realtime | audit_log open endpoint |
| Card decisions | State changes, quality score, vote count, spectrum coverage | Realtime | audit_log |
| Operating costs | Itemized expenses, cost per card | Monthly | Dashboard + open data |
| Funding sources | Donation totals & distribution, B2B customer list, grant details | Monthly | Same |
| Maintainer hours | Time-investment log | Monthly | Dashboard |
| Official-account posts | All automated publications with generation basis | Realtime | Posting-log endpoint |
| Appeal statistics | Case volume, upheld rate, processing time (de-identified) | Quarterly | Report |
| Coordination statistics | Pattern-level descriptions of vote-stuffing events | Post-event | Report |

## Never-Published Items (hard constraints)

- Any individual-level data: vote-identity mappings, query-identity mappings, IPs, source-platform identifiers
- Contributor stance vectors (engine-internal only)
- Appellant identities
- Identifiable information of accounts involved in vote-stuffing events — **patterns only, never people** (example: "a card received 340 votes within 2 hours, 82% from handles registered under 7 days")

## Dashboard Specification (public page)

Blocks: today's cluster count / query volume / arbitration volume; spectrum diversity metric; monthly finance (income distribution pie, expense detail, cost per card); top-queried clusters; strong-signal low-arbitration clusters (arbitration recruitment CTA); system health (API latency, quota headroom). Every figure links to its open-data download.

## Exceptions

- Security hotfixes: deploy first, full disclosure within 72 hours
- Legally compelled data demands: transparency report discloses request counts and types received (warrant-canary mechanism evaluated in doc 13)

## Automated Weekly Report (feeds doc 15)

The "Firefly Weekly" is system-generated: weekly cluster count, the largest synchronized-posting event's timing chart, arbitration participation stats — data as content; generation rules open source; publications enter the posting log.

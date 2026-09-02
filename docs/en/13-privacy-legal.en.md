# 13 | Privacy & Legal Compliance Assessment

> Firefly (螢火) | v0.1 | 2026-07-20 | AGPL-3.0
> This is an engineering risk map, not legal advice. Schedule professional legal review before launch and again before joining a fiscal host (budgeted in doc 11).

## Personal Data (Taiwan PDPA / GDPR)

| Design fact | Compliance effect |
|---|---|
| No IP stored (24h abuse-window rolling deletion), no nationality, no real identity, platform IDs one-way hashed | Personal-data surface near zero; nothing individual-level exists to hand over on demand or leak |
| Literacy diary purely on-device, login-free | Sensitive inferential data (reading tendencies) never lands on servers |
| Passive reading tracking prohibited (even anonymized) | Avoids the entire "anonymous behavioral data is re-identifiable" risk class |
| Named contributors: self-chosen nickname + login credential only | Purpose-bound, minimized; self-service deletion provided |
| Open data k-anonymized | Research releases do not constitute personal-data disclosure |

To do: privacy policy (bilingual), GDPR representative-obligation assessment (if EU user threshold reached), lightweight DPIA.

## Content (Defamation / Reputation Risk)

- The core defense is the product design itself: cards state verifiable facts only (times, counts, links) with no characterization ("manipulation / fake account / cyber troop") — factual statements carry a truth defense; characterizations are the high-risk defamation zone
- Handle display: showing public platform handles is restatement of public information; a masking-appeal channel still exists (doc 09)
- The AI output guardrails (doc 04 whitelist + post-validation) double as legal guardrails: intent attribution is systematically excluded
- Residual risk: clustering errors associating innocent accounts → re-review queue at top priority + public correction records

## Platform Terms

| Platform | Dependency | Risk & response |
|---|---|---|
| Threads API | mentions/replies/publishing | Quotas and policy at Meta's discretion; feature-flag kill switch; complete review materials; never scrape beyond the API |
| LINE Messaging API | Full bot functionality | Terms stable; reply-mode compliant; raw userId never stored |
| Snapshot fetching | Public web | Public content only, robots and rate etiquette respected; Wayback primary evidence store, own snapshots secondary |

## Government Data Demands

- Minimized deliverable surface is the first defense (see above)
- Transparency report: quarterly disclosure of demand counts and types
- Warrant canary: adopt after evaluation — a standing dashboard statement "no data demands under gag order received this quarter"; its disappearance is the signal. Legal effectiveness varies by jurisdiction; on the counsel checklist
- Cross-border deployers (AGPL forks) bear their own local compliance; stated in README

## Operator Personal Protection

- Named operation (a transparency requirement) carries personal risk: harassment, vexatious litigation, cross-border pressure
- Responses: legal-insurance evaluation, incorporation timing (linked to doc 11 Phase 1), litigation reserve as a budget line, emergency-shutdown and data-preservation runbook (doc 14)

# 11 | Operating Costs & Funding Model

> Firefly (螢火) | v0.1 | 2026-07-20 | AGPL-3.0

## Cost Structure (monthly estimate, MVP stage)

| Item | Estimate | Notes |
|---|---|---|
| VPS (single machine incl. DB) | NT$800–2,000 | 4–8 GB RAM class |
| LLM drafting | NT$300–1,500 | Amortized: billed by cluster count, not posts/queries |
| Embedding compute | ~NT$100 | Self-hosted small model, CPU-viable |
| Domain/certs/backup | NT$300 | |
| LINE official account | NT$0–800 | Replies free; push queue volume small |
| **Cash subtotal** | **NT$1,500–4,700** | |
| Maintainer time | The largest cost | Presented as transparent hour logs on the dashboard |

Conclusion: cash costs sit within small-donation range; what the funding model must actually solve is the **sustainability of maintainer time**.

## Three Revenue Layers

### Layer 1: Small donations + open ledger (live at launch; phased dual-track)
- **Phase 0**: ECPay/NewebPay recurring donations embedded on our own site (cards ~2–2.75%/txn, NTD, no monthly fee; enable auto-withdrawal to avoid dormant-account management fees). Ko-fi (0% platform fee) as the overseas-donor side door. Buy Me a Coffee not adopted (5% platform fee + USD FX loss; poor fit for a Taiwan-donor majority)
- **Phase 1 (at scale)**: move under a fiscal host (e.g. Open Culture Foundation, ~10% admin fee) — buying compliance (charitable-solicitation law), donation receipts (needed by corporate/large donors), and neutrality optics (funds enter a foundation account, not a personal one). Transition thresholds and timing published on the dashboard; consult nonprofit counsel before switching
- Ledger transparency never depends on the platform: whatever the payment rail, the public ledger is our own finance_record open data
- Tangible specificity: dashboard shows "N cards this month / cost X / shared by M donors / cost per card" in real time
- Sponsorship: donors may sponsor specific clusters' verification cost (shown on card pages, nickname only)
- Single-funder cap: no source may exceed 30% of annual revenue; approaching the cap triggers public notice and suspension of acceptance

### Layer 2: B2B API (Phase 2)
- Customers: newsrooms, fact-checking orgs, brand safety (advertisers avoiding farm domains)
- What's sold: quota, SLA, push — **never data exclusivity** (open data available to all; neutrality preserved)
- Pricing: tiered subscription; customer list is public (customers must consent to this term in advance; no consent, no deal)
- Refusals: political parties, campaign organizations, government tenders — regardless of country

### Layer 3: Grants (optional)
- Acceptable: civic-tech awards (e.g. g0v grants), open-source foundations, academic collaborations
- Full disclosure: amounts, conditions, timelines public; accompanied by a "funder has zero influence on product decisions" statement
- Government and foreign political funding: declined by default; exceptional cases require public deliberation via governance

## Sustainable Path for Maintainer Time

1. Phase 0 (now): side project; hours logged transparently
2. Phase 1: donations reach NT$30,000/month → one fixed day per week
3. Phase 2: stable B2B revenue → evaluate half/full-time; financial thresholds and decisions public
4. Principle: growth is met with automation before headcount; single-person operability is an architectural requirement (doc 03)

## Financial Transparency Format

- finance_record (doc 08) exported monthly as CSV/JSON to the open-data endpoint
- Quarterly summary card: "where our money came from and went," rendered in the same format as context cards — eating our own dog food

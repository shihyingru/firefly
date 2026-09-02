# 06 | API Specification

> Firefly (螢火) | v0.1 | 2026-07-20 | AGPL-3.0
> Base: `https://api.firefly.example/v1` (domain TBD) | HTTPS only | JSON

## Authentication

- Consumer: anonymous device handle (opaque token issued on first call; bound to no personal data)
- Contributor: device-handle upgrade (optionally named after accumulated votes); Bearer token
- B2B: API key; separate quotas and billing
- Internal entries (LINE/Threads bot servers): service token

## Consumer Endpoints

### POST /lookup
Look up a link; returns a context card or status.
```json
req: { "url": "https://www.threads.com/@user/post/xxx" }
res 200: { "card": {…}, "cluster_id": "cl_8f2", "status": "displayed|candidate|no_signal" }
res 202: { "status": "processing", "retry_after": 5 }   // new cluster drafting
res 422: { "status": "unfetchable" }                    // non-public/deleted
```

### GET /cards/{card_id}
Full card. Fields are exactly doc 04's whitelist: earliest_seen, original_source, account_count, timing_chart (data-point array), archive_links, domain_note, arbitration (i_c, vote_count, spectrum_coverage).

### POST /cards/{card_id}/votes
```json
req: { "helpful": true }
res: { "accepted": true }        // idempotent: same handle re-voting overwrites
```

### GET /queue?limit=5
Arbitration queue (contributor token required). Backend selects per spectrum-balancing strategy.

### POST /clusters/{id}/flags
Named contributors flag clustering errors or submit supplementary sources.

## B2B Endpoints (Phase 2)

- GET /signals/domains: domain signal list (with version, evidence links)
- GET /signals/clusters?since=: active cluster summary stream
- Everything on the consumer side is equally available to B2B; B2B pays for quota, SLA, and push — never data exclusivity (neutrality: data verifiable by anyone)

## Open Data Endpoints

- GET /open/cards.jsonl: all displayed cards (daily snapshot)
- GET /open/audit-log: card state changes and prompt audits
- GET /open/finance: operating income/expense (format defined in doc 12)

## General Rules

- Quotas: anonymous 60 req/hr; contributor 300; B2B per contract. 429 includes Retry-After
- Versioning: URL-versioned; breaking changes announced 90 days ahead
- Error format: `{ "error": { "code": "...", "message_zh": "...", "message_en": "..." } }`
- CORS open for GET open-data endpoints; write endpoints restricted to allow-listed origins

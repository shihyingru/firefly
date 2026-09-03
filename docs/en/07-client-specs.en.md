# 07 | Client Technical Specifications

> Firefly (螢火) | v0.1 | 2026-07-20 | AGPL-3.0

## 7.1 LINE Bot (Wave 1)

- LINE Messaging API; webhook served by the main backend (FastAPI route)
- Message handling: text containing a URL → extract & normalize → call /lookup; forwarded messages likewise
- Card rendering: two-part Flex Message — summary bubble (source/time/account count) + button row (helpful/not-helpful postback, "view full card" URI)
- Voting: postback event carries card_id; server uses a one-way hash of the LINE userId as the contributor handle (no raw-userId mapping table stored); the hash is HMAC-SHA256 with a server secret in an environment variable, rotated via runbook
- Always reply via reply token (free); never proactive push (zero cost, zero annoyance)
- When /lookup returns 202 (drafting): reply a "processing" message via the reply token with a "check again" button (postback carrying the original URL). No push, no waiting
- "Today's queue": rich-menu postback `queue:today`, answered via reply with 5 cards (zero storage)
- Onboarding push (D-014): on day 0 the follow reply carries the queue and an invitation; consenting users receive 5 cards by push daily for N days (initially 3), the last push carrying self-serve instructions; this is the only push scenario, governed by a daily cap and a feature flag

## 7.2 Threads Reply Bot (Wave 1, technical-validation item)

- Official account: @firefly_tw (to register); bio states "automated reply bot | open source | posting log public"
- Trigger: webhook preferred (mention events — **verify availability before launch**); fallback polling of keyword/mention queries every 5 minutes
- Reply assembly: summary text (<500 chars) + card page link; repeated triggers on the same cluster return the existing link
- Quota governance: daily reply counter with 20% headroom; over quota → link-only replies, no new card generation
- Kill switch: feature flag for global disable (one-click offline on Meta policy changes; other entries unaffected)
- App Review materials: use-case description, privacy policy link, demo video — on the launch checklist

## 7.3 Mobile Share Target (Wave 2)

### Android
- Kotlin + Compose; `ACTION_SEND` (text/plain) intent-filter
- On share → parse URL → bottom sheet showing card (Compose) + voting
- Contributor handle: device-generated UUID in EncryptedSharedPreferences
- Offline: show last cached card; query history local only (Room)
- Arbiter-queue notification: WorkManager once daily; can be disabled in settings

### iOS
- Swift; Share Extension (NSExtensionActivationSupportsWebURLWithMaxCount=1)
- Lightweight card view inside the extension; full features in the main app (SwiftUI)
- Shares the API client spec with Android (OpenAPI-generated)

## 7.4 Arbiter Queue (Late Wave 2)

- Form: a tab inside the mobile app (not a separate app)
- Gestures: swipe right = helpful / left = not helpful / up = skip; 5 cards daily; completion shows contribution-day streak
- No leaderboards, no badge store — avoids volume incentives distorting arbitration quality

## 7.5 Browser Extension (later; placeholder)

- WebExtension (Chrome/Firefox); DOM-injected card indicators on Threads web
- High selector-maintenance cost; deferred; separate spec at kickoff

## Common

- API clients generated from the OpenAPI schema (Kotlin/Swift/TypeScript)
- No client collects anything beyond the device handle; no third-party analytics SDKs
- UI copy in bilingual resource files; tone follows doc 02

# 02 | User Journeys & UX Flows

> Firefly (螢火) | v0.1 | 2026-07-20 | AGPL-3.0

## User Roles

| Role | Description | Core flow |
|---|---|---|
| Querier | Scrolled past a suspicious post, wants quick context | Drop link → read context card |
| Arbiter | Willing to spend 3 min/day voting | Read card → one-tap vote |
| Bystander | Sees the bot's public replies on Threads | Sees card → curious → converts to querier |

Design principles: every role's next step is always exactly one action; queriers never register; arbiters participate under anonymous device handles and may optionally upgrade to named contributors.

## Entry 1: LINE Bot (Wave 1)

1. User adds the official account (QR / ID search)
2. Pastes a post link or forwards a message
3. Bot replies with a context card (Flex Message): original source, first-seen time, same-content account count, snapshot links
4. Two buttons at card bottom: "Helpful" / "Not helpful" (postback, stays in chat)
5. After voting: thanks. On the day of following, the user already receives today's queue and a "send me the queue daily for three days" invitation; afterwards the rich-menu "today's queue" serves it on demand (D-014)

When no card can be generated (cluster not formed, non-public link): reply "no coordination signals found" + a generic literacy tip. Never reply with nothing.

## Entry 2: Threads Reply Bot (Wave 1, technical-validation item)

1. User replies "@firefly_tw" (or trigger phrase) under any post
2. Server receives the mention via webhook or polling; fetches the parent post
3. Official account publicly replies with a card summary + full-card link
4. Voting happens on the card page (no interactive elements inside Threads replies)

Quota discipline: prioritize clusters not yet replied to; repeat queries on the same cluster get the existing card link, no regeneration.

## Entry 3: Mobile Share Target (Wave 2)

- Android: system share sheet → Firefly → bottom sheet with card + voting
- iOS: Share Extension → same layout
- Query history stays on-device; optional "arbiter queue" notifications

## Entry 4: Arbiter Queue (Late Wave 2)

- Daily push of 5 cards awaiting arbitration; swipe right = helpful, left = not helpful, up = skip
- Done in three minutes; streak shows contribution days (no leaderboards — avoids volume-chasing culture)
- Queue composition assigned by backend per spectrum-balancing needs (doc 05)

## Conversion Funnel

Bystander → querier: the Threads bot's public replies are the acquisition channel
Querier → arbiter: a single light question after each query ("Was this card helpful?" is itself the first vote)
Arbiter → named contributor: invited after N valid votes (unlocks submitting supplementary sources)

## Copy & Tone Rules

- Ask, don't assert: "Did you notice these 32 accounts posted within the same hour?" — never "This content is suspicious"
- Never use verdict words like "fake news" or "debunk"; always "context", "signals", "evidence"
- When no signals found, say so plainly — imply neither safety nor danger

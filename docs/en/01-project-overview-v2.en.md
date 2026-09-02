# Project Overview (One-Pager)

> Project name: (TBD)
> Version: v0.2 draft | 2026-07-20 | Status: pending confirmation
> License: AGPL-3.0

## Problem

We are entering an era of unlimited content supply and limited judgment time. Coordinated fake-account networks, AI-mass-produced posts and videos, and AI-driven scams are filling everyone's feeds faster than human fact-checking can ever keep up. Research by Doublethink Lab gives this a concrete scale: a single operation ran 549 fake accounts and 1,217 domains on Threads, publishing over 460,000 posts — building trust and traffic with everyday lifestyle content, ready to pivot to political or commercial manipulation at any moment.

Existing countermeasures each have a gap: professional fact-checking has limited throughput and never reaches users mid-scroll; crowdsourced fact-checking has a high contribution barrier and declining participation; platform-native mechanisms (e.g. Meta's Community Notes) have not reached Taiwan and have no announced timeline. More fundamentally, most solutions judge *for* users instead of growing users' own capacity to judge.

## Vision

Help everyone's media literacy evolve as fast as content-generation technology does.

Taiwan is the first deployment ground (a mature civic-tech tradition plus a high-intensity information-manipulation environment), but the architecture is designed from day one to be cross-language and cross-border — deployable in any society facing coordinated inauthentic behavior and AI-enabled scams. The long-term goal is not to build an authority on truth, but to cultivate a generation-wide habit loop: observe → judge → think carefully.

## Core Idea

**AI is the clerk; humans are the arbiters.**

- AI does all the heavy lifting: detecting coordination fingerprints (formatting formulas, domain matching, synchronized posting patterns), collapsing hundreds of thousands of posts into a small number of "claim clusters" via semantic clustering, and drafting one "context card" per cluster.
- Context cards may contain **machine-verifiable fields only**: original source, first-seen timestamp, number of accounts posting identical content, archive snapshot links. The AI writes no opinionated inference.
- Humans do exactly one thing: read the card, tap "helpful / not helpful."
- A **bridging scoring engine** filters echo-chamber noise: a card is displayed only when users across the opinion spectrum find it helpful — single-camp vote-stuffing is mathematically silenced.

One arbitration covers every reincarnation of a claim across the whole cluster. This is leverage that purely human collaboration can never reach.

## What We Do NOT Do

- We do not rule on truth or falsehood, and we make no stance-based commentary — we only make invisible coordinated behavior visible
- We do not label content by political stance; we label coordinated inauthentic behavior (the CIB framework)
- We belong to no existing community or political camp — independent brand, open-source governance, verifiable neutrality

## Product Form (Low-Friction, Multi-Entry)

1. **Mobile share target** (Android Share Target + iOS Share Extension) — long-press share on any suspicious post to check it. Fully self-controlled, zero platform-approval dependency.
2. **Threads reply bot** — @-mention the official account under a post to receive a context card in reply. Replies are public, so every answer is also reach. (Depends on Meta API review and quotas; flagged as a technical-validation item.)
3. **LINE bot** — paste a link, get a context card in seconds, vote directly on the card. Zero install; usable by elders.
4. **Arbiter queue** — a three-minute daily ritual of 5 cards awaiting arbitration; swipe left/right, done.
5. **Browser extension** (later phase) — automatic inline embedding for web flows.

All entries share one backend and one voting dataset. Query-only mode launches first; queriers naturally convert into arbiters, solving the cold start.

## Neutrality and Transparency (Where Trust Comes From)

- Algorithms and data fully open source (AGPL-3.0); anyone can re-run and verify
- A governance charter defines inclusion criteria, an appeal/removal process, and cross-spectrum contributor composition targets
- An operations transparency dashboard: real-time costs, funding sources, and posting logs all published as open data

## Operating Model (Three Layers)

1. Small donations + open ledger (tangible specificity: "N cards this month, cost X, shared by M donors")
2. B2B API (newsrooms, fact-checking orgs, brand safety) — the consumer side stays free forever
3. Grants (civic-tech awards, open-source foundations) — full disclosure, with a cap on any single funder's share

## Success Signals (Phase 1)

- MVP entries live; context-card query volume and query→arbitration conversion rate
- Contributor spectrum diversity reaches the operational threshold for the bridging algorithm
- At least one real coordinated-manipulation cluster detected, arbitrated, and published by the system

## Deliverables and Next Steps

This document is the first of a 15-document set (Traditional Chinese / English dual versions) and anchors the core decisions for all subsequent technical, data, governance, legal, and marketing documents.

---

## Appendix: Glossary

| Term | Plain-language explanation | Reference |
|---|---|---|
| Semantic clustering / claim cluster | AI automatically groups posts that "say the same thing" (even with different wording). One group = one claim cluster; one arbitration covers the whole group. | — |
| Coordinated Inauthentic Behavior (CIB) | The standard is the behavior itself — a group of accounts acting in concert while pretending to be unrelated — not the content's stance. Meta uses this framework to take down manipulation networks. | [Meta threat reporting](https://transparency.meta.com/metasecurity/threat-reporting) |
| Coordination fingerprints | Technical traces revealing links between accounts: identical formatting formulas, shared domains, synchronized posting times, shared source code. | [Doublethink Lab](https://doublethinklab.org) |
| Bridging algorithm | Instead of counting "how many agree," it surfaces content that people who usually disagree both find helpful. A thousand aligned votes from one camp mathematically collapse toward one. | [Research paper](https://arxiv.org/abs/2210.15723) |
| Community Notes | X (Twitter)'s community annotation system — the largest real-world deployment of a bridging algorithm; code is open source. | [Guide](https://communitynotes.x.com/guide) | [Source](https://github.com/twitter/communitynotes) |
| Polis | An opinion-clustering and consensus-discovery platform; a pioneer of the bridging concept, used by Taiwan's vTaiwan for public policy deliberation. | [Polis](https://pol.is) | [vTaiwan](https://vtaiwan.tw) |
| Cold start | The failure mode where a collaborative system can't function early on because there aren't enough participants. This project routes around it with query-only-first: the tool is unilaterally useful before collaboration grows. | — |
| Sybil attack | One actor controlling many fake accounts to fake majority opinion. Bridging algorithms are naturally resistant: behaviorally identical accounts compress into a single stance vector. | — |
| Archive snapshot | A third-party timestamped copy of a web page, preserving evidence even if the original is deleted. | [Wayback Machine](https://web.archive.org) |
| AGPL-3.0 | An open-source license requiring that any network service built on this project also be open-sourced — preventing closed, opaque partisan forks. | [License](https://www.gnu.org/licenses/agpl-3.0.html) |
| Cofacts | Taiwan g0v community's crowdsourced fact-checking system; pioneer of the LINE forward-to-check pattern. | [Cofacts](https://cofacts.g0v.tw) |

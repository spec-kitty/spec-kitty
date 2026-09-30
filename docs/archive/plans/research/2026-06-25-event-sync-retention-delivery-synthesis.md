---
title: Event sync — separating retention from delivery (research synthesis)
description: Design synthesis for the event-sync mission (issue 2124) — separating local event retention from per-target delivery state across the journal, ledger, and dispatcher.
doc_status: superseded
updated: '2026-09-06'
---

> **Superseded (2026-09-06, Convergence #3881).** This synthesis was built on the retired
> event-sync / journal / delivery stack, which the convergence removed wholesale. Kept as a
> historical design record; the carried-forward behaviors were logged upstream
> (Priivacy-ai/spec-kitty-saas#1152, spec-kitty/zeitgeist#45).

# Research Notes: Event sync — separating retention from delivery

**Status:** Design input for `/spec-kitty.tasks`; decisions settled for this mission below
**Owner:** Lynn Cole (design), with Robert Douglass (proposal) and Stijn (feedback)
**Last updated:** 2026-06-28
**Primary issue:** https://github.com/Priivacy-ai/spec-kitty/issues/2124
**Related issues:** https://github.com/Priivacy-ai/spec-kitty/issues/2146, https://github.com/Priivacy-ai/spec-kitty/issues/2144, https://github.com/Priivacy-ai/spec-kitty/issues/1800, https://github.com/Priivacy-ai/spec-kitty/issues/1666, https://github.com/Priivacy-ai/spec-kitty/issues/1619, https://github.com/Priivacy-ai/spec-kitty/issues/2165

---

## Issue topology and sequencing

This note now feeds the #2131 mission package, not a standalone build spec. It
sits in the SaaS sync durability cluster:

- **#2146 — sync target authority**: folded into #2131 as the first concern.
  It decides which value owns runtime target selection and proves queue scope,
  auth/readiness, WebSocket, tracker, status, and network calls cannot diverge.
- **#2124 — retained event journal + per-target ledger**: this note's primary
  design spike.
- **#2144 — Teamspace durability registry + git/SaaS replay**: sibling/follow-on,
  but its capture-before-drain invariant applies here: feature flags, auth/team
  gaps, and network gates must block drain eligibility only, not silently drop
  Teamspace-bound facts.
- **#1800 / #1666 / #1619**: parent sync/event-envelope hardening and execution
  context/domain-boundary architecture.
- **#2165**: docs-layout reorganization context only. This mission keeps its
  artifacts in the current `architecture/3.x/research/` and `kitty-specs/`
  locations; no docs tree reshuffle is part of the work.

Planning order inside #2131: **target authority (#2146) -> journal/ledger
(#2124) -> capture/replay compatibility with #2144**.

## Why this exists

The CLI's local sync queue is a destructive outbound queue: on a terminal
success from a SaaS endpoint the local row is deleted (`process_batch_results`,
`src/specify_cli/sync/queue.py:1693`). That is fine for one durable production
target. It is wrong for transient SaaS test environments (Upsun PR envs), where
the operator wants to drain the same local events to env A, destroy it, and
drain the same events again to env B.

Robert opened #2124 to fix this at the CLI level before Teamspace is exposed to
users. Stijn added the operator-config framing and a hard requirement on module
boundaries. This note folds both into one design.

## The core move (Robert): separate retention from delivery

Today, one concept does two jobs: the queue row is both *the event payload* and
*the delivery state*. Split them:

- **Event journal** — append-only local record of event payloads. Does not know
  whether an event was ever sent anywhere.
- **Delivery target registry** — target identity (canonical URL + user/team
  scope, plus optional server-advertised deployment metadata).
- **Delivery ledger** — per-event/per-target state: was event X sent to target
  Y, when, with what result?
- **Dispatcher** — selects journal events lacking terminal successful delivery
  for the active target, posts, updates the ledger. Never deletes source events.
- **Retention / GC** — explicit operator action only.

A successful upload becomes a *ledger update*, not event destruction.

## The operator surface (Stijn): `EventSyncConfig` is the same split, from the top

Stijn's `EventSyncConfig` (`LOCAL_RETENTION` / `EXTERNAL_RECEIVER` / `TEAMSPACE`
/ `OPT_OUT`/`TRASH`) is not a competing proposal — it is the operator-facing dial
for exactly the retention-vs-delivery separation above. Under the hood it resolves
to **two orthogonal axes**:

- **Retention** (the journal): on = keep payloads locally · off = discard
- **Delivery** (the target + ledger): none · Teamspace · external-receiver

The four named modes are the useful presets over those axes:

| Mode | Retention | Delivery |
|---|---|---|
| `TEAMSPACE` | journal on | → SaaS Teamspace target (default for connected users) |
| `EXTERNAL_RECEIVER` | journal on | → operator-configured endpoint (just another target type) |
| `LOCAL_RETENTION` | journal on | none — retain now, choose a target and drain later (the replay case) |
| `OPT_OUT` / `TRASH` | off | none |

Modeling it as two axes (not a flat enum) keeps Robert's separation honest and
leaves room for presets to grow without reshaping the core.

### Target-authority prerequisite (#2146)

`EventSyncConfig` must sit behind one target-authority rule, not become another
source of truth. Before event migration or delivery implementation, #2131 must
settle this matrix:

| Surface | Required decision before implementation |
|---|---|
| `EventSyncConfig` | Selects retention/delivery policy only; does not independently choose a network target. |
| `SyncConfig.server_url` / `config.toml` | Canonical runtime target unless an explicit whole-process override is active. |
| `SPEC_KITTY_SAAS_URL` | Either setup/dev-only, or a deliberate override that affects auth, sync, tracker, queue scope, WebSocket, readiness, and diagnostics consistently. |
| `SPEC_KITTY_ENABLE_SAAS_SYNC` | Affects drain eligibility only; Teamspace-bound capture still lands in SQLite or git. |
| Auth session + team scope | Supplies identity for delivery target and ledger rows when known; not required for initial local capture. |
| Queue scope | Derived isolation key, not an independent target selector. |
| Network calls | Must use the same resolved target as queue scope and status diagnostics. |

Acceptance for this prerequisite: env/config disagreement cannot create a queue
scope for one target while network calls go to another, and stale
`active_queue_scope` is reported as stale/non-authoritative.

### The testing stub falls out for free

Stijn wants a stub receiver so fork CI stops depending on a real Teamspace and
the `teamspace_key` in core that keeps breaking his runs. A stub is just an
`EXTERNAL_RECEIVER` pointed at a localhost sink that accepts and records events
for assertions. It is a configuration of the design, not a special case — and it
gets CI off the Teamspace dependency.

## Module boundary (Stijn's hard requirement)

Stijn requires this be modeled as a **separate domain in core**, to avoid the
spaghetti trap from 2.x. The current `queue.py` is 1,861 lines; an honest
append-only journal and safe coalescing are not achievable inside it. Proposed
boundary, mapping 1:1 to Robert's components:

- `event_journal/` — the journal (append-only payload store).
- `delivery/` — target registry + ledger + dispatcher.
- `EventSyncConfig` — the policy layer that selects retention × delivery target.

Do not name the new journal package `events/`. `src/specify_cli/events/` already
owns event-log integration, sanitizer, and decision-log surfaces; reusing that
package for the journal would collapse two bounded contexts.

## Code-level sharpening points (from the #2124 review)

1. **The migration depends on #2146's target-authority decision.** The queue DB is keyed
   `server|user|team` (`build_queue_scope`, `queue.py:391`), so events produced
   against env A live only in A's DB. The journal must become
   **target-independent** — scoped to producer (`user|team` / repo-local) — with
   the server URL moving out to the target registry. Migration consolidates
   possibly-several per-server DBs into one journal and backfills ledger rows.
   Honest limit: events already delivered-and-deleted are gone; migration can
   only preserve *currently-queued* payloads. Same `event_id` with identical
   payload imports once with source provenance; same `event_id` with divergent
   payload is a migration conflict/quarantine, not overwrite, ignore, or ID
   rewrite.

2. **Coalescing vs append-only is the correctness trap.** Coalescing today
   *mutates* the existing row (`UPDATE event_type, data …`, `queue.py:1267`).
   Once an event has a terminal delivery to any target, mutating it makes the
   ledger lie. Rule: coalesce only among events with no terminal delivery to any
   target; after first delivery the event is immutable and a new event is a new
   row (mark the old superseded). This protects the audit honesty the feature
   exists for.

3. **Target identity = URL + scope; deployment metadata is provenance, not
   identity.** `UNIQUE(url_hash, team_slug, user_email)` is right. Upsun stamps a
   new `deployment_id` per push, so deployment identity must not fork the target —
   record it, and use a *change* in it to detect "same URL, env reset underneath
   us" and offer a re-drain. Reset-detection, not identity-forking.

4. **`/api/v1/sync/health/` deployment metadata is a SaaS cross-repo
   dependency.** Sequence it: ship the CLI with URL-only identity first (already
   correct for destroy-and-recreate, since a new env is a new URL), then SaaS
   exposes the metadata, then the CLI consumes it. Don't let the health work
   block the CLI work.

5. **Append-only grows until `sync gc`.** Safe default, but surface journal size
   in `sync status` and suggest GC once the journal is large *and* fully
   delivered to all known targets. "Explicit only" must not mean "silent
   unbounded."

One easing fact: `pending` / `rejected` / `failed_transient` handling already
matches the proposal (`queue.py:1666-1678`); only `success` / `duplicate` /
`failed_permanent` need to stop deleting and become ledger writes. The heavy
lifting is the journal/ledger split + the migration, not the dispatch logic.

## Settled decisions before `/spec-kitty.tasks`

1. **MVP delivery mode**: one operator-selected active target. Robert's
   fan-out lean on #2124 was considered, but the #2131 package chooses
   single-target for MVP because it matches the original non-goal and avoids
   partial-failure/ordering semantics. The ledger remains per-event/per-target
   so fan-out can be added later without a schema break.
2. **Target reset under stable URL**: advisory follow-on. URL+scope identity is
   enough for the immediate transient-env replay use case; consuming SaaS
   `/api/v1/sync/health/` deployment metadata waits for the SaaS-side change.
3. **Teamspace durability**: #2144 full registry/replay is follow-on, but
   #2131 must not introduce any silent discard of Teamspace-bound facts. Capture
   comes before drain gates.
4. **Docs structure**: #2165 is not folded into this mission. No docs-root move
   or frontmatter normalization is part of #2131.

## Next step

Run `/spec-kitty.tasks` from the revised #2131 spec/plan. Task generation must
preserve the concern order above and use the mission contract in
`kitty-specs/event-sync-retention-delivery-01KVYWRG/contracts/`.

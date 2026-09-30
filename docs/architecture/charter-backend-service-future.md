---
title: Charter Backend Service (Future — Backlog)
description: 'Preliminary backlog design for a separate charter/doctrine resolution process behind a stable API/MCP endpoint: remote compute, shared caching, out-of-cycle precompute. Backlog.'
doc_status: draft
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/architecture/profile-load-reliability.md
- docs/architecture/governed-profile-invocation.md
- docs/architecture/multi-agent-orchestration.md
---
# Charter Backend Service (Future — Backlog)

> **Scope:** **BACKLOG — not scheduled for 4.0.0** (design spike #3815 sits in the Product backlog; see the [4.0.0 roadmap](../plans/4-0-0-milestone-roadmap.md)). This is a *preliminary* design sketch
> for discussion, not committed work. The near-term stabilization that must land first
> (activation-data fix + orchestrator-injects contract + `/spk-load-profile`) is specified
> in [Profile-Load Reliability](profile-load-reliability.md) §4. This document describes
> the **evolution** that the orchestrator-injects contract deliberately makes possible.

## 1. Motivation

Today, charter/doctrine resolution runs **in-process, per invocation**, via the
`spec-kitty` CLI (`agent profile show`, `charter context`). That is correct for a single
orchestrator, but it couples every resolution to a local checkout and pays a cold-start +
environment-drift cost each call. A separate, long-lived **charter backend process** —
reached through a stable API and/or MCP endpoint — unlocks capabilities the in-process
model cannot offer:

- **Remote compute** — resolution runs where the doctrine corpus and compute live, not on
  every consumer's machine; thin clients (CI, IDE agents, headless/cron, other repos) call
  the same authority.
- **Shared caching** — a warm process caches compiled charters, DRG traversals, profile
  lineage, and action-scoped context across invocations and across consumers, instead of
  recompiling per CLI call.
- **Out-of-cycle context precomputation** — the backend can precompute and refresh
  action-scoped context and profile bundles *ahead of* a mission/squad run (on charter
  change, on a schedule), so dispatch reads a ready artifact rather than resolving on the
  critical path.

## 2. Design constraints (carried from the near-term work)

1. **Same resolution contract.** The backend sits behind the *identical* contract the
   orchestrator already uses in [Profile-Load Reliability](profile-load-reliability.md)
   §4.2 — request `(profile_id, action)` → resolved profile + compact context. Adopting
   it must not touch delegate prompts.
2. **Fail-loud, never fail-open.** Backend-down or profile-unresolved surfaces as a hard
   error at the orchestrator (substitute / activate / abort) — never a silently unprofiled
   delegate. This is the invariant Issue 1 violated.
3. **Overlays applied server-side.** Resolution must apply overlays, `specializes_from`
   lineage, and `enhances`/`overrides` — the raw-YAML fallback that skips these is not an
   acceptable backend response.
4. **Loopback-only, read-only by default.** If exposed over HTTP, bind to `127.0.0.1`
   read-only (consistent with the repo's loopback-only control-plane policy); do not force
   HTTPS on an intentionally-loopback transport. Remote exposure is an explicit,
   authenticated opt-in, not the default.

## 3. Transport options (to evaluate, not yet decided)

| Option | Wins | New failure modes |
|---|---|---|
| **Local daemon + API** (precedent: the retired sync daemon, `core/loopback_http.py`, `auth/loopback/callback_server.py`) | Warm authority; kills cold-start + install/PYTHONPATH drift; one source of truth across harnesses | Daemon lifecycle (start/stop/ports); staleness on charter change (needs reload/invalidation); availability dependency; real-port tests must run serially |
| **MCP endpoint** | Directly serves shell-less harnesses (tool result → context, no shell); uniform across MCP-capable agents | "Interactively-authenticated MCP servers may be absent in headless/cron" — trades the shell-less gap for an absent-in-headless gap |
| **Remote service** | Remote compute; shared cache across machines/repos; centrally-refreshed doctrine for a multi-repo program | Network dependency; auth/tenancy; cache-coherence; larger security surface |

A likely path is **local daemon first** (behind the §2 contract), with MCP and remote
exposure as later transports over the same core — but this is open for design review.

## 4. Open questions

- **Cache invalidation** — how does the backend detect charter/pack/DRG changes and
  invalidate compiled artifacts without serving stale doctrine?
- **Consistency vs. freshness** — for a long squad run, does a delegate get a pinned
  snapshot (deterministic) or the latest (fresh)? The near-term design pins at dispatch;
  the backend should keep that default.
- **Authority reconciliation** — the canonical "squad-eligible profiles" query is
  **authored in charter data near-term** ([Profile-Load Reliability](profile-load-reliability.md)
  §4.2 / §6 D4); the only backlog-open question is whether the backend later **exposes** it as
  an endpoint. This is the seam gap from Profile-Load Reliability §2.4, promoted to a
  first-class API concern.
- **Degradation** — precise behavior when the backend is unreachable: the orchestrator
  falls back to in-process CLI resolution (same contract) and never to unprofiled dispatch.
- **Relationship to `orchestrator-api`** — does this reuse or extend the existing external
  orchestrator-api surface, or stand alone?

## 5. Non-goals

- Not a replacement for the in-process CLI resolution path — that remains the default and
  the degradation target.
- Not a prerequisite for fixing squad profile loading — the near-term design stands alone.
- Not scheduled for 4.0.0.

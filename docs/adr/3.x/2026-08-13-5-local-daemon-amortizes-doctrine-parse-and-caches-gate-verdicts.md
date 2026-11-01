---
title: 'ADR: A local loopback daemon amortizes doctrine parse and caches deterministic gate verdicts (direction)'
description: 'Direction-setting ADR: a local loopback daemon holds parsed doctrine and a content-hash-keyed verdict cache, making gate execution a warm API call rather than a cold subprocess.'
status: Proposed
date: '2026-08-13'
related:
- docs/architecture/mission-gates.md
- docs/adr/3.x/2026-08-13-2-gates-are-declarative-asset-backed-doctrine-artefacts.md
doc_status: active
kind: ADR
updated: '2026-08-13T00:00:00Z'
---
# A local loopback daemon amortizes doctrine parse and caches deterministic gate verdicts

**Filename:** `2026-08-13-5-local-daemon-amortizes-doctrine-parse-and-caches-gate-verdicts.md`

**Status:** Proposed (direction-setting; not a prerequisite for the gate work)

**Date:** 2026-08-13

**Deciders:** Operator (ATDD)

**Technical Story:** Records a direction surfaced while designing declarative gates
([ADR 2026-08-13-2](2026-08-13-2-gates-are-declarative-asset-backed-doctrine-artefacts.md)).
Captured now so the gate design is daemon-ready, but scoped as a follow-on.

---

## Post-dialectics revision (2026-08-13) — DECISION HELD OPEN

Per operator: **this decision is held open for further discussion**; the rest of the gate
architecture proceeds without it. Recorded from the dialectics pass
(`work/gate-design-dialectics/04-...`, `99-COHERENCE.md`), not yet settled:

- **The verdict cache keyed on pack content-hash is contested as unsound.** The pack hash omits
  the **working tree**, which is the dominant input of both the incumbent `spec-kitty-pre-review`
  gate (scoped tests at head) and the `docs-structural-lint` example (lints the tree). Editing a
  tracked file leaves the pack hash unchanged → a stale **PASS** could cross a blocking gate.
  Capturing "everything a subprocess reads" is not feasible without tracing infra that dwarfs the
  daemon.
- **Parse-amortization is sound and daemon-independent** — the parse is a pure function of pack
  bytes and can be a content-addressed on-disk cache with no daemon.
- No decision is folded here yet. The daemon-as-warm-API and the verdict-cache question remain
  **open** pending further discussion.

## Context and Problem Statement

The CLI parses doctrine + DRG (and, with declarative gates, gate definitions) on **every
invocation**. Adding gate execution compounds that per-invocation cost. But gates are
**deterministic and side-effect-free**, which makes their verdicts **cacheable**.

There is precedent for a resident local process: the dashboard daemon
(`.kittify/.dashboard`) and the `orchestrator-api` external surface already exist, and the
project's loopback-only HTTP posture (127.0.0.1, no forced TLS) is the established security
model for such a surface.

## Decision Drivers

- Amortize doctrine/DRG/gate parse across invocations.
- Exploit gate determinism: identical inputs ⇒ identical verdict ⇒ cache hit.
- Do not couple the gate design to a daemon that does not exist yet.

## Decision Outcome

**Direction (not yet a committed build):** a **local, loopback-only daemon** may host doctrine
resolution and gate execution behind an API. It holds:

- **Parsed doctrine / DRG**, loaded once and reused across calls.
- **A deterministic gate-verdict cache**, keyed on `(gate id, gate/pack version, hash of the
  inputs the gate reads)`. The **pack `pack-meta.yaml` content-hash** is the natural
  invalidation key — the same hash that is signed for trust (ADR 2026-08-13-4). Three
  concerns converge on one hash: **integrity (signature), identity (version), and cache-key**.

Gate execution then becomes a warm API call; a cold CLI subprocess remains the fallback and
the v1 path. **The gate design (ADRs -2/-3/-4) must stand on its own without the daemon** —
the daemon is an optimization, not a dependency.

### Consequences

#### Positive

- Repeated transitions collapse to cache hits; parse cost is paid once.
- Reuses existing loopback-daemon precedent and security posture.

#### Negative

- A daemon that executes shipped code is a **persistent execution surface** with a real
  lifecycle (start/stop/staleness) and security story — deserves its own ADR + threat model
  before it is built.
- Cache correctness depends entirely on the input-hash being complete; a gate that reads an
  un-hashed input would return a stale verdict.

#### Neutral

- Whether this extends the existing dashboard daemon or is a new process is unresolved.

### Open questions (for the dialectics squad)

1. Extend the dashboard daemon, or a separate gate/doctrine daemon?
2. How is "the inputs the gate reads" captured completely enough to be a safe cache key?
3. Is verdict caching even worth it before the daemon exists (cold CLI has no persistent cache)?

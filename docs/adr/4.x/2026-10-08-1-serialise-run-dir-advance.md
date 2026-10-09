---
title: 'ADR: advancing a mission run is serialised by a per-run-dir lock and a caller-step compare-and-swap'
description: 'Concurrent `spec-kitty next` on one run is serialised: a stale advance is refused with a named `blocked` reason, and at most one writer mutates a run cursor at a time.'
status: Accepted
date: '2026-10-08'
---

**Status:** Accepted

**Date:** 2026-10-08

**Deciders:** Stijn Dejongh (owner), via the governed mission `serialise-next-advance-01M4EF16`.

**Technical Story:** [#5854](https://github.com/spec-kitty/spec-kitty/issues/5854) (P2, epic [#3897](https://github.com/spec-kitty/spec-kitty/issues/3897)) and [#5682](https://github.com/spec-kitty/spec-kitty/issues/5682) (P1). Reuses the `next` contract fixed by ADR [2026-02-17-1](../2.x/2026-02-17-1-canonical-next-command-runtime-loop.md) and follows the lock pattern the run-INDEX lock established (`src/runtime/next/run_index.py`, #5389/#5390, which shipped without an ADR of its own).

**Reader:** a maintainer who needs to know why a per-run-directory lock and a caller-evaluated-step compare-and-swap guard the `next` advance, which writers they cover, and why a contended or stale advance surfaces as `blocked`.

---

## Context and Problem Statement

`spec-kitty next` advances a mission run by reading the run cursor (`state.json`'s `issued_step_id`), evaluating gates against it, then committing the advance. The documented multi-agent loop runs several agents on one mission in parallel, and one agent may retry a slow call — so two advances overlap. Two defects followed, one cause in two layers:

1. **The advance never recorded which step its caller evaluated.** The bridge read `issued_step_id` once at bootstrap, but `plan_advance` re-read `state.json` and `commit_advance`'s stale check compared only that *second* read against `plan.source`. A peer advance that landed between the bootstrap read and `plan_advance`'s read was invisible, so the caller completed a step it never evaluated — a review step marked done while the WP sat in `for_review`, the loop reporting `terminal` (#5682). The same window hit both the composition and engine advance paths.
2. **No mutual exclusion covered the read→modify→write of a run cursor.** `commit_advance` was a compare-then-write TOCTOU; `_write_snapshot` staged through a fixed `state.json.tmp` that two writers collided on; `provide_decision_answer` was a third unguarded writer. On a stale plan the engine path re-planned through `next_step` and re-applied `success`, double-completing a step (#5854), while the composition path already refused.

The single-writer assumption was stated only in a code comment. Nothing enforced it.

## Considered Options

Recorded in the mission's `research.md` (pre-spec and post-spec adversarial squads). The chosen shape is the synthesis.

1. **Hold one lock across the whole advance (bootstrap read → commit).** Rejected: the composition advance runs step-contract executors of unbounded duration, so the hold would breach the primitive's 10 s max-hold default and risk the 60 s stale-reclaim. The architect lens rejected it.
2. **A compare-and-swap alone, no lock.** Rejected: the CAS closes the bootstrap→plan *staleness* window, but two genuinely concurrent writers can both re-read the same cursor, both pass the CAS, and both append — a true-concurrency TOCTOU only a lock closes. The reviewer lens proved this (reverting the lock while keeping the CAS leaves the race live).
3. **A new `specify_cli` mission-write lock.** Rejected: the runtime layer must not import `specify_cli` (layer rules), so PR #5890's lock is not reusable here.
4. **A new transient-contention Decision kind / exit code.** Rejected: it is a `next` contract change with no canonical answer; the existing `blocked` + `reason` (EDGE-003) already carries a refused advance, so contention and staleness reuse it.

## Decision

Advancing a run is serialised by two complementary mechanisms, both load-bearing:

1. **Caller-step compare-and-swap.** `AdvancePlan` carries the `issued_step_id` the caller evaluated at bootstrap (`expected_issued_step`), threaded from `plan_advance` through both the composition and engine paths. The one staleness authority — `commit_advance`'s `StaleAdvancePlan`, via `_refuse_stale_plan` — is **widened** (not duplicated) to also refuse when the live on-disk `issued_step_id` differs from that caller-evaluated step. This closes the bootstrap→plan window (#5682).
2. **Per-run-directory lock.** A dedicated `<run_dir>/state.json.lock` sidecar, constructed through the one canonical primitive `kernel.locks.machine_file_lock` (blocking, 10 s timeout), mirroring `run_index.py`. It is held **only** around the commit read→validate→append→write in `commit_advance` (and `next_step`'s commit), the whole of `provide_decision_answer`, and the retrospective capture + rollback writer. It is **never** held across executor dispatch. Run start (`start_mission_run`) stays lock-free because its run directory is private until the run index publishes it.

Supporting changes: `_write_snapshot` stages through a unique `tempfile.mkstemp` temp (no fixed-name collision); the engine path (`_dn_advance_engine`) refuses a `StaleAdvancePlan` or a `LockAcquireTimeout` with a `blocked` Decision and a named reason — reusing ADR 2026-02-17-1's contract, with **no** new Decision kind and **no** new exit code — and no longer falls back to `next_step` (#5854).

**Invariants:**
- The run-INDEX lock (taken in `get_or_start_run`) is released before any run-cursor lock is acquired; the two are never held nested, so the two locks cannot deadlock.
- The run-cursor lock span never encloses executor dispatch, keeping the hold well under the 10 s ceiling.

## Consequences

- A stale or contended advance is refused as `blocked` with a named reason and writes nothing; the loop does not complete an unevaluated step.
- **Residual (out of scope):** a refusing stale path can make an outer retry loop spin on `blocked` — the livelock guard tracked by [#5112](https://github.com/spec-kitty/spec-kitty/issues/5112). The CAS guarantees run-state integrity, not executor exactly-once: a peer that landed before the composition executor ran still fired that executor's side effects.
- **Residual:** the engine `next_step` one-shot is lock-serialised but not caller-step-CAS-guarded; it is reached in production only on the narrow plan-unavailable edge (no previewed step to complete), so it is not a #5682 exposure.
- The acceptance set pins each part independently (deterministic, no-sleep): the CAS, the engine refusal, the `provide_decision_answer` guard, the lock (a deterministic held-lock-blocks test plus a barrier true-concurrency proof), and the unique temp — reverting any one part turns at least one test red.

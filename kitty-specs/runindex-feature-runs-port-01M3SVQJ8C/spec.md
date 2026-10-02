# Spec — RunIndex: locked, repo-relative run index port

**Mission:** runindex-feature-runs-port
**Fixes:** #5390 (P0, 4.0.0 release scope) · #5389 (P1) · **Refs** #2624 (containment)
**Milestone:** 4.0.0 release scope

## Problem

`.kittify/runtime/feature-runs.json` — the run index mapping a mission to its runtime run
(`run_dir`) — has two defects that share one writer (`get_or_start_run`,
`src/runtime/next/runtime_bridge_io.py`):

- **#5390 (P0):** `run_dir` is persisted as an **absolute** path. After a filesystem copy of a
  project, `spec-kitty next` in the copy resolves the **original** folder's `run_dir` and
  advances the original's cursor (exit 0), marking a step complete there using an artifact that
  only exists in the copy. A **move** leaves a stale absolute path and fails `RUN_STATE_MISSING`.
- **#5389 (P1):** the read-modify-write of the index is **unlocked**. Two concurrent `next`
  starts each save "old snapshot + my one new entry", so one distinct-mission registration is
  lost; continuing that mission silently starts a *new* run and replays the first step.

## Desired behaviour (acceptance)

- **AC-1 (copy):** After copying a runtime-bearing project, `next` in the copy advances the
  **copy's** cursor and leaves the **original's** cursor byte-unchanged. (`#5390`)
- **AC-2 (move):** After moving a project, `next` continues the in-flight run normally (no
  `RUN_STATE_MISSING` for a run whose cursor moved with the project). (`#5390`)
- **AC-3 (containment):** A resolved `run_dir` that escapes the **invoking** repo root is
  **refused, never followed** — no cross-checkout mutation is possible. (`#2624`)
- **AC-4 (concurrency):** Two concurrent `next` starts of **distinct** missions both retain
  their run-index registrations; neither is lost and continuation keeps the original run id.
  (`#5389`)
- **AC-5 (no absolute persisted):** The port never writes an absolute `run_dir` to the index.
- **AC-6 (heal):** An existing index holding absolute `run_dir` values is healed to relative
  tokens by `spec-kitty migrate`, and reported (read-only) by `spec-kitty doctor run-index`.
- **AC-7 (single reader):** The index file is opened by exactly one module — the RunIndex port.

## In scope
The RunIndex port (sole reader/writer), token serialization + read-time resolution +
containment, the lock, the heal migration, the doctor check, the two empty-allowlist gates,
and issue-pinned red-first regression tests.

## Out of scope (audit-only → one follow-up issue)
Other persisted absolute paths found by the audit — `state.json`'s `template_path` (drift
detection silently skipped on move), the run event-log paths, and `review/lock.py`
`worktree_path`. Reported, not fixed here (operator directive). No version bump past the
untagged rc.

## Constraints
- Canonical env-expand/token seam (ADR `2026-08-16-5`), kernel lock (`kernel/locks.py`),
  kernel env-expand (`kernel/env_expand.py`). No new path authority.
- Terminology canon: the domain object is a Mission; `feature-runs.json` is a frozen legacy
  filename kept for compatibility (do not rename in this fix).
- Layer rules: the port imports kernel + local seam only (no new `runtime→specify_cli`
  outbound-ledger growth).

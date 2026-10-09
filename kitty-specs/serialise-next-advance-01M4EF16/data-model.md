# Data Model — serialise-next-advance

This mission adds no new persisted schema. It changes the *concurrency discipline*
around the existing run-cursor files and adds one in-memory field plus one lock
sidecar. Entities below are the ones the fix touches.

## Run cursor (existing — `state.json`)

The authoritative per-run state at `.kittify/runtime/runs/<run_id>/state.json`.
Relevant fields (unchanged shape): `issued_step_id`, `completed_steps`,
`pending_decisions`, `inputs`, `decisions`, `blocked_reason`.

- **Invariant (new, enforced):** a write that completes/issues a step is applied
  only if the on-disk `issued_step_id` still equals the step the caller evaluated
  at bootstrap. Otherwise the write is refused (`StaleAdvancePlan`).
- **Invariant (new, enforced):** at most one process mutates a given run's cursor
  at a time (serialised by the run-cursor lock).
- Written by: `_commit_advance`, `provide_decision_answer`, the
  retrospective-rollback path, and run start (`start_mission_run`). All but run
  start take the lock; run start is exempt (private, unpublished run dir).

## Run event journal (existing — `run.events.jsonl`)

Append-only event log beside `state.json`. The fix does not change its records; it
ensures appends happen under the same lock as the snapshot write, so a refused
advance appends nothing (matching today's `test_stale_plan_raises_and_writes_nothing`).

## Advance plan (existing in-memory — `AdvancePlan`)

Computed by `plan_advance`, committed by `commit_advance`.

- **New field (conceptual): expected issued step.** The `issued_step_id` the
  caller evaluated at bootstrap (`DecideNextContext.current_step_id`), threaded in
  so `commit_advance` compares the live cursor against *the step the caller
  actually gated on*, not only against the plan's own (second) read. Folded into
  the existing `StaleAdvancePlan` check (widened window), not a parallel gate.

## Run-cursor lock (new — `<run_dir>/state.json.lock`)

A dedicated lock-only sidecar guarding the run-cursor read-modify-write.

- Constructed via `kernel.locks.machine_file_lock(lock_path, blocking=True,
  timeout_s=…)` — the one canonical primitive; mirrors `run_index.py`.
- **Resource:** the per-run directory (distinct from the repo-wide run-index lock
  `feature-runs.json.lock`).
- **Ordering invariant:** acquired only after the run-index lock (taken in
  `get_or_start_run`) is released; the two are never held nested (no deadlock).
- **Hold-span invariant:** acquired just before the commit re-read, released after
  the snapshot write; the span never encloses step-contract executor dispatch, so
  the hold stays well under the primitive's 10 s max-hold / 60 s stale-reclaim.

## State transitions (unchanged lanes, new refusal edge)

The 9-lane WP state machine and the run step progression are unchanged. The only
new behavior is an **edge that does not fire**: an advance that would complete a
step the caller did not evaluate is refused (returns `blocked`) and writes
nothing, instead of silently completing it or re-planning `success`.

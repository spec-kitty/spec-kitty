# Data Model: setup-plan commits its lifecycle events on coordination Missions

## Lifecycle event

A line in a Mission's `status.events.jsonl`, written by `emit_artifact_phase`.

- `event_type`: one of `SpecifyCompleted`, `PlanStarted`, `PlanCompleted` (this Mission's scope).
- Mission identity (slug / id) and actor `setup-plan`.
- Deduplicated by `(event_type, dedup_keys)` at append time, so a re-run appends nothing new.

**Invariant (this Mission)**: on a coordination Mission, setup-plan's lifecycle events exist only in the coordination log and are committed on the coordination branch by the end of the run, or the run exits 1 with `SETUP_PLAN_LIFECYCLE_UNCOMMITTED`.

## Coordination record

The Mission's `status.events.jsonl` in the coordination worktree, on the coordination branch. The status authority for a coordination topology.

## Stranded event

A setup-plan lifecycle event written to a coordination Mission's coordination worktree log and left uncommitted there by an earlier CLI. Reported by the existing `doctor coordination` warning `COORDINATION_WORKTREE_DIRTY`; never migrated, committed or deleted by this Mission (C-002).

## setup-plan JSON result (additions)

- `lifecycle_commit`: on a coordination Mission, the router outcome of the coordination commit (`committed` with its hash, or `unchanged`); absent on other topologies.
- On refusal: `result: error`, `phase_complete: false`, `error_code: SETUP_PLAN_LIFECYCLE_UNCOMMITTED`, `lifecycle_events_in_log` (setup-plan event types present in the worktree log) and `lifecycle_diagnostic` (the router or guard diagnostic); the plan commit that landed stays reported as `commit_hash`.
- A concurrent status write that already committed setup-plan's events (the branch moved, every setup-plan event id is on it) is `lifecycle_commit.status: unchanged`, not a refusal.

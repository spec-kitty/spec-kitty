# Data Model: CI Pipeline Honesty — Actionable Fixes

This mission is CI tooling; the "entities" are the value objects the two extracted helpers compute
over. No persistent storage.

## #4360-B — shard completeness (reconcile_shards.py)

- **RegistryShard**: `module: str`, `shard_index: int` — a row from the module-shard registry
  (37 total at base). Identity: `(module, shard_index)`.
- **SelectedSet**: the shards the diff-scoped matrix chose for this run. `None` ⇒ full-mode
  (all registry shards selected — legacy behaviour).
- **ShardArtifact**: `module`, `shard_index`, `fresh: bool` (present in the current run) — coverage
  artifact produced by a component workflow.
- **CompletenessResult** (the load-bearing output):
  - `complete: bool`
  - `missing: list[RegistryShard]`
  - Rule: a shard is *required* iff it is in `SelectedSet` (or `SelectedSet is None`). A required
    shard absent from BOTH current and fallback ⇒ `missing` ⇒ `complete = False` (fatal).
  - Rule (**must_be_fresh invariant**): a SELECTED shard must be *fresh* in the current run; a
    fallback/backfill artifact does NOT satisfy a selected shard.
  - Rule: an UNSELECTED shard is optional — backfilled from a prior run if available, ignored (never
    `missing`) if absent.

**Invariant (NFR-001)**: `complete = True` requires every SELECTED shard fresh. No relaxation may let
a selected-but-absent shard read complete.

## #4208 — blocking classification (router_gate.py)

- **JobConclusion**: one of `success | failure | cancelled | timed_out | skipped | startup_failure |
  action_required` (jobs-API vocabulary; `needs`-context only ever yields the first five, never
  `timed_out`).
- **BlockingEntry**: `job: str`, `conclusion: JobConclusion`.
- **GateDecision**:
  - `blocking: dict[job, conclusion]` — jobs whose conclusion ∈ blocking set.
  - `blocks: bool` — True iff `blocking` non-empty.
  - Rule: the blocking set membership is UNCHANGED from baseline (`failure`, `cancelled`, and
    `timed_out`-as-a-form-of-cancelled all block); only the *reported label* distinguishes
    `timed_out` from `cancelled`.

**Invariant (NFR-001)**: `blocks` is byte-identical to baseline for every `{failure, cancelled}`
input distribution; classification adds labels, never changes the verdict.

## #4454 / #4212 — no new value objects

Pure config: #4454 adds routing globs (matched by the existing `select_modules` parser); #4212 adds
shell exit-code capture + a terminal gate step. Their behaviour is pinned by the existing
workflow-lint / gate-selection authority tests, not by a new data type.

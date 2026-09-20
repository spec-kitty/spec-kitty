# Contract — Terminus-Safety Invariant (behavioral)

The three terminus commands MUST satisfy these observable contracts. Each is a red-first test hook.

## C-MERGE (FR-001/002/003/006/011)
- **PRE**: `merge` evaluates merge-ready via the shared aggregate BEFORE any mutation, regardless of `policy.merge_gates.mode`.
- **REFUSE**: if not merge-ready → exit ≠ 0, message names the missing WP(s), and **no** lane consolidation, **no** `mission_number` bake, coord/lane/primary refs unchanged; the WP can still reach `for_review`.
- **PASS**: merge-ready mission proceeds exactly as before (no false-block), including on `--resume` (readiness re-evaluated LIVE, never vacuous on a stale `merged_at`).
- **WARN**: evidence-QUALITY gates still soften to warnings under `warn` mode.
- **BAKE (merge-ready)**: `mission_number` write-back reaches the correct meta.json surface, or the unbaked field is surfaced as a queryable event + merge-summary line — never a silent fail-open.

## C-CLOSE (FR-004/005/013)
- **PRE**: `mission close` (non-discard) checks `is_mission_merged` BEFORE teardown.
- **REFUSE**: not-merged → exit ≠ 0, **no** retrospective written/committed, **no** `RetrospectiveCaptured` event, coord worktree intact; message points at `--discard`.
- **PASS**: merged mission → existing teardown.
- **ROBUST**: an orphaned `coordination_branch` marker is tolerated (no traceback), slug rendered once (not doubled), `--json` honored.

## C-ROLLBACK (FR-007/008)
- After a completion command mutates and a later step fails, coord ref/worktree (and target ref on direct-on-target) reset to the pre-command checkpoint; `--resume` reads a coherent state (committed `done` markers ↔ worktree bytes consistent).

## C-DIRECT-ON-TARGET (FR-010/012)
- **SAFE**: a not-merge-ready direct-on-target mission refuses BEFORE advancing the target ref (target provably unchanged) — regardless of whether the rollback arm has shipped.
- **COMPLETE**: a merge-ready direct-on-target mission with no lane branch completes transactionally via `merge --skip-lanes`/`--no-lanes` (no hard-fail), still enforcing the merge-ready precondition (no bypass).

## C-SHARED-AUTHORITY (FR-009)
- `merge`, `accept`, and `mission close` in `specify_cli` all derive terminal readiness from the one shared aggregate; none re-inlines its own acceptable-ending loop. (Runtime-side loops out of scope, C-002.)

## C-ACCEPT-GUIDANCE (FR-014)
- `accept` gives followable guidance (names the real escape hatch), not impossible "materialize-then-retry". Liveness: verified-already-fixed if a red-first probe is green on current main.

# Contract: Verdict invariants (dedup survivor — behavior pins)

Stage 1 changes **no** `classify`/`report` behavior; these are the invariants the new dedup unit test must pin, because the fan-out cap (coalesce-with-survivor) now depends on them.

## VI-1 — Survivor re-reads live evidence (double-snapshot)

`fleet_verdict.report()` snapshots current evidence at entry (`:317`) and again immediately before publishing (`:332-334`); if the head SHA or evidence fingerprint drifted between the two reads it raises `"changed before publication; later event will reconcile"` and posts nothing.

- **Test**: given a survivor whose second snapshot differs from the first, `report()` raises (does not post a stale verdict).
- **Rationale**: under `cancel-in-progress: true`, only the last completion survives; it must recompute from live state. Pinned so a future edit cannot turn coalescing into a stale-post.
- **Non-tautology guard (Renata, implement-review)**: the drift between the two `snapshot()` calls MUST be driven through the in-memory `API()` stub's mutating state so `report()` actually calls `snapshot` twice and compares — NOT by patching `snapshot` itself (which would assert the mock, not the behavior). Reviewer verifies the test exercises the real double-read.

## VI-2 — Newer verdict is never suppressed; only exact-duplicate running is

The running-suppression (`:325-331`, guard at `:329`) returns without posting **only** when the latest ledger comment is a bot comment carrying the same fingerprint, OR (`state=="running"` AND the latest body starts with `[ci] running @<sha>`). A newer *terminal* verdict (green/red) for the same head is **not** suppressed.

- **Test**: `test_duplicate_latest_evidence_is_suppressed_but_newer_verdict_is_not` (existing, `:209-219`) stays green; ADD an explicit case: a `running` post followed by a `green`/`red` post for the same head **does** publish.
- **Rationale**: NFR-002 — the last-writer terminal verdict a landed tip needs is never dropped by dedup.

## VI-3 — Never-green preserved

`classify` never turns absent/cancelled/skipped/incomplete evidence into green (`:87`).

- **Test**: `test_truncated_files_and_deferred_pr_never_green` (existing) stays green. Stage 1 adds no path that could green-wash.

## VI-4 — Main path shares the same guarantee

`fleet_main.report()` re-reads main head + attempts at `:124` (raises on drift) and dedups a single open incident issue.

- **Test**: `test_fleet_main.py` main-intake tests stay green; the per-SHA `report-main` coalesce does not change the incident-issue idempotence.

## VI-5 — Aggregate fail-closed guard untouched (NFR-001)

Stage 1 touches no source-eligibility or reconciliation logic in `ci-aggregate.yml` / `scripts/ci/reconcile_shards.py`.

- **Test**: `tests/ci/test_reconcile_shards.py` and the aggregate guard tests stay green; the Stage-1 diff contains no `ci-aggregate.yml` / `reconcile_shards.py` / `aggregate_source.py` changes.

## VI-6 — Coalescing depends on `types:[completed]` staying present (Renata LOW)

The survivor's "later event will reconcile" behavior (VI-1) relies on upstream `completed` `workflow_run` events remaining the trigger. The Stage-1 trim to `types:[completed]` *preserves* the reconciling event (completions are exactly what remain), so the assumption holds. But a future narrowing of `types:` (or removing a completing upstream workflow) could silently turn coalescing into a suppression path — the same class as the Stage-3 compat edge case.

- **Pin**: not unit-testable in pytest (C-002); documented here + in the top-level-concurrency golden-YAML pin's neighborhood so a future `types:` edit is reviewed against this dependency. A wedged terminal survivor is caught on the merged tip by **SC-006** (terminal-verdict presence).

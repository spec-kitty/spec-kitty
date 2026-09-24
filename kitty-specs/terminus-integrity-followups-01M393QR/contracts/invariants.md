# Behavioral Invariant Contracts — Terminus Integrity Follow-ups

Executable-intent contracts. Each invariant names its verifying `tests/terminus/` repro (red-first) and the fail-closed rule. These are the ATDD contract the WPs deliver.

## INV-1 — Squash content soundness (WS1 / FR-001, FR-002)

> After an exit-0 `spec-kitty merge` on the **default squash strategy**, no content path on the target is authored solely by a removed/canceled WP.

- **Given** a mission where a canceled WP authored `src/pkg/<wp>_removed.py` that rode a carrier lane, **When** `spec-kitty merge` runs with no `--strategy`, **Then** the gate FAILs, the target is CAS-rolled-back, the command exits non-zero, and `<wp>_removed.py` is absent from the target tree.
- **Given** a clean mission (all approved present, nothing excluded), **When** the default squash merge runs, **Then** the content axis PASSes (no false-refusal).
- **Fail-closed:** `GitProbeError` from `blob_id_at`/`changed_paths_in_range`, or a `None` window base, ⇒ REFUSE (never PASS).
- **Honest reporting:** the squash success message must not assert excluded-commit reachability was verified beyond what the axis computed.
- **Verifies:** `test_terminus_reconciliation_property::no_excluded_commit_reachable[squash]` (xfail→green); default-squash variants of `test_repro_{4945,4977,4981}.py` (blob/tree-presence observable); a new clean-squash no-false-fail param.
- **Residual (deferred):** 3-way merge-resolution content (blob ≠ either parent) — tracked follow-up, honest `xfail` if surfaced.

## INV-2 — Resume fidelity (WS2 / FR-003, FR-004, FR-005)

> A resumed merge behaves identically to the uninterrupted one: same strategy, same landed tree.

- **Given** an interrupted `merge --strategy merge`, **When** `merge --resume` runs with no `--strategy`, **Then** the resumed run uses the persisted `merge` strategy, not squash.
- **Given** a resume with an explicit `--strategy` differing from persisted, **When** it runs, **Then** it REFUSEs (H1 strategy-flip guard).
- **Given** an interrupted merge whose pre-interrupt lane tips carried approved commits, **When** resumed, **Then** the reconciliation claim's coord base is the persisted `pre_mutation_coord_sha` (not the live checkpoint) and every pre-interrupt approved commit is reachable from the target.
- **Given** an interrupted non-default-target merge, **When** resumed, **Then** it lands on that target with no `SafeCommitHeadMismatch`.
- **Fail-closed:** absent persisted coord base / lane tips where required ⇒ REFUSE (H4); a live lane tip that is neither equal to nor a descendant of the persisted tip ⇒ REFUSE (H3).
- **Verifies:** `test_repro_{4985,4991}.py` (green after strategy fix); `test_repro_{4982,4997}.py` (green after strategy + lane-tip preservation).

## INV-3 — Coordination write integrity (WS3 / FR-006, FR-007)

> A coord-routed write never clobbers committed coordination content by mistaking a stale local head for a first-write window.

- **Given** an `UNMATERIALIZED` local-head coord branch already carrying committed issue-matrix content, **When** a coord-routed write attempts self-materialization, **Then** the gate REFUSEs.
- **Given** a genuine first-write (no committed matrix content), **When** it self-materializes, **Then** it succeeds (no false-refusal).
- **Given** an `issue-verdict` write, **When** it resolves its write surface, **Then** it uses `resolve_for_write` (fail-closed), not the degrading read resolver.
- **Fail-closed:** unreadable git during the committed-content probe ⇒ treat as content-present ⇒ REFUSE.
- **Verifies:** `test_repro_4970.py` (xfail→green).

## Cross-cutting (C-004)

Every INV runs its check **before** any branch/worktree teardown, push, or exit-0; the existing verify→FAIL→CAS-rollback→exit-1 boundary and 3-arg `update-ref` CAS discipline are preserved.

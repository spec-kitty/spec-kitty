# Implementation Plan: Consolidation / done-bookkeeping regressions (#6071, #6073)

**Branch**: `issue-6071-consolidation-bookkeeping-regressions` · **Spec**: `spec.md` ·
**Diagnosis**: `research/defect-diagnosis.md`

## Strategy

Four independently-reviewable slices, each red-first through its pre-existing test entry
point (reproductions recorded in `research/`), each fixing the root cause (not retry-to-green).
Smallest-viable-diff; locality of change; no gate loosening. No tidy-first enabler commit is
needed — each surface is touched surgically and the touched functions are already within
complexity/Sonar limits.

## Slices → commits (each maps to named tests)

### Slice 2 — Post-merge done-check via the canonical reducer (cluster A, FR-001/FR-002)
- `src/specify_cli/consolidation/done_bookkeeping.py`: replace the hand-rolled wall-clock
  `(at, event_id)` fold in `_assert_merged_wps_done_on_target` with the canonical status
  reducer (reads the target-branch committed `status.events.jsonl`, reduces causally). Retire
  `_parse_target_lanes_by_wp` (its only consumer) or route it through the canonical reducer.
- Re-point `tests/consolidation/test_done_bookkeeping_seam.py` #5354 unit test(s) to realistic
  full-envelope events preserving the invariant (newer `done` beats older migration seed).
- Respect the non-vacuity AST pin referencing `_assert_merged_wps_done_on_target`.
- Target green: `test_merge_coord_topology_1772::test_post_merge_validation_reads_in_branch_status_path`.

### Slice 3 — Bare-slug composed-dir teardown on resume (cluster B, FR-003)
- `src/specify_cli/consolidation/phase_teardown.py`: in `_unlanded_paths_outside_mission_dir`,
  widen `own_prefixes` to include the composed `<slug>-<mid8>` coordination directory via the
  canonical authority `missions._read_path_resolver.mission_dir_aliases` (as
  `interrupted_alias_fold_guidance` already does).
- Target green: `test_bare_slug_coord_mission_consolidates_again_after_the_bookkeeping_commit_failed`.

### Slice 4a — Skip-lanes fixture realism (cluster C, FR-004) — TEST-DATA re-pin
- `tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py`: in
  `_bootstrap_direct_on_target_mission`, replace the invalid `claimed→in_progress`,
  `in_review→approved` chain with a reducer-valid chain
  (`claimed→in_progress→for_review→in_review→approved`) so WP01 genuinely reduces to `approved`
  under the events-10.4.x stricter reducer.
- Target green: `test_issue_2745_merge_skip_lanes` ×3. (Divergence from the brief's "product
  fix" framing — flagged in the PR with the probe evidence.)

### Slice 4b — Interrupted-fold dirty detection (cluster D, FR-005)
- Make the interrupted one-directory-fold state (composed-dir coordination-KIND deletions in
  the root checkout) trip `MERGE_UNSAFE_PRIMARY_DIRTY` in the pre-mutation primary-checkout leg
  so the existing #5748 `interrupted_alias_fold_guidance` renders, rather than passing the
  dirty guard (role-based residue treats them disposable) and hitting the stale
  `__global_merge__` lock. Lowest-risk: a dedicated interrupted-fold detection reusing the
  existing predicate, without loosening the shared #5965/#5966 residue classifier. Confirm the
  `--abort` step reclaims the stale same-owner lock.
- Target green: `test_a_run_killed_inside_the_fold_...[status-pair-only]` and `[every-coordination-kind]`.

## Testing (per CLAUDE.md + NO_FULL_HEAVY_SUITES_IN_MISSION)
Seven target tests by name; owning dirs `tests/consolidation/`,
`tests/integration/test_merge_lane_planning_data_loss.py`, the relevant
`specify_cli` merge/2745/1772 tests; `make test-fast`; the named gate file(s)
`tests/consolidation/test_single_rollback_authority.py` (+ any coord-teardown/bookkeeping gate).
Integration resume tests serially (`-p no:xdist`) AND under `make test-fast -n auto`.
`ruff check`, `ruff format --check --force-exclude` changed files, mypy, complexity ≤ 15.
Never the bare `tests/architectural/` dir; never `make test-full`.

## Risks
- Slice 4b touches the pre-mutation preflight near the shared residue classifier — keep the
  change additive (detect-and-refuse) so #5965/#5966 behaviour is unchanged for non-fold dirt.
- Running `spec-kitty consolidate` locally on this mission exercises the very code under fix —
  single_branch/direct_repo topology has no lanes, so the risk is low; done last.

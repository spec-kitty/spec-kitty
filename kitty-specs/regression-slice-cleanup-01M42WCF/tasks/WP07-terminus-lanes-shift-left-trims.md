---
work_package_id: WP07
title: Terminus/lanes SHIFT-LEFT trims to one smoke per family (#5618 part 2)
dependencies:
- WP06
requirement_refs:
- FR-006
- FR-008
- NFR-001
- C-001
- C-002
- C-005
- SC-003
- NFR-003
planning_base_branch: issue-5618-regression-slice-cleanup
merge_target_branch: issue-5618-regression-slice-cleanup
branch_strategy: Planning artifacts for this mission were generated on issue-5618-regression-slice-cleanup. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5618-regression-slice-cleanup unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-regression-slice-cleanup-01M42WCF
base_commit: 34a4baa8297101bd9f0f30834374928637f4a55e
created_at: '2026-10-04T08:20:00.545312+00:00'
subtasks:
- T033
- T034
- T035
- T036
- T037
phase: Phase 1 - Ledger follow-through (#5618)
history:
- at: '2026-10-04T07:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/terminus/
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- tests/terminus/test_abort_restores_snapshot.py
- tests/terminus/test_canceled_dependency_content_refused.py
- tests/terminus/test_rollback_restores_refs.py
- tests/lanes/test_lane_allocation_integrity_e2e.py
- tests/lanes/test_destroyed_lane_guard_lanes_topology.py
- tests/terminus/test_mixed_lane_canceled_content_controls.py
- tests/terminus/test_mixed_lane_fail_recovery_and_attestation.py
- tests/terminus/test_claim_refusal_before_mutation.py
- tests/terminus/test_mixed_lane_canceled_content_verdicts.py
- tests/terminus/test_mixed_lane_closed_world.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Terminus/lanes SHIFT-LEFT trims to one smoke per family (#5618 part 2)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission regression-slice-cleanup-01M42WCF`). All feedback items must be addressed before the work is complete.

---

## Objectives & Success Criteria

- **Goal**: Cut ≈820 s of summed per-PR runtime by trimming the slow consolidate/abort replays to one smoke per behaviour family, after re-proving each covering seam guard with the ledger's planted breaks B1–B9.
- **Independent test**: For each trimmed family the named seam guard goes RED on the matching planted break (B1–B9) and the kept smoke passes on the clean tree.
- **Issue**: #5618 — read the full issue body (ledger + planted-break table) before starting: `https://github.com/spec-kitty/spec-kitty/issues/5618`.
- Every removal (RETIRE, trimmed SHIFT-LEFT test, retired AST pin) has a planted-break record with a RED covering guard.

## Context & Constraints

- Spec: `kitty-specs/regression-slice-cleanup-01M42WCF/spec.md`; plan: `.../plan.md`; research: `.../research.md` (R-02 marker routing, R-03 planted breaks in worktrees).
- Charter: `.kittify/charter/charter.md` — Standing Order #4 (judge the test; red-first; never retry-to-green), `NO_FULL_HEAVY_SUITES_IN_MISSION`.
- Procedure: `packs/internal/procedures/test-suite-quality-assessment.procedure.yaml` (step: verify each fix/retirement with a planted break); built-in `test-desiderata-and-boundaries` and `testing-principles` styleguides; `development-assist-test-cleanup` procedure.
- `tests/regression/README.md` — what `regression` means and the exit rule for green pins.
- Ledger rows may be stale against current `main`: apply the verdict's intent to the file's current shape and record any deviation.

## Branch Strategy

- **Strategy**: lanes (execution worktree per computed lane from `lanes.json`)
- **Planning base branch**: `issue-5618-regression-slice-cleanup`
- **Merge target branch**: `issue-5618-regression-slice-cleanup`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

Implement command: `spec-kitty agent action implement WP07 --agent claude --mission regression-slice-cleanup-01M42WCF`

## Shared Protocol (binding for every subtask in this WP)

### Planted-break protocol (RETIRE / SHIFT-LEFT / FIX evidence — FR-008, C-005)

1. Work in this WP's lane worktree. Edit the named product file under `src/` to disable
   exactly the behaviour the guard names (the issue ledger names the edit; reproduce it).
2. Run ONLY the named guard files:
   `uv run --frozen pytest <guard files> -q -p no:randomly` — pytest's `pythonpath = src`
   makes the worktree's `src/` win for in-process tests. For tests that shell out to the
   `spec-kitty` CLI or `python -m specify_cli`, prefix `PYTHONPATH=$PWD/src`.
3. Record `N failed / M passed` (RED is required for a removal).
4. Revert: `git checkout -- src/` and confirm `git status --short src/` prints nothing.
   **A planted break is never committed.**
5. If the guard stays GREEN, the verdict flips to KEEP (or FIX): keep the test and say so.
6. Append one row per break to the WP's Activity Log and to the evidence file named in
   the WP (format: `| id | product edit | guard files | result | reverted |`).

### Marker edits

- MARKER-ONLY: remove `regression` (module `pytestmark` entry or decorator). Keep the
  tier markers (`fast`, `unit`, `integration`, `git_repo`, ...). If the test is left with
  no tier marker, add the marker its siblings in the same directory use.
- SPLIT-BY-KIND: move the marker from module level onto only the ledger-named tests
  (decorator), or split those tests into a sibling file — prefer the decorator unless the
  ledger says "split the file".
- Rewrite stale docstrings that call a green test "red-first" / "stays red on main": per
  `tests/regression/README.md` exit rule, say the defect is fixed and the test is a
  permanent guard; keep the issue number as history.
- Never touch `p0_repro` (C-003).

### Validation (run before handing to review)

```bash
uv run --frozen pytest <every file you touched> -q                 # record counts
uv run --frozen pytest <touched files> -q --durations=0 | tail -15  # before and after timing
uv run --frozen ruff check <touched files>
uv run --frozen ruff format --check --force-exclude <touched files>
uv run --frozen pytest <touched files> -m regression --collect-only -q | tail -1
```

Run the marker gates once at the end of the WP:
`uv run --frozen pytest tests/architectural/test_marker_job_completeness.py tests/architectural/test_fast_tier_marker_completeness.py -q`.
Never run `make test-full` or whole heavy directories (C-002). If a test is red on
`origin/main` too, it is baseline: note it, do not fix it.

### Commits

- Conventional Commits, type `test` (e.g. `test(status): ...`). One logical change per commit;
  seam tests land in a commit BEFORE the commit that trims the slow test.
- Every commit message ends with the trailer
  `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`.
- No AI model identifiers in commit messages.
- Product code under `src/` is never changed (C-001). If a test exposes a real product
  defect, stop and report it; it becomes a filed issue, not a fix here.


## Subtasks & Detailed Guidance

### Subtask T033 – Rollback/abort family: B1–B5
- Files: `tests/terminus/test_abort_restores_snapshot.py` (9, 251 s; keep `test_abort_restores_every_snapshotted_branch`), `tests/terminus/test_rollback_restores_refs.py` (8, 125 s; keep 1–2 smoke).
- Guards: `tests/consolidation/test_rollback_authority.py`, `tests/specify_cli/cli/commands/test_consolidate_abort_rollback.py`, `tests/consolidation/test_executor_rollback_wiring.py`, `tests/consolidation/test_single_rollback_authority.py`.
- Planted breaks (re-run, record): B1 drop the `live != post` "moved by another actor" guard in `src/specify_cli/consolidation/rollback.py`; B2 `_refusal` always returns None; B3 `--abort` skips `rollback_to_snapshot` (`src/specify_cli/cli/commands/consolidate.py`); B4 a foreign live merge lock no longer refuses the abort; B5 gate/door rollback never calls the authority (`consolidation/executor.py`). Each must red its unit guard. Only then trim; map each removed test to the break whose guard covers it.

### Subtask T034 – Claim-refusal ordering: B6
- `tests/terminus/test_claim_refusal_before_mutation.py` (3, 61 s) → SHIFT-LEFT: guards `tests/consolidation/test_executor_phase_boundary.py` + `tests/consolidation/test_claim_integrity_refusal.py`. B6: the claim-integrity refusal is not acted on before the first mutation → guards RED. Keep one smoke (the ledger says SHIFT-LEFT; keeping one e2e per family is the brief's rule).

### Subtask T035 – Canceled-content verdict families: B7, B8
- `tests/terminus/test_canceled_dependency_content_refused.py` (6, 150 s): keep 1 param, drop the merge×squash matrix (strategy does not change this axis). Guard: `tests/consolidation/test_canceled_dependency_lane.py` incl. WP06's new units; B8 must red ≥2.
- `tests/terminus/test_mixed_lane_canceled_content_verdicts.py` (5, 51 s): keep the add/modify/delete smoke; guard `tests/consolidation/test_reconciliation.py`; B7 (canceled-content axis disabled in `reconciliation.py`) reds 7.
- `tests/terminus/test_mixed_lane_fail_recovery_and_attestation.py`: remove the 3 attestation-level tests now covered by WP06's units (re-run B7a); keep the rerun + supersede e2e.
- `tests/terminus/test_mixed_lane_canceled_content_controls.py` (7, 94 s): negative controls; the ledger says "needs an over-trigger break; not done". Plant an OVER-trigger break (make the canceled-content check flag content a surviving WP superseded — i.e. stop honouring supersession in `wp_attribution.py`) and run `tests/consolidation/test_wp_attribution.py` + `tests/consolidation/test_reconciliation.py`. Trim to the superseded-by-survivor squash smoke only for controls whose unit guard went RED; keep the rest and say so.
- `tests/terminus/test_mixed_lane_closed_world.py`: KEEP (only e2e proof of FR-013); ensure it carries the `slow` tier marker as the ledger says "KEEP (slow tier)" — check `slow` is the registered marker name and what selects it.

### Subtask T036 – Lanes families: B9
- `tests/lanes/test_destroyed_lane_guard_lanes_topology.py` (9, 101 s): keep the refuse + reopen smokes; guards `tests/lanes/test_destroyed_lane_guard_helpers.py` + `tests/lanes/test_issue_4889_destroyed_lane_guard.py`. B9 (remove the `_refuse_if_lane_destroyed` call in `src/specify_cli/lanes/worktree_allocator.py`) reds the 4889 guards; per-row decision-table breaks were NOT planted by the review — plant one per removed row in the helper (`test_destroyed_lane_guard_helpers.py` must go RED) or keep that row.
- `tests/lanes/test_lane_allocation_integrity_e2e.py` (4, 103 s): ledger says "SHIFT-LEFT → slow/nightly". The #4889 half is covered (B9); the #4905 half was not planted — plant break D (skip `_partition_paths_by_primary_kind` in `workflow.py`) and run `tests/specify_cli/cli/commands/agent/test_workflow.py` + `tests/specify_cli/cli/commands/agent/test_issue_4905_coord_staging.py`. Then mark the file `slow` (check how `slow` is routed: `Makefile`, `scripts/ci/shard_select.py`, `ci-nightly.yml`) rather than deleting, if `slow` moves it off the per-PR path; otherwise trim to one smoke per fix.

### Subtask T037 – Validate, time and record evidence
- Run the Validation block on every trimmed file and every guard file (guards are read-only here). Record summed durations before/after per file (NFR-001 target: ≥410 s of the ≈820 s estimate). Record B1–B9 + over-trigger rows.

## Risks & Mitigations

- A planted break left in `src/` → C-005 violation: run `git status --short src/` before every commit.
- A covering guard that stays green → the slower test is the last guard: keep it (verdict flips to KEEP).
- Removing a marker can drop a test out of every CI selection only if no tier marker remains: run the marker gates.

## Review Guidance

- Re-run at least one planted break per removal family yourself and confirm RED; confirm `git diff --stat origin/main -- src/` is empty.
- Check each removed test maps to a recorded RED guard; check each MARKER-ONLY file keeps a tier marker.
- Confirm seam tests landed in an earlier commit than the trims.

## Activity Log

- 2026-10-04T07:40:00Z – system – Prompt created.

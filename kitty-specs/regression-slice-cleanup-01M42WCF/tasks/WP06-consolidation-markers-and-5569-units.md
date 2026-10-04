---
work_package_id: WP06
title: 'Consolidation/lanes marker fixes and #5569 seam units (#5618 part 1)'
dependencies: []
requirement_refs:
- FR-006
- FR-008
- C-001
- C-004
- C-005
- SC-002
- NFR-003
planning_base_branch: issue-5618-regression-slice-cleanup
merge_target_branch: issue-5618-regression-slice-cleanup
branch_strategy: Planning artifacts for this mission were generated on issue-5618-regression-slice-cleanup. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5618-regression-slice-cleanup unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-regression-slice-cleanup-01M42WCF
base_commit: 6b4b1efbef89c4e0966c7aefa1429e76acb5d2f1
created_at: '2026-10-04T07:32:50.340295+00:00'
subtasks:
- T028
- T029
- T030
- T031
- T032
phase: Phase 1 - Ledger follow-through (#5618)
history:
- at: '2026-10-04T07:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/consolidation/
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- tests/lanes/test_lane_tip_record_points.py
- tests/terminus/test_fixture_mixed_lane_canceled.py
- tests/specify_cli/lanes/test_lane_dependency_cycle_cli_determinism.py
- tests/specify_cli/lanes/test_for_review_gate_parity.py
- tests/consolidation/test_done_bookkeeping_rollback_coherence.py
- tests/consolidation/test_traces_driver_section_union_4894.py
- tests/orchestrator_api/test_mission_branch_delete_cas.py
- tests/consolidation/test_terminus_absent_snapshot_precondition_fold.py
- tests/consolidation/test_hollow_review_warnings.py
- tests/consolidation/test_canceled_dependency_lane.py
- tests/consolidation/test_canceled_attestation.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Consolidation/lanes marker fixes and #5569 seam units (#5618 part 1)

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

- **Goal**: Drop the mislabel from the 8 MARKER-ONLY files, split the #4894 file, add the #5569 deleted-branch REFUSE and approved-dependency PASS units, and move the 3 attestation-level tests of the mixed-lane fail/attestation e2e into `test_canceled_attestation.py`.
- **Independent test**: Planted break B8 (`never_exempt` no longer subtracted) reds ≥2 tests in `tests/consolidation/test_canceled_dependency_lane.py` instead of 1.
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

Implement command: `spec-kitty agent action implement WP06 --agent claude --mission regression-slice-cleanup-01M42WCF`

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

### Subtask T028 – MARKER-ONLY batch
Drop `regression` (keep/add tier markers) on: `tests/lanes/test_lane_tip_record_points.py`, `tests/terminus/test_fixture_mixed_lane_canceled.py` (marker declared twice — remove both), `tests/specify_cli/lanes/test_lane_dependency_cycle_cli_determinism.py`, `tests/specify_cli/lanes/test_for_review_gate_parity.py`, `tests/consolidation/test_done_bookkeeping_rollback_coherence.py`, `tests/orchestrator_api/test_mission_branch_delete_cas.py`, `tests/consolidation/test_terminus_absent_snapshot_precondition_fold.py`, `tests/consolidation/test_hollow_review_warnings.py`.

### Subtask T029 – SPLIT-BY-KIND `test_traces_driver_section_union_4894.py`
- Unmark the unit half; keep `regression` on the issue-pinned e2e half (read the file; if it has one test with both halves, keep the marker and record that the split is not applicable).

### Subtask T030 – #5569 units: deleted-branch REFUSE and approved-dependency PASS
- **Purpose**: B8 rests on one unit test (`tests/consolidation/test_canceled_dependency_lane.py`). Read `src/specify_cli/consolidation/wp_attribution.py` (`never_exempt`, the dependency-tip exemption) and the existing test.
- Add (a) a fully-canceled dependency lane whose branch is unreadable/deleted → the attribution result REFUSEs (CLAUDE.md: "REFUSEs when its branch is unreadable (#5569)"); (b) an approved (non-canceled) dependency lane → its content stays exempt → PASS (positive control on the same fixture builder).
- Planted break **P-5618-B8**: stop subtracting `never_exempt` → ≥2 tests RED. A second break: treat an unreadable dependency branch as empty → the REFUSE test RED. Revert both.
- These tests must land in a commit before WP07 trims `tests/terminus/test_canceled_dependency_content_refused.py`.

### Subtask T031 – Attestation units moved from the mixed-lane fail/attestation e2e
- Read `tests/terminus/test_mixed_lane_fail_recovery_and_attestation.py` (5 tests): the attestation-rejection and dry-run-notice tests (3) belong at unit level. Add equivalent unit tests to `tests/consolidation/test_canceled_attestation.py` (calling `consolidation/canceled_attestation.py` directly). Do NOT edit the terminus file here — WP07 removes the 3 e2e tests after this WP lands.
- Planted break **P-5618-B7a**: make the attestation validator accept an empty reason / unknown WP → new units RED. Revert.

### Subtask T032 – Validate and record evidence
- Run the Validation block; record P-5618-B8, B8b, B7a.

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

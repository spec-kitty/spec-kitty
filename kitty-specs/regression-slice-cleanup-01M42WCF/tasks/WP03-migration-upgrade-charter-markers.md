---
work_package_id: WP03
title: 'Migration/upgrade/charter marker splits, #4962 port, T030 retire (#5621)'
dependencies: []
requirement_refs:
- FR-004
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
base_commit: 11c768416d8c9c76807b35f4ba7ef204b7ba1341
created_at: '2026-10-04T07:30:31.876828+00:00'
subtasks:
- T011
- T012
- T013
- T014
- T015
phase: Phase 1 - Ledger follow-through (#5621)
history:
- at: '2026-10-04T07:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/migration/
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- tests/specify_cli/test_audit_tail_readers.py
- tests/specify_cli/migration/test_mission_state_identity.py
- tests/specify_cli/upgrade/migrations/test_single_branch_code_lanes_restamp.py
- tests/unit/migration/test_mission_state_lanes_rebuild.py
- tests/specify_cli/migration/test_backfill_cutover_guard.py
- tests/policy/test_issue_matrix_cross_site_consistency.py
- tests/regressions/test_issue_4962_charter_encoding.py
- tests/migrate/test_charter_encoding_migration.py
- tests/specify_cli/audit/test_status_event_row_shape.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Migration/upgrade/charter marker splits, #4962 port, T030 retire (#5621)

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

- **Goal**: Stop the stale module-level `regression` marker (the dead '#2957 main-push collection' reason) from spreading onto non-pins; port the one non-redundant #4962 subprocess case to the migration unit file and retire the subprocess file; retire T030.
- **Independent test**: `pytest <the 9 files> -m regression --collect-only` drops from 66 to only the ledger-named pins; the #4962 tie-break planted break reds the migration unit file.
- **Issue**: #5621 — read the full issue body (ledger + planted-break table) before starting: `https://github.com/spec-kitty/spec-kitty/issues/5621`.
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

Implement command: `spec-kitty agent action implement WP03 --agent claude --mission regression-slice-cleanup-01M42WCF`

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

### Subtask T011 – SPLIT-BY-KIND the four ledger files
- **Files / rules** (#5621 Do 1):
  - `tests/specify_cli/test_audit_tail_readers.py` (27 tests, 56 s): keep `regression` on the 14 corrupt-input pins only; drop `unit` from the 5 command-level tests (they are not unit tests — give them the tier the directory uses for CLI/component tests, e.g. `integration` or `fast` — check siblings).
  - `tests/specify_cli/migration/test_mission_state_identity.py`: keep the marker on issue-pinned tests only (read docstrings for issue numbers).
  - `tests/specify_cli/upgrade/migrations/test_single_branch_code_lanes_restamp.py`: keep the marker on the #5398 cases only.
  - `tests/unit/migration/test_mission_state_lanes_rebuild.py`: only T011 (#4758) keeps it.
- **Steps**: remove the module-level `regression` and the "#2957 main-push collection" justification comment; add `@pytest.mark.regression` to each pin. Verify with `--collect-only -m regression`.

### Subtask T012 – MARKER-ONLY two files
- `tests/specify_cli/migration/test_backfill_cutover_guard.py`: drop the module-level marker; keep the explicit per-test pins.
- `tests/policy/test_issue_matrix_cross_site_consistency.py`: an invariant, not a bug pin — drop `regression`, keep the tier marker.

### Subtask T013 – SHIFT-LEFT #4962: port case 3, then retire the subprocess file
- **Purpose**: #5621 Do 3 — `tests/regressions/test_issue_4962_charter_encoding.py` runs subprocesses (8 s); with the tie-break broken (`cp1252_in_tied = False`) 7 lower tests also go red, so cases 1 and 2 are redundant.
- **Steps**:
  1. Port case 3 (`test_preexisting_backup_blocks_normalization`) into `tests/migrate/test_charter_encoding_migration.py` at the function seam the migration module exposes (the refusal when a `.bak` already exists). Commit this first.
  2. Planted break **P-5621-1**: set `cp1252_in_tied = False` in the charter-encoding detection (find with `grep -rn cp1252_in_tied src/`); run `tests/migrate/test_charter_encoding_migration.py` → RED (expect ≥7 failed). Revert.
  3. Planted break **P-5621-2**: disable the pre-existing-backup refusal; the ported test must go RED. Revert.
  4. `git rm tests/regressions/test_issue_4962_charter_encoding.py` only if both breaks went RED on the migration unit file. If the file is listed in any registry (`pyproject.toml` lists `tests/regressions/*` in a ruff/format list — check with `git grep test_issue_4962`), update that registry in the same commit.

### Subtask T014 – RETIRE T030 in the status-event row-shape test
- **Purpose**: #5621 Do 4 — T030 is a special case of T032 in `tests/specify_cli/audit/test_status_event_row_shape.py`.
- **Steps**: planted break **P-5621-3**: remove `review_result` from the shape registry (find the registry the test imports); both T030 and T032 must go RED. Revert. Then delete T030 and its module-docstring bullet; T032 becomes MARKER-ONLY (drop `regression`).

### Subtask T015 – Validate and record evidence
- Run the Validation block on all nine files; record per-file before/after `-m regression` counts and P-5621-1..3.

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

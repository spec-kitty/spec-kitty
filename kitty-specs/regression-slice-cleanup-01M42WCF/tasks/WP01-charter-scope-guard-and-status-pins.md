---
work_package_id: WP01
title: Charter scope-config guard and status/coordination pins (#5620 part 1)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-008
- C-001
- C-005
- SC-001
planning_base_branch: issue-5618-regression-slice-cleanup
merge_target_branch: issue-5618-regression-slice-cleanup
branch_strategy: Planning artifacts for this mission were generated on issue-5618-regression-slice-cleanup. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5618-regression-slice-cleanup unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-regression-slice-cleanup-01M42WCF
base_commit: 8de885a685e5ca2093e56dcd0678205aeb79058d
created_at: '2026-10-04T07:29:00.688296+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Ledger follow-through (#5620)
history:
- at: '2026-10-04T07:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/charter/
create_intent:
- tests/charter/test_charter_scope_config_reader.py
execution_mode: code_change
model: sonnet
owned_files:
- tests/charter/test_charter_scope_config_reader.py
- tests/next/test_cli_boundary_scope_config_4600.py
- tests/coordination/test_commit_router_coord_only_dirty_status_log.py
- tests/core/test_mission_create_coord_status_placement.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Charter scope-config guard and status/coordination pins (#5620 part 1)

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

- **Goal**: Guard the #4600 fix at its seam (the only unguarded fix in the slice), then retire or unmark the CLI replay that cannot guard it, retire the folded #5513 file, and FIX+unmark the #5440 file.
- **Independent test**: Planting `return None` in place of `raise CharterPackConfigError` in `src/charter/activation/scope.py::_load_charter_scope_config` turns the new unit test file red.
- **Issue**: #5620 — read the full issue body (ledger + planted-break table) before starting: `https://github.com/spec-kitty/spec-kitty/issues/5620`.
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

Implement command: `spec-kitty agent action implement WP01 --agent claude --mission regression-slice-cleanup-01M42WCF`

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

### Subtask T001 – Add the `_load_charter_scope_config` unit test (priority, red-first)
- **Purpose**: #5620 item 1 — the reader is unguarded: `tests/next/test_cli_boundary_scope_config_4600.py` stays green when the fix is reverted and `tests/charter/test_charter_scope_traversal.py` mocks the reader.
- **Steps**:
  1. Read `src/charter/activation/scope.py` (`_load_charter_scope_config`, ~line 253). Contract: absent `.kittify/config.yaml` → `None`; unreadable / non-UTF-8 / malformed YAML → `CharterPackConfigError` whose message names the config path; non-dict YAML → default `CharterScopeConfig()`; dict → validated config.
  2. Create `tests/charter/test_charter_scope_config_reader.py` (markers: `pytestmark = [pytest.mark.fast, pytest.mark.unit]` — check `tests/charter/` siblings and match). Use `tmp_path` as `repo_root`; write bytes directly (`b"\xff\xfe not utf-8"`) for the non-UTF-8 case and `"scopes: [unclosed"` for malformed YAML.
  3. Cases: non-UTF-8 → raises, message contains the config path; malformed YAML → raises, message contains the path; absent file → `None`; non-dict YAML (e.g. `- a`) → default config; a valid dict → validated config (positive control on the same fixture shape).
  4. Planted break **P-5620-1**: replace the `raise CharterPackConfigError(...)` with `return None`; the two error cases must go RED. Revert. Record.
- **Files**: `tests/charter/test_charter_scope_config_reader.py` (new, ~60 lines).
- **Notes**: Do not mock the reader or `yaml`; it is a pure file reader — real files at `tmp_path` are the boundary.

### Subtask T002 – Retire or unmark the #4600 CLI replay
- **Purpose**: the CLI replay does not guard its own fix (it stays green on P-5620-1).
- **Steps**:
  1. Re-run P-5620-1 against `tests/next/test_cli_boundary_scope_config_4600.py` to confirm it stays GREEN (record it).
  2. Read the file. If it still pins a CLI-boundary behaviour the unit test does not (e.g. the CLI renders the error as a clean exit rather than a traceback), keep it and drop only `regression` (MARKER-ONLY). If it pins nothing beyond the reader, retire it — the covering guard is T001's file, proven RED on P-5620-1.
  3. Prefer MARKER-ONLY unless the file is clearly redundant; record the decision and reason in the Activity Log.
- **Files**: `tests/next/test_cli_boundary_scope_config_4600.py`.

### Subtask T003 – RETIRE the #5513 coord-only dirty status-log file
- **Purpose**: #5620 item 2 — `tests/coordination/test_commit_router_coord_only_dirty_status_log.py` (19 s) is folded into `tests/coordination/test_commit_router.py::test_router_never_reports_a_coord_only_dirty_status_log_as_unchanged` and the unit `test_act_on_stage_plan_translates_a_log_with_mission_slug_via_write_dir`.
- **Steps**:
  1. Confirm both covering tests exist (`grep -n` in `tests/coordination/`).
  2. Planted break **P-5620-2**: break the translate step in `_act_on_stage_plan` (find it with `grep -rn "def _act_on_stage_plan" src/`) so a log carrying the mission slug is not translated via the write dir. Run the two covering tests AND the file to retire; the covering tests must be RED. Revert.
  3. If RED: `git rm` the file. If GREEN: keep it, MARKER-ONLY, and record.
- **Files**: `tests/coordination/test_commit_router_coord_only_dirty_status_log.py` (delete). `tests/coordination/test_commit_router.py` is read-only here.

### Subtask T004 – FIX + unmark the #5440 coord status placement file
- **Purpose**: #5620 item 3 — `tests/core/test_mission_create_coord_status_placement.py` passes; its "stays red on main" docstring is false. It is a cheap permanent guard.
- **Steps**:
  1. Planted break **P-5620-3**: force the status log into `scaffold_paths` in the mission-create code (find the coord-status placement in `src/specify_cli/core/mission_creation.py`); the test must go RED. Revert.
  2. Drop `regression`; keep/add the tier marker its `tests/core/` siblings use.
  3. Rewrite the docstring: defect #5440 is fixed; this is a permanent guard.
- **Files**: `tests/core/test_mission_create_coord_status_placement.py`.

### Subtask T005 – Validate and record evidence
- Run the Validation block. Append P-5620-1..3 rows to the Activity Log. Record the before/after `-m regression` count of the four files and the durations of the retired file.

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

---
work_package_id: WP02
title: Materialize, charter-activate and release changelog route through the Mission predicate
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
- FR-006
- FR-007
- FR-009
- NFR-001
- SC-002
- SC-004
planning_base_branch: issue-6758-kitty-specs-walkers-mission-predicate
merge_target_branch: issue-6758-kitty-specs-walkers-mission-predicate
branch_strategy: Planning artifacts for this mission were generated on issue-6758-kitty-specs-walkers-mission-predicate. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6758-kitty-specs-walkers-mission-predicate unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
- T010
- T011
phase: Phase 2 - Remaining read surfaces
history:
- at: '2026-10-30T17:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/materialize.py
- src/specify_cli/charter_activate.py
- src/specify_cli/release/changelog.py
- tests/specify_cli/cli/commands/test_materialize.py
- tests/cli/test_charter_activate_warning.py
- tests/release/test_release_prep.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Materialize, charter-activate and release changelog route through the Mission predicate

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

## Objectives & Success Criteria

Three more read surfaces stop deciding "is this a Mission?" for themselves:

1. `_mission_dirs_to_process` (`materialize`, `src/specify_cli/cli/commands/materialize.py`)
2. `_collect_inflight_missions` (charter-activate in-flight warning, `src/specify_cli/charter_activate.py`)
3. `build_changelog_block` (release changelog, `src/specify_cli/release/changelog.py`)

Done means: on the shared fixture (WP01's `tests/_support/mission_residue_fixture.py`) each surface
yields the Mission and not the residue child; the existing tests of all three test files still pass; and
each new test was seen red before its walker changed.

## Context & Constraints

- Mission spec FR-004, FR-005, FR-006, FR-007, FR-009; plan IC-01 and its per-walker table; data model's
  "Per-walker output contract".
- The predicate already exists: `is_selectable_mission_dir(path, *, repo_root, tracked=...)` with
  `TrackedMissionPaths(repo_root)` as the per-walk memo. Follow the pattern in
  `src/specify_cli/cli/commands/_mission_type_audit.py::audit_mission_types`.
- **Do not** route through `FsMissionResolver` (it needs a `mission_id` and would hide legacy Missions),
  change the predicate's rules, or touch `src/specify_cli/audit/engine.py` (#6757).
- Keep each walker's posture (C-003): `materialize` keeps its dot-directory skip and its `errors[]`
  contract; `_collect_inflight_missions` keeps its best-effort scan; `build_changelog_block` keeps its
  date/tag filtering and markdown rendering.

## Branch Strategy

- **Strategy**: feature branch, single-branch mission topology.
- **Planning base branch**: `issue-6758-kitty-specs-walkers-mission-predicate`
- **Merge target branch**: `issue-6758-kitty-specs-walkers-mission-predicate`

## Subtasks & Detailed Guidance

### Subtask T007 – Red-first tests for the three surfaces

- **Purpose**: pin behaviour before the change.
- **Files**: `tests/specify_cli/cli/commands/test_materialize.py`,
  `tests/cli/test_charter_activate_warning.py`, `tests/release/test_release_prep.py`.
- **Steps**: each test uses `seed_mission_and_residue(tmp_path)` from
  `tests/_support/mission_residue_fixture.py` and asserts both halves on that one fixture:
  - `test_mission_dirs_to_process_skips_residue` — `[slug for slug, _ in _mission_dirs_to_process(repo_root, repo_root / "kitty-specs", errors)] == [MISSION_SLUG]` and `errors == []`.
  - `test_collect_inflight_missions_skips_residue` — the returned `AffectedMission` slugs are `{MISSION_SLUG}` (both children carry an in-flight `WP02` event, so a local rule would return both).
  - `test_changelog_excludes_residue_folder` — `slug in slugs` for the Mission and `RESIDUE_SLUG not in slugs` (both children carry an accepted `WP01`, so a local rule would include both).
- **Run them against the unchanged code and record the failures**; keep the failing output for the PR.
- Extend `test_mission_dirs_to_process_skips_residue` with the NFR-001 probe-cost assertion: a counter on
  the memo's probe (`specify_cli.context.mission_resolver.tracked_mission_paths`) must record exactly one
  call for the shared fixture and zero for a fixture whose every child carries a `mission_id`.

### Subtask T008 – `materialize` processes Missions only

- **Files**: `src/specify_cli/cli/commands/materialize.py`.
- **Steps**: in `_mission_dirs_to_process`, build one `TrackedMissionPaths(repo_root)` and add
  `is_selectable_mission_dir(root_dir, repo_root=repo_root, tracked=tracked)` to the existing generator
  (keep `is_dir()`/dot-directory checks as they are). A residue child must produce neither a target nor
  an `errors[]` entry, so no `_status_dir_for` (and therefore no coordination-worktree probe) runs for it.
  Extend the docstring by one sentence.
- **Validation**: the new test plus the file's existing tests.

### Subtask T009 – Charter-activate in-flight scan walks Missions only

- **Files**: `src/specify_cli/charter_activate.py`.
- **Steps**: in `_collect_inflight_missions`, derive `repo_root = mission_specs_dir.parent`, build one
  memo, and skip a child the predicate rejects before `_inflight_missions_for` reads its log. Keep the
  `not mission_specs_dir.is_dir()` early return and the best-effort except posture. Docstring: one
  sentence on read-side residue.
- **Validation**: the new test plus `tests/cli/test_charter_activate_warning.py` in full.

### Subtask T010 – Release changelog lists Missions only

- **Files**: `src/specify_cli/release/changelog.py`.
- **Steps**: filter the sorted `mission_dirs` list in `build_changelog_block` through the predicate with
  one memo per call, before the per-mission loop; keep everything else identical. Docstring: one sentence.
- **Validation**: the new test plus `tests/release/test_release_prep.py` and
  `tests/regressions/test_changelog_regex_redos.py`.

### Subtask T011 – Blast radius

- **Steps**: run and record:
  - `uv run pytest tests/specify_cli/cli/commands/test_materialize.py tests/cli/test_charter_activate_warning.py tests/release/test_release_prep.py tests/regressions/test_changelog_regex_redos.py -q`
  - `uv run pytest tests/release tests/cli -q` (the two owning subsystem directories; keep it to these,
    `NO_FULL_HEAVY_SUITES_IN_MISSION`)
  - `uv run ruff check` and `uv run ruff format --check` on the three source and three test files.

## Test Strategy

- Red first; do not edit an assertion to make a walker-local rule pass.
- Both halves on one fixture (positive control for every absence assertion).
- Real git in the fixture, so git-aware read-side residue is actually exercised.

## Risks & Mitigations

- **Materialize side effects**: a residue child previously triggered a coordination-worktree probe and an
  `errors[]` entry; the test asserts `errors == []` so the change is visible.
- **Existing non-git fixtures** (`test_release_prep.py`, `test_charter_activate_warning.py`) write
  `meta.json` without `mission_id` in a plain `tmp_path`; the predicate treats them as Missions by file
  presence. Leave them alone — they are the regression guard.
- **Changelog date filtering**: keep the `since_tag` logic untouched; add only the filter.

## Review Guidance

- Each walker has exactly one new predicate call and one new memo, no second rule.
- No behaviour change for a selectable Mission (existing tests green).
- No audit-engine or predicate-semantics change.

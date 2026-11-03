---
work_package_id: WP01
title: "Make the #4891 accept pin's two controls a Mission apart only by lanes.json"
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6859-accept-pin-fixture
merge_target_branch: issue-6859-accept-pin-fixture
branch_strategy: Planning artifacts for this mission were generated on issue-6859-accept-pin-fixture. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6859-accept-pin-fixture unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-issue-6859-accept-pin-fixture-01M6GS08
base_commit: 6cd0603418c0d890d823eb2ca401e4330623581d
created_at: '2026-11-03T13:21:31.865873+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Fixture
history:
- at: '2026-11-03T13:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/cli/commands/
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py
- docs/changelog/unreleased/*.internal.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6859'
---

# Work Package Prompt: WP01 – Make the #4891 accept pin's two controls a Mission apart only by `lanes.json`

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter before
parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

---

## Objectives & Success Criteria

- `tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py` reports `2 passed` on
  a clean checkout, and the positive control is green for the intended reason: the fixture is an
  acceptable Mission and the only thing added is `lanes.json` + a passing acceptance matrix.
- Both controls are built by one module-level builder (`_build_accept_ready_mission`) that does
  **not** write `lanes.json`; only the positive control adds the manifest, the matrix and WP01's
  lane implementation commit.
- Every pre-existing assertion of the pin is byte-identical: `git diff` on the file shows no
  change to any `assert` line and no marker change.
- Removing each of the three fixture parts in turn turns the positive control red with the
  matching evidence code (`IMPLEMENTATION_UNREADABLE`, `IMPLEMENTATION_MISSING`,
  `REVIEW_NOT_INDEPENDENT`) — the non-vacuity proof for SC-002.
- A changelog fragment exists at `docs/changelog/unreleased/<pr>.internal.md`, shaped per
  `docs/changelog/unreleased/README.md`.

Success: FR-001, FR-002, FR-003; NFR-001, NFR-002, NFR-003; C-001, C-002, C-003; SC-001,
SC-002, SC-003.

## Context & Constraints

- Read `kitty-specs/issue-6859-accept-pin-fixture-01M6GS08/spec.md` and `plan.md` first.
- **Which side is wrong.** `accept` refuses an approved work package with no readable evidence
  window, no owned change in the window, or no independent approval —
  `src/specify_cli/consolidation/wp_evidence.py` (`_scan_lane`, `_judge`) and
  `src/specify_cli/consolidation/preflight.py::_independent_reviewer_confirmed`. That is
  deliberate fail-closed product behaviour with its own tests. The pin's *fixture* predates all
  three axes: `_create_test_feature` declares no `owned_files` and seeds one forced
  `planned -> done` hop under a single actor, and `write_single_lane_manifest` records a
  `planning_commit_sha` whose lane branch was never created. The fixture is the side that is
  wrong; fix it, never the assertion.
- Do **not** edit `tests/specify_cli/test_acceptance_regressions.py::_create_test_feature` — about
  thirty-five call sites share it. Call it with `omit_status_events=True` and seed the lifecycle
  locally in the pin's module.
- The evidence axis reads **authored frontmatter** only (`_owned_patterns_by_wp`), so
  `owned_files` must be declared in `tasks/WP01-test.md`. A `write_scope` in `lanes.json` does
  not stand in for it.
- `tests/lane_test_utils.commit_lane_implementation(repo_root, feature_dir, path=...)` reads
  `lanes.json`, so it can only run in the positive control, after the manifest exists; its
  `path` must match the declared `owned_files` glob (`src/wp01.py` under `src/**`).
- Status events must be seeded through `tests._support.status_seed.seed_status_event` and
  materialized with `specify_cli.status.reducer.materialize`; an `event_id` outside the ULID
  alphabet (no `I`, `L`, `O`, `U`) makes the store drop the line.
- `test_accept_clean_tree.py` already builds this exact shape for the same gate — reuse its
  pattern (claim with `build_claim_policy_metadata`, approval by a distinct actor, then done)
  instead of inventing a third fixture shape.
- Never skip, xfail, delete or rename the test, and never weaken a gate to make it pass.
- Never run a full heavy suite locally (`NO_FULL_HEAVY_SUITES_IN_MISSION`); run the affected file
  and the adjacent modules below. CI owns the wide sweep.

## Branch Strategy

- **Strategy**: planning artifacts were generated on `issue-6859-accept-pin-fixture`; completed
  changes merge back into it. That branch is the pull request's head against `main`.
- **Planning base branch**: `issue-6859-accept-pin-fixture`
- **Merge target branch**: `issue-6859-accept-pin-fixture`

## Subtasks & Detailed Guidance

### T001 – Read the three gates, record which refuse today's fixture

- **Purpose**: repair the fixture completely rather than tuning it to the first error message.
- **Steps**: read `src/specify_cli/consolidation/wp_evidence.py` (`_scan_lane`, `_judge`,
  `has_owned_change`, `_owned_patterns_by_wp`) and
  `src/specify_cli/consolidation/preflight.py::_independent_reviewer_confirmed`. Record in the
  PR body which code each axis would emit for this fixture, and why the product behaviour is
  correct.
- **Files**: none (reading).
- **Notes**: the red-first evidence is the pre-change run of the pin on pristine `main`:
  `1 failed, 1 passed`, `assert result.exit_code == 0` with `IMPLEMENTATION_UNREADABLE`.

### T002 – The shared accept-ready fixture builder

- **Purpose**: both controls start from one Mission, so the positive control cannot drift into a
  different fixture shape than the negative control.
- **Steps**: add `_build_accept_ready_mission(tmp_path) -> tuple[Path, Path]` to the pin module:
  call `_create_test_feature(tmp_path, _MISSION_SLUG, omit_status_events=True)`; overwrite
  `tasks/WP01-test.md` with frontmatter that includes `owned_files: [src/**]`; `git branch -M
  _WORK_BRANCH` and repoint `meta.json`'s `target_branch`/`mission_id`/`mid8` (the existing
  protected-branch sidestep, unchanged in intent); seed `planned -> claimed` (implementer actor,
  `build_claim_policy_metadata`), `claimed -> approved` (a distinct reviewer actor),
  `approved -> done`, then `materialize`; commit everything so the tree is clean. It must **not**
  write `lanes.json`.
- **Files**: `tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py`.
- **Notes**: keep the helper's docstring explicit about *why* each part exists (an axis a landing
  surface reads), so a future reader cannot mistake it for ceremony and delete it.

### T003 – The positive control adds the manifest, the matrix and the evidence

- **Purpose**: the positive control differs from the negative one by `lanes.json` only.
- **Steps**: negative control calls the builder and asserts nothing more; positive control calls
  the builder, then `write_single_lane_manifest(..., target_branch=_WORK_BRANCH)`,
  `write_acceptance_matrix(feature_dir, _passing_acceptance_matrix(_MISSION_SLUG))`, commit, then
  `commit_lane_implementation(repo_root, feature_dir, path="src/wp01.py")`.
- **Files**: `tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py`.
- **Notes**: leave both test bodies' assertions exactly as they are; the only new lines are
  fixture setup.

### T004 – Non-vacuity, half by half

- **Purpose**: prove the repaired positive control can fail for each axis it now satisfies.
- **Steps**: for each experiment, revert exactly one fixture part, run the file, record the
  failure code, restore:
  1. drop the `commit_lane_implementation` call -> `IMPLEMENTATION_UNREADABLE` (already observed
     pre-change);
  2. keep the commit but drop the `owned_files` declaration -> `IMPLEMENTATION_MISSING`;
  3. keep both but remove the independent approval (approve as the implementer) ->
     `REVIEW_NOT_INDEPENDENT`.
- **Files**: none (temporary edits, restored).
- **Notes**: delete any experiment leftovers; `git status` must be clean of them before commit.

### T005 – Changelog fragment, targeted run, self-review

- **Purpose**: leave the record the PR body needs.
- **Steps**: add `docs/changelog/unreleased/<pr>.internal.md` (PR number once known; tests-only
  change is not user-facing) in the shape `docs/changelog/unreleased/README.md` requires; run the
  commands under **Test Strategy**; re-read the diff for changed assertions, a modified shared
  helper, or a skipped/marked test.
- **Files**: `docs/changelog/unreleased/<pr>.internal.md`.
- **Notes**: never edit `docs/changelog/CHANGELOG.md`; `check_changelog_style` rejects the old
  `[Unreleased]` shape.

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py -q
uv run --frozen pytest tests/specify_cli/cli/commands/test_accept_clean_tree.py -q
uv run --frozen pytest tests/specify_cli/test_acceptance_regressions.py -q
uv run --frozen ruff check tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py
uv run --frozen ruff format --check --force-exclude tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py
uv run --frozen mypy tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py
```

Red-first evidence: the pre-change run of the pin on pristine `main` (`1 failed, 1 passed`,
`IMPLEMENTATION_UNREADABLE`). Record it verbatim in the PR body, together with the T004
half-by-half results.

## Risks & Mitigations

- **A fixture that is green because a gate was relaxed.** No product code is touched and no
  assertion changes; T004 proves each axis still refuses when its fixture part is removed.
- **The shared helper moves under thirty-five other call sites.** Not edited; only called with a
  documented option (`omit_status_events=True`).
- **Duplicate or contradictory status history.** The helper omits its own events, so the module
  seeds the lifecycle exactly once.
- **A false red from the shared machine.** Reproduce on pristine `origin/main` in a clean
  worktree before attributing any failure to this diff, then report it in `## Deferred`.

## Review Guidance

- Are all pre-existing `assert` lines in the pin byte-identical?
- Do both controls come from `_build_accept_ready_mission`, with `lanes.json` written only by the
  positive control?
- Does the fixture declare `owned_files`, commit WP01's change on the **lane** branch, and record
  an approval by an identity distinct from the implementer?
- Is `_create_test_feature` unmodified? Is `src/` untouched?
- Is the changelog a fragment (not a `CHANGELOG.md` edit), and does its shape match the README?

## Progress & Status

Progress, history and status live in the status event log — never in this file.

- `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- `spec-kitty agent tasks move-task WP01 --to <status>`
- `spec-kitty agent tasks status`

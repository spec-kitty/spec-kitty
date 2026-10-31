---
work_package_id: WP02
title: Lane collector requests exact files and reports the truth
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-003
- FR-004
- NFR-001
- C-003
- SC-001
- SC-002
planning_base_branch: issue-6750-lane-auto-commit-directory-expansion
merge_target_branch: issue-6750-lane-auto-commit-directory-expansion
branch_strategy: Planning artifacts for this mission were generated on issue-6750-lane-auto-commit-directory-expansion. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6750-lane-auto-commit-directory-expansion unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-lane-auto-commit-directory-expansion-01M67HVC
base_commit: 35a56150ad67d9f66f9d1212a295beec6a7d726b
created_at: '2026-10-31T02:11:37.103185+00:00'
subtasks:
- T005
- T006
- T007
- T008
- T009
phase: Phase 2 - Lane collector
history:
- at: '2026-10-30T23:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/specify_cli/cli/commands/agent/test_mt_lane_deliverable_directory_6750.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/agent/tasks_move_task.py
- src/specify_cli/cli/commands/agent/tasks_move_task_gates.py
- tests/specify_cli/cli/commands/agent/test_mt_lane_deliverable_directory_6750.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6750'
---

# Work Package Prompt: WP02 – Lane collector requests exact files and reports the truth

## Do This First: Load Agent Profile

Load `packs/built-in/agent_profiles/python-pedro.agent.yaml` and follow it.

Mission: `lane-auto-commit-directory-expansion-01M67HVC`. Read `../spec.md`,
`../plan.md`, `../research.md`, the issue spec-kitty/spec-kitty#6750, and WP01's prompt
(`WP01-preflight-refuses-directory-paths.md`) — WP01's refusal is the backstop you are
fixing the caller for.

## The defect (reproduced on main 512567eee7)

`_mt_commit_lane_deliverables` reads `status_entries(worktree_path, untracked=None)`.
With the repository's default `status.showUntrackedFiles=normal`, a new directory is
**one collapsed entry** (`?? .zig-cache/`). `_lane_deliverable_paths` forwards that
directory, `safe_commit` stages/commits its children, and then
`_assert_committed_paths_requested` compares the committed **files** against the literal
**directory** and raises `SafeCommitUnrequestedPaths` — whose message states a
pre-commit hook did it. The collector's `except Exception` then prints "could not
auto-commit", so a landed commit reads as an untouched failure.

Verified repro (issue body, re-run on main): HEAD advanced, both children committed,
empty hook directory, message blames a hook, warning says "could not auto-commit".

## Objectives & Success Criteria

### T006 — expand untracked entries in the collector (FR-001, NFR-001, SC-001)

- In `_mt_commit_lane_deliverables`, read `status_entries(worktree_path, untracked="all")`
  so every untracked **file** is its own entry — the same expansion rule the public
  `safe-commit` CLI uses (`safe_commit_cmd._worktree_status_entries`), not a new helper.
- Keep `_lane_deliverable_paths`' contract (absolute paths, rename/copy both sides,
  #5401) and `_drop_lane_coord_residue` (#2549) untouched.
- Align the sibling caller `tasks_move_task_gates._mt_pre_review_dirty_paths`, which
  feeds the same helper and today also sees collapsed directories: it should return the
  files too (its own docstring says "deliverable paths"). One-line change plus a
  comment pointing at the shared rule; do not restructure that module.
- NFR-001: a clean auto-commit must not gain a git round trip. The status probe is the
  same single invocation with a different flag; assert this in T009 rather than by
  inspection.

### T007 — report a landed commit truthfully (FR-004, SC-002)

- Import `SafeCommitRecoveryFailed` and catch it **before** the generic `except
  Exception` arm in the collector. It is raised only after HEAD moved and carries
  `commit_sha`/`destination_ref`: print a warning that says the commit
  landed, names the SHA and the ref, and then why it is being reported (for example
  `Warning: committed lane deliverables for WP01 on <ref> as <sha>, but <reason>`).
- Reserve the current "could not auto-commit lane deliverables for <WP>: <reason>"
  wording for failures that did not land a commit.
- Keep it best-effort: the readiness guard stays authoritative, so do not raise or
  abort the move from this arm. `st.json_output` keeps suppressing console output.
- Do not change `SafeCommitUnrequestedPaths`' type, code or message shape (C-002).
  After T006 the only genuine cause of an extra path is an external stager, so its
  wording becomes true again — pin that in T008 instead of rewording it.

### Tests — new file `tests/specify_cli/cli/commands/agent/test_mt_lane_deliverable_directory_6750.py`

Write T005 **first** and watch it fail on today's code (it will: the warning blames a
hook and says "could not").

- **T005 — the issue's fixture (SC-001)**: git fixture on a branch, `core.hooksPath`
  pointing at an **empty** directory, one committed README, then untracked
  `.zig-cache/one.bin` and `.zig-cache/two.bin`. Drive the **real**
  `_mt_commit_lane_deliverables` (build a real `_MoveTaskState` as
  `tests/specify_cli/cli/commands/agent/test_mt_lane_coord_residue_2549.py` does, and
  monkeypatch `_tasks.resolve_workspace_for_wp` to a `ResolvedWorkspace` whose
  `worktree_path` is the fixture). Use `json_output=False` and `capsys` so the console
  text is assertable. Assert: exactly one new commit; its changed-path set is exactly
  the two children; working tree clean; output contains no "pre-commit hook" and no
  "could not auto-commit", and does say it committed. Also add a modified-but-unrelated
  tracked file to the fixture and assert it is **not** in the commit and stays dirty.
- **T008 — genuine hook negative control (FR-003, SC-002)**: same shape of fixture but
  with a real `pre-commit` hook that runs `git add -u`, plus an unrelated modified
  tracked file. Assert the collector reports a landed commit with the SHA and that the
  swept path is named and the requested paths are not blamed. Assert the exception path
  itself at the seam level (`SafeCommitUnrequestedPaths`, its `error_code` and
  `extra_paths`) so the guard provably did not go vacuous.
- **T009 — no extra git round trip (NFR-001)**: wrap `subprocess.run` (or the
  `kernel.git` runner the code actually uses) with a counter and assert a clean
  auto-commit issues the same number of git invocations as the pre-change behaviour for
  the status probe — i.e. the probe is one invocation and the refusal path issues none.
  If counting is brittle, assert the collector's own probe is called once and that the
  preflight refusal path is filesystem-stat-only (call it directly with a directory and
  assert zero git calls).

Half-by-half proof: reverting T006 alone must turn T005 red (hook text / wrong outcome);
reverting T007 alone must turn the landed-report assertions in T005/T008 red.

### Changelog

Add an `[Unreleased]` entry to `docs/changelog/CHANGELOG.md` (the root `CHANGELOG.md`
is a symlink to it): bold impact-first lead with `(#6750)`, then before/after, under
1,200 characters. Follow the surrounding entries' shape; do not reflow unrelated text.

## Branch Strategy

- Planning branch / final merge target: `issue-6750-lane-auto-commit-directory-expansion`.
- Execution worktrees come from `lanes.json`; never build a workspace path by hand.

## Definition of Done

- T005/T008/T009 fail before their change and pass after; the half-by-half proof above
  holds (record it in the WP history).
- `uv run pytest tests/specify_cli/cli/commands/agent/test_mt_lane_deliverable_directory_6750.py -q`
  green, plus the neighbouring suites that pin this collector:
  `tests/specify_cli/cli/commands/agent/test_mt_lane_coord_residue_2549.py`,
  `tests/specify_cli/cli/commands/agent/test_agent_git_paths.py`,
  `tests/specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_gate_observability.py`,
  `tests/tasks/test_move_task_git_validation_unit.py`, and any
  `tests/architectural/test_no_write_side_rederivation.py` entry that names this
  collector. Adjust paths to what the tree actually holds; do not run the full suite.
- `uv run ruff check src/specify_cli/cli/commands/agent/ tests/specify_cli/cli/commands/agent/` clean.
- No `# type: ignore` added, no `--no-verify`, no weakened assertion.

## Risks

- Expanding untracked files can enumerate a large tree in an unusual lane. That is the
  CLI's existing behaviour; do not add a cap or an ignore-list policy (C-003).
- Do not re-enable the `.gitignore` "mitigation": the fix is the seam contract, not a
  repository-local ignore file.
- The collector has two other guards (owned-scope `OWNED_DELIVERABLE_SCOPE_REFUSED`,
  coord residue #2549). Both must keep passing unchanged.

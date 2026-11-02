---
work_package_id: WP01
title: Re-pin the move-task fixtures refused by the owned-file evidence gate
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-7057-move-task-evidence-fixture-repin
merge_target_branch: issue-7057-move-task-evidence-fixture-repin
branch_strategy: Planning artifacts for this mission were generated on issue-7057-move-task-evidence-fixture-repin. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7057-move-task-evidence-fixture-repin unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Test remediation
history:
- at: '2026-11-02T17:15:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/tasks/
create_intent:
- docs/changelog/unreleased/7057-move-task-evidence-fixtures.internal.md
execution_mode: code_change
model: ''
owned_files:
- tests/tasks/test_move_task_git_validation_unit.py
- docs/changelog/unreleased/7057-move-task-evidence-fixtures.internal.md
role: implementer
tags: []
task_type: implement
---

# Work Package Prompt: WP01 – Re-pin the move-task fixtures refused by the owned-file evidence gate

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Issue #7057: on `origin/main` `9aed3a8012`, 8 of the 15 nodes in
`tests/tasks/test_move_task_git_validation_unit.py` are refused by #6715's owned-file
evidence gate before they reach the behaviour they test. The gate is right; the module's
`git_repo_with_worktree` fixture is stale — its WP01 declares **no `owned_files`** and its
lane branch commits an unowned root `implementation.txt`. Re-pin the fixture so the gate
passes on honest evidence, and name the approver the independence gate requires for a
`done` move. **No production code changes**, and no test is skipped, xfailed, deselected,
retried or loosened.

## Context

- `research.md` (mission dir) has the reproduction, the exact failing node ids, the gate's
  call chain (`_mt_require_implementation_evidence` → `_mt_require_lane_evidence` →
  `wp_evidence.has_owned_change`) and why an empty `owned_files` pattern list can never
  match.
- The gate reads ownership from the **authored WP frontmatter**
  (`read_authored_wp_frontmatter(...).owned_files`, normalized by
  `wp_evidence.owned_patterns`); `lanes.json`'s `write_scope` is `src/**` through
  `write_single_lane_manifest` in `tests/lane_test_utils.py`, so an owned deliverable
  belongs under `src/`.
- `test_move_to_done_with_override_reason_succeeds_when_unmerged` moves to `done`, an
  approval lane: #6715's `_mt_require_independent_approval` refuses a placeholder
  approver, so the invocation must pass a non-generic `--agent`.
- The remaining done-transition nodes use `--force`, which both gates skip by design
  (operator ruling 3); leave them alone.

## Detailed Guidance

### Subtask T001 – Capture the red-first proof

On the planning base (`git rev-parse origin/main` or the branch point, `9aed3a8012`), run:

```bash
uv run --frozen pytest -q -p no:randomly -n0 tests/tasks/test_move_task_git_validation_unit.py
```

Record the result (expected: 8 failed, 7 passed) and paste the failing node list and one
`IMPLEMENTATION_MISSING` payload into the Activity Log and the PR's Tests-run section.

### Subtask T002 – Fixture ownership and owned commit

In `git_repo_with_worktree` (`tests/tasks/test_move_task_git_validation_unit.py:42`):

1. Add `owned_files:\n  - "src/**"` to the WP01 task-file frontmatter string, with a
   Python comment above `task_content` explaining that #6715's review-ward evidence gate
   refuses a WP with no owned change in the lane's window, so the declaration is
   load-bearing and must not be deleted.
2. Replace the root `implementation.txt` lane commit with `src/implementation.py`
   (`IMPLEMENTED = True`), keeping the commit subject `Add implementation` (another node
   asserts it). Create the `src/` directory before writing.

Do not touch the planning-commit bookkeeping (`write_single_lane_manifest`), the seeded
status events, or any assertion.

### Subtask T003 – Name the approver in the done-override node

In `test_move_to_done_with_override_reason_succeeds_when_unmerged`, add
`"--agent", "reviewer-renata"` to the `move-task` invocation (with a one-line comment
saying that a `done` move is an approval and #6715 refuses a placeholder approver). Do not
add `--force`: the node must prove the done-override path, not dodge the gate.

### Subtask T004 – Re-run the module and the neighbouring surfaces

- `uv run --frozen pytest -q -p no:randomly -n0 tests/tasks/test_move_task_git_validation_unit.py` → expect 15 passed.
- `uv run --frozen pytest -q -p no:randomly -n0 tests/tasks` → the directory stays green.
- `uv run --frozen pytest -q tests/integration/test_6715_lane_autowalk_guards.py tests/integration/test_6715_squad_identity_and_evidence.py` → unchanged, proving the gate is not weakened.
- `uv run --frozen pytest -q tests/agent/test_review_validation_unit.py` (shares `write_single_lane_manifest`) → green.

Do **not** run a full heavy suite (`NO_FULL_HEAVY_SUITES_IN_MISSION`).

### Subtask T005 – Internal changelog fragment

Create `docs/changelog/unreleased/7057-move-task-evidence-fixtures.internal.md` (rename it
to `<pr>.internal.md` once the PR number exists — the fragment's `<id>` is the PR number
once known; `docs/changelog/unreleased/README.md` is the shape authority). One entry, no
heading, bold lead, `(#7057)` reference, under 1,200 characters, describing the test-only
remediation. Then:

```bash
uv run --frozen python -m scripts.docs.check_changelog_style
uv run --frozen python -m scripts.docs.check_spelling --pass unreleased
```

### Subtask T006 – Scope discipline and node-set check

- `git diff --stat <planning-base>..HEAD -- src/` must be empty (C-002).
- `uv run --frozen pytest --collect-only -q tests/tasks/test_move_task_git_validation_unit.py | tail -3` still reports 15 tests, and `git diff` shows no marker/`pytestmark` change.
- `uv run --frozen ruff check tests/tasks/test_move_task_git_validation_unit.py`, `uv run --frozen ruff format --check --force-exclude tests/tasks/test_move_task_git_validation_unit.py` and `uv run --frozen mypy tests/tasks/test_move_task_git_validation_unit.py` are clean (NFR-002).

## Branch Strategy

Planning branch `issue-7057-move-task-evidence-fixture-repin`, merge target the same
branch. Topology is `single_branch`: work in the repository root checkout, commit with the
mission-aware entry point on that branch, never push `main` and never hand-build a
worktree path.

## Test Strategy

Red first (T001, on the planning base). Then the module (T004), the directory, the two
#6715 integration files and the shared-helper agent test, plus lint/format/type and the
changelog style checks. Record every command and count in the Activity Log; the PR's
Tests-run section repeats them.

## Definition of Done

- SC-001: the module is 15 passed / 0 failed on the branch (8 failed / 7 passed on the base).
- SC-002: the fixture WP declares `owned_files` and its lane's `Add implementation` commit touches a matching path.
- SC-003: no `src/` diff against the planning base; the module still collects 15 nodes.
- SC-004: the #6715 gate tests are unchanged and green.
- NFR-002, C-001–C-003 hold: lint/format/type clean, no skip/xfail/force, one module plus one fragment.

## Risks & Mitigations

- **Wrong ownership shape** (deliverable outside `src/**`): the lane's `write_scope` is `src/**`, so the commit must be under `src/`; the prototype in `research.md` §6 verified 15/15.
- **Independence gate refusal** on the done node: pass a non-generic `--agent`; never `--force`.
- **Accidental gate weakening**: no assertion changes; the #6715 integration files must stay green and untouched.
- **Out-of-matrix blind spot**: per-PR CI does not run `tests/tasks`; the proof is the explicit local run, recorded in the PR, and the nightly shard that owns the directory.

## Review Guidance

Reviewer: check that (a) the gate is untouched and its refusal text/ordering unchanged,
(b) the fixture now models what `finalize-tasks` produces (ownership declared, commit
inside it), (c) no assertion, marker, skip, xfail or force was added, (d) the done node
still proves the override path rather than the independence gate, (e) the fragment is
`.internal.md` (test-only change) and its style is clean.

## Activity Log

- 2026-11-02T17:15:00Z – system – Prompt created.
- 2026-11-02T17:00:00Z – pi – T001 red first (planning base `9aed3a8012`): `uv run --frozen pytest -q -p no:randomly -n0 tests/tasks/test_move_task_git_validation_unit.py` → **8 failed, 7 passed**. Every failure led by `IMPLEMENTATION_MISSING: WP01 cannot move into review: no change to its owned_files in its evidence window <sha>..kitty/mission-017-test-feature-lane-a (lane-a)`. Failing nodes: `test_move_to_done_with_override_reason_succeeds_when_unmerged`, `test_move_to_for_review_persists_transition_event`, `test_move_to_for_review_fails_when_event_readback_is_blocked`, `test_move_to_for_review_still_validates`, `test_move_to_done_with_staged_but_uncommitted_fails`, `test_move_for_review_blocks_when_lane_branch_has_kitty_specs_commits`, `test_move_for_review_from_worktree_keeps_commit_history_unchanged`, `test_for_review_auto_commits_uncommitted_deliverables`.
- 2026-11-02T18:55:00Z – pi (python-pedro) – T002/T003 green: `git_repo_with_worktree` WP01 now declares `owned_files: ["src/**"]` matching the lane's `write_scope`, the lane's `Add implementation` commit writes `src/implementation.py` instead of an unowned root `implementation.txt`, and `test_move_to_done_with_override_reason_succeeds_when_unmerged` passes `--agent reviewer-renata` (a `done` move is an approval; #6715 refuses the placeholder approver). No assertion, marker or `--force` changed; `git diff` under `src/` is empty.
- 2026-11-02T19:20:00Z – pi – T004 verification: module **15 passed** (`-p no:randomly -n0`, 8.9s); `tests/tasks` **228 passed**; `tests/integration/test_6715_lane_autowalk_guards.py` **14 passed** (1414s, the accept/consolidate nodes are slow, not hung); `tests/integration/test_6715_squad_identity_and_evidence.py` **8 passed** (723s); `tests/agent/test_review_validation_unit.py` **9 passed**. The gate's own coverage is unchanged and green.
- 2026-11-02T19:25:00Z – pi – T005/T006: `docs/changelog/unreleased/7057-move-task-evidence-fixtures.internal.md` added (internal, test-only); `check_changelog_style` exit 0 with no finding on this fragment, `check_spelling --pass unreleased` exit 0. `pytest --collect-only` still reports **15 tests**; `ruff check` and `ruff format --check --force-exclude` clean; `mypy` reports the same **16 pre-existing** `no-untyped-def` errors as on the planning base (`git show 9aed3a8012:...`), zero new.
- 2026-11-02T19:55:00Z – pi – Review round 1 (independent reviewer `reviewer-renata` on model `gpt-6.1-sol`): **APPROVE**. Its checks: `git diff 8b065d044c..HEAD -- src/` empty; AST comparison against the planning-base module shows 15 identical test definitions, 66 identical assertions, unchanged decorators/markers (no skip/xfail/force added); 15 collected nodes match; the lane window's `src/implementation.py` is recognised as owned evidence; the diagnosis and the `--agent` choice were endorsed, `--force` correctly rejected; module 15 passed in 5.56s; changelog style/spelling clean; ruff clean. One non-blocking finding folded in this commit: the protective `owned_files` comment now also sits above `task_content` (the WP prompt's T002 asked for it there). Re-ran module after the fold: **15 passed** (107.9s) and `ruff check` clean.

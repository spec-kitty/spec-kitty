---
work_package_id: WP02
title: Handle-equivalence matrix seeds the mission type it runs
dependencies: []
requirement_refs:
- FR-004
- NFR-002
- NFR-003
planning_base_branch: kitty/nightly-reds-2026-10-03
merge_target_branch: kitty/nightly-reds-2026-10-03
branch_strategy: Planning artifacts for this mission were generated on kitty/nightly-reds-2026-10-03. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty/nightly-reds-2026-10-03 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-reds-2026-10-03-01M42RR1
base_commit: 035816f0018a86f8951f4fc13bb3c5386ab7ddef
created_at: '2026-10-04T06:20:36.331428+00:00'
subtasks:
- T005
- T006
- T007
phase: Phase 1 - Test repairs
history:
- at: '2026-10-04T06:16:20Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/missions/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/specify_cli/missions/test_handle_equivalence_matrix.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP02 – Handle-equivalence matrix seeds the mission type it runs

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

If this work package was returned from review, the feedback reference is in the status event log (`spec-kitty agent tasks status --mission nightly-reds-2026-10-03-01M42RR1`). Address every item before handing back.

---

## Objectives & Success Criteria

- `tests/specify_cli/missions/test_handle_equivalence_matrix.py::test_mission_run_identity_identical_across_handle_forms` passes for all three handle forms (`083-my-feature-01KTPKST`, `01KTPKST`, `083`) (FR-004).
- Every other test in the file keeps its outcome.
- Red on base `b2c466d7d1`: the baseline `mission run` exits 2 with `MISSION_TYPE_CONFLICT`.

## Context & Constraints

- Evidence and classification: `kitty-specs/nightly-reds-2026-10-03-01M42RR1/research/nightly-red-memo.md`.
- Spec and plan: `kitty-specs/nightly-reds-2026-10-03-01M42RR1/spec.md`, `plan.md`.
- **Hard rules (NFR-001, C-001)**: change only the files listed under `owned_files`. Do not edit anything under `src/`. Do not raise a budget or timeout, add a retry, or skip, xfail, deselect or delete a test. Keep every existing assertion except the stale literal you are replacing (NFR-002).
- **Test runs (C-003)**: run only the named node ids or the named file, in the foreground, serially:
  `PWHEADLESS=1 <repo>/.venv/bin/python -m pytest -p no:cacheprovider -q -n0 <ids>` where `<repo>` is `/home/stijn/Documents/_code/SDD/fork/sk-nightly-reds-2026-10-03` and the command is run **from your lane worktree** with `PYTHONPATH=$PWD/src`. Never run a whole directory, `make test-fast` or `make test-full`; the orchestrator runs the breadth.
- **Red-first evidence (NFR-003)**: before editing, run the named tests and record the failing summary line. After the fix, record the passing summary line. Put both in the commit message body.
- Lint: `<repo>/.venv/bin/ruff check <files>` and `<repo>/.venv/bin/ruff format --check --force-exclude <files>` must be clean. No new `# noqa` or `# type: ignore`.
- Commit on the lane branch with a conventional message `test(<area>): ...`. Do not push. Do not touch `uv.lock`.
- Terminology: write Mission, never Feature, in new prose.

## Branch Strategy

- **Strategy**: lane worktree allocated by `spec-kitty agent action implement WP02 --agent claude`
- **Planning base branch**: kitty/nightly-reds-2026-10-03
- **Merge target branch**: kitty/nightly-reds-2026-10-03

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

Implementation command: `spec-kitty agent action implement WP02 --agent claude --mission nightly-reds-2026-10-03-01M42RR1`

## Subtasks & Detailed Guidance

### Subtask T005 – Record the red baseline

- **Steps**: run the node id (all three params) with `-n0`; keep the `3 failed` line and the `MISSION_TYPE_CONFLICT` text.

### Subtask T006 – Let the seeding helper take a mission type

- **Purpose**: `866402daba` (PR #5421) makes `spec-kitty mission run <key>` refuse to retype an existing mission (`_mission_type_conflict` in `src/specify_cli/mission_loader/command.py`). A typeless mission may be typed and a matching type passes. `_seed_mission` (line 65) hard-codes `"mission_type": "software-dev"`, and the run-identity test runs custom key `_CUSTOM_MISSION_KEY = "matrix-custom-run"` on that mission.
- **Steps**:
  1. Add a keyword-only parameter `mission_type: str = "software-dev"` to `_seed_mission` and write it into `meta.json`. The default must stay `software-dev`: `_seed_mission` has four callers and the others rely on it.
  2. Find how the `repo` fixture used by `test_mission_run_identity_identical_across_handle_forms` seeds its mission. Make this test run against a mission whose `mission_type` equals `_CUSTOM_MISSION_KEY`, taken from that constant (not a second string literal). Prefer a small dedicated fixture or re-seeding step local to the custom-run section over changing the shared `repo` fixture; if you must touch the shared fixture, prove every other test in the file still passes.
  3. Do not weaken the test: both `exit_code == 0` assertions, the `mission_slug == _FULL_SLUG` assertion and every run-identity assertion after it stay as they are.
- **Files**: `tests/specify_cli/missions/test_handle_equivalence_matrix.py`
- **Notes**: seeding a typeless mission would also pass, but a matching type is the honest fixture for "run a custom mission on its own mission"; use the matching type.

### Subtask T007 – Validate the whole file

- **Steps**: run the whole file with `-n0`; record `N passed`. Compare with the base run: the only outcome change is the three params going from failed to passed.

## Risks & Mitigations

- Changing the shared `repo` fixture could change what other tests exercise; keep the change local to the custom-run test.

## Review Guidance

- The default of `_seed_mission` is unchanged and the custom type comes from `_CUSTOM_MISSION_KEY`.
- No assertion removed; the test still compares run identity across handle forms.
- The numeric-prefix handle `083` still resolves (the slug and mission id of the seeded mission are unchanged).

## Activity Log

- 2026-10-04T06:16:20Z – system – Prompt created.

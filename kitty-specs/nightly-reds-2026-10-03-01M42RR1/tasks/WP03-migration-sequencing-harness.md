---
work_package_id: WP03
title: Migration sequencing test applies only its two migrations
dependencies: []
requirement_refs:
- FR-005
- NFR-002
- NFR-003
planning_base_branch: kitty/nightly-reds-2026-10-03
merge_target_branch: kitty/nightly-reds-2026-10-03
branch_strategy: Planning artifacts for this mission were generated on kitty/nightly-reds-2026-10-03. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty/nightly-reds-2026-10-03 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-reds-2026-10-03-01M42RR1
base_commit: 86732aadfd3e2662de713fe69adce73ac7cce703
created_at: '2026-10-04T06:21:17.206530+00:00'
subtasks:
- T008
- T009
- T010
phase: Phase 1 - Test repairs
history:
- at: '2026-10-04T06:16:20Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/upgrade/migrations/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/specify_cli/upgrade/migrations/test_hosted_endpoint_session_backfill.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP03 – Migration sequencing test applies only its two migrations

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

- `tests/specify_cli/upgrade/migrations/test_hosted_endpoint_session_backfill.py::TestMigrationSequencing` passes (2 tests) and no longer touches any path outside pytest temporary directories (FR-005).
- Red on base `b2c466d7d1`: `PermissionError: [Errno 13] Permission denied: '/any'` (or `FileNotFoundError ... '/any/project/.gitattributes'`, depending on migration order).

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

- **Strategy**: lane worktree allocated by `spec-kitty agent action implement WP03 --agent claude`
- **Planning base branch**: kitty/nightly-reds-2026-10-03
- **Merge target branch**: kitty/nightly-reds-2026-10-03

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

Implementation command: `spec-kitty agent action implement WP03 --agent claude --mission nightly-reds-2026-10-03-01M42RR1`

## Subtasks & Detailed Guidance

### Subtask T008 – Record the red baseline

- **Steps**: run the class with `-n0`; keep the `2 failed` line and the exception text.

### Subtask T009 – Apply only the two migrations under test, in registry order

- **Purpose**: both tests call `MigrationRegistry.get_applicable("3.2.6", "4.0.0rc5", project_path=Path("/any/project"))` and then `apply()` **every** returned migration on the fabricated path, skipping the `detect()` / `can_apply()` gate the real runner uses (`src/specify_cli/upgrade/runner.py`). Newer migrations write to the project (`m_4_0_0rc5_heal_run_index_paths` takes a lock under the project, `m_4_0_0rc5_decision_index_merge_driver` writes `.gitattributes`, the lane-tip recorder shells out to git), so the test breaks whenever such a migration lands. The class docstring states the intent: prove the delete migration (`SIBLING_MIGRATION_ID`) sorts before the backfill (`MIGRATION_ID`) and that running both in that order ends in the asserted state.
- **Steps**:
  1. Keep `get_applicable` as the source of order. In **both** tests assert that `SIBLING_MIGRATION_ID` and `MIGRATION_ID` are present in the applicable ids and that the sibling's index is lower (the first test already does; the second must do the same, otherwise it could pass by applying nothing).
  2. From the applicable list, select the migrations whose id is one of those two, **preserving the registry order**, and apply only those. Do not hand-order them: a future `target_version` reordering must still change what this test does.
  3. Assert `result.success is True` for each applied migration in both tests.
  4. Replace `Path("/any/project")` with a real temporary project directory (`tmp_path / "project"`, created) for both the `get_applicable` call and `apply`. Add `tmp_path` to the test signatures next to the existing `home` fixture. Check what `get_applicable` does with `project_path` so the applicable set still contains both ids for an empty directory; if it filters on project content, say so in the commit body and keep whatever minimal seeding is needed.
  5. Keep the end-state assertions on `home / "config.toml"` exactly as they are.
  6. Update the class docstring only if a sentence became untrue.
- **Files**: `tests/specify_cli/upgrade/migrations/test_hosted_endpoint_session_backfill.py`
- **Notes**: do not call `detect()`/`can_apply()` on unrelated migrations as an alternative; applying only the two under test is the smaller and more stable contract.

### Subtask T010 – Validate the whole file

- **Steps**: run the whole file with `-n0`; record `N passed`. Confirm nothing was created under `/any` (it must not exist).

## Risks & Mitigations

- If the selection were hand-ordered, the test would stop detecting a `target_version` reordering; step 2 forbids that.

## Review Guidance

- Both tests assert presence and order of the two ids before applying.
- The applied subset keeps registry order (no hard-coded sequence).
- No literal `/any` path remains in the two tests.
- End-state assertions unchanged.

## Activity Log

- 2026-10-04T06:16:20Z – system – Prompt created.

---
work_package_id: WP01
title: Red-first measurement of the three migrations under an empty home
dependencies: []
requirement_refs:
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- NFR-003
- SC-001
- SC-002
planning_base_branch: issue-6954-upgrade-empty-home-command-migrations
merge_target_branch: issue-6954-upgrade-empty-home-command-migrations
branch_strategy: Planning artifacts for this mission were generated on issue-6954-upgrade-empty-home-command-migrations. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6954-upgrade-empty-home-command-migrations unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-upgrade-empty-home-command-migrations-01M6EJQR
base_commit: 75a8c37debcbaf0981e780857bb20accfda1c91d
created_at: '2026-11-02T17:08:45.364780+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Measurement
history:
- at: '2026-11-02T17:10:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/upgrade/
create_intent:
- tests/upgrade/test_empty_home_command_migrations.py
execution_mode: code_change
model: ''
owned_files:
- tests/upgrade/test_empty_home_command_migrations.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Red-first measurement of the three migrations under an empty home

## ⚡ Do This First: Load Agent Profile

Load the agent profile named in the frontmatter (`python-pedro`) before parsing the rest of
this prompt.

- **Profile**: `python-pedro`
- **Role**: implementer
- **Agent/tool**: `pi`

## Objectives & Success Criteria

Create `tests/upgrade/test_empty_home_command_migrations.py`, which measures the three
migrations named in issue #6954 at the **real** `upgrade` entry point:

1. `2.1.3_restore_prompt_commands` and `2.1.4_enforce_command_file_state` — pin that their
   template resolution does not depend on the operator's home (FR-005).
2. `3.1.2_globalize_commands` — prove it does, and fail on today's code (FR-001/FR-003).

Done when the module runs on `main`'s source and the new `3.1.2` assertions fail for the
stated reason while every other test in it passes; no test is skipped or xfailed.

## Context & Constraints

- Grounding (see `research.md`): on a converged project all three records are `success`,
  and `success` settles a migration, so the ledger never re-evaluates them. Seed the three
  as `skipped` and assert the resulting ledger, otherwise the fixture measures nothing.
- Copy the harness shape from `tests/upgrade/test_upgrade_integration.py`: a module-level
  `typer.Typer(add_completion=False)` test app with `upgrade` registered, a
  `typer.testing.CliRunner`, and `contextlib.chdir` around the invocation.
- Use the `canonical_home` fixture for `SPEC_KITTY_HOME`; never pin it locally, never patch
  `Path.home()`. Bootstrapping the home means writing
  `<SPEC_KITTY_HOME>/cache/version.lock`; un-bootstrapping means removing it.
- Do not touch `src/` in this WP. Do not create
  `tests/upgrade/test_upgrade_empty_home_noop.py` — that path belongs to unmerged PR #6946
  (C-001).

## Files

- Create: `tests/upgrade/test_empty_home_command_migrations.py`
- Read: `tests/upgrade/test_upgrade_integration.py`, `tests/conftest.py` (`canonical_home`),
  `src/specify_cli/upgrade/ledger.py`, `src/specify_cli/upgrade/migrations/m_3_1_2_globalize_commands.py`

## Test inventory

| Test | Shape | Expectation on `main` |
| --- | --- | --- |
| `test_converged_upgrade_makes_no_tracked_change_without_a_bootstrapped_home` | converge under a bootstrapped home, un-bootstrap, run `upgrade --project --yes --no-worktrees` | passes or fails only for the #6551 predicate path, never for the three (assert the three ledger records are untouched and say so in the docstring) |
| `test_dated_project_removes_marked_command_file_under_an_empty_home` | stamped project + one version-marked `spec-kitty.specify.md` + `skipped` 3.1.2 record, empty home | **FAILS**: file kept and no commit |
| `test_same_commit_leaves_identical_tracked_state_in_both_homes` | same fixture as above, run once empty and once bootstrapped (fresh copy each) | **FAILS**: the two runs disagree |
| `test_unmarked_command_file_is_held_in_both_homes` | file with no version marker | passes; `manual_review_required`, file preserved |
| `test_template_source_is_home_independent` (parametrised over both modules) | call `_get_runtime_command_templates_dir()` with empty and bootstrapped home | passes; path is inside the package/doctrine tree |

## Definition of Done

- `uv run pytest tests/upgrade/test_empty_home_command_migrations.py -q` runs; the two
  `3.1.2` tests fail with an assertion message that names the kept file and the missing
  removal.
- Tracer entries appended: the red output for T007
  (`spec-kitty agent tracer-append --mission <slug> --category approach --entry "..."`).
- No `src/` change in this work package's diff.

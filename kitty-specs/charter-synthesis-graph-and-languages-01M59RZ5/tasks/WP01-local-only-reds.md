---
work_package_id: WP01
title: 'Local-only reds: upgrade outside git, orphan ceiling, nag-test hermeticity'
dependencies: []
requirement_refs:
- FR-015
- FR-016
- FR-017
- C-006
- SC-005
planning_base_branch: issue-6442-charter-synthesis-graph-work
merge_target_branch: issue-6442-charter-synthesis-graph-work
branch_strategy: Planning artifacts for this mission were generated on issue-6442-charter-synthesis-graph-work. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6442-charter-synthesis-graph-work unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-synthesis-graph-and-languages-01M59RZ5
base_commit: d3e049f9f41c13cf9577f12fe2c0c8762d054e23
created_at: '2026-10-19T10:25:21.081227+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Foundations
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/
create_intent:
- tests/specify_cli/upgrade/test_runner_not_a_git_repository.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/upgrade/runner.py
- tests/specify_cli/upgrade/test_runner_not_a_git_repository.py
- tests/specify_cli/cli/commands/test_upgrade_command.py
- tests/specify_cli/cli/commands/test_doctrine_regenerate_graph.py
- docs/development/testing/testing-flakiness.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Local-only reds: upgrade outside git, orphan ceiling, nag-test hermeticity

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

## Objective

Turn three real reds on `main` green and make the nag tests hermetic against agent-container environment variables. Never skip, xfail or quarantine a test (C-006).

## Context

These were classified on 2026-10-19 in a clean environment; see `research/squad-findings.md`.

- `tests/specify_cli/cli/commands` and `tests/specify_cli/upgrade` are out of the PR matrix, so these reds merged green. Nightly 39195441445 reproduces them, tracked by #6437 and #6432.
- `test_upgrade_command_skill_drift::test_6155_*` is #6416. It is out of scope; do not touch it.
- Plan decisions D-07 and D-08 apply.

### Subtask T001: Red-first test for upgrade outside a git repository

- Create `tests/specify_cli/upgrade/test_runner_not_a_git_repository.py`, marked `@pytest.mark.regression` with an issue reference to #6437.
- Build a minimal compatible project in `tmp_path` that is not a git repository. Reuse the project helper in `tests/specify_cli/cli/commands/test_upgrade_command.py` (`_make_compatible_project`) if it can be imported cleanly; otherwise build the minimal `.kittify/metadata.yaml` it uses.
- Run the migration runner, including `dry_run=True`.
- Assert that:
  - there is no exception;
  - `3.2.0rc35_unified_bundle` is reported skipped with a "not inside a git repository" warning;
  - no ledger record is written for it.
- Confirm the test fails on the current source with `NotInsideRepositoryError`.

### Subtask T002: Runner guard (FR-015)

- In `src/specify_cli/upgrade/runner.py` `_apply_migration` (around lines 425-450), treat `NotInsideRepositoryError` raised by `migration.can_apply(...)` or `migration.apply(...)` as not applicable:
  - return `MigrationResult(success=True, warnings=[f"Migration {id} not applicable here (not inside a git repository); skipping"])` with status `"skipped"`;
  - write no record.
- Import it lazily inside the runner with `from charter.resolution import NotInsideRepositoryError`. That is the established `specify_cli` path (see `context.py` and `dispatch.py`).
- Do NOT edit `m_3_2_0rc35_unified_bundle.py`. It shipped, and DIRECTIVE_044 forbids editing it.
- Keep `_apply_migration` at complexity ≤ 15; extract a helper if needed.
- After the fix, the six tests below must pass:
  - `test_yes_and_force_produce_same_effect`
  - `test_yes_and_force_together_allowed`
  - `test_existing_dry_run_flag_preserved`
  - `test_existing_verbose_flag_preserved`
  - `test_existing_force_flag_preserved`
  - `test_existing_no_worktrees_flag_preserved`

### Subtask T003: Orphan ceiling (FR-016)

- `tests/specify_cli/cli/commands/test_doctrine_regenerate_graph.py:124` has `DOCUMENTED_ORPHAN_RESIDUAL = 21`, but the shipped graph has 25 orphans.
- The four new orphans are `mission_step_contract:plan/{plan,research,review,specify}`. PR #6379 vendored them, and they are edge-less by construction.
- The four nodes are already listed in the shipped-orphan set in `tests/charter_offering/drg/migration/test_extractor_projection.py` (around lines 852-876).
- **Preferred approach:** derive the ceiling from that set, so there is one hand-kept list. Do this only if it can be imported without fragile cross-test imports. If you share it, move the set to a small `tests/_support` or conftest-level constant. Ask the orchestrator first if that would touch files you do not own.
- **Otherwise:** raise the ceiling to 25 with a dated comment (2026-10-19) citing #6379, in the style of the existing comment block (around lines 102-123).
- Do not wire edges, and do not touch `packs/built-in/`.
- Report the residual-doc addendum text to the orchestrator in the WP history. A code_change work package cannot own `kitty-specs/`, so the orchestrator commits it at closeout. The doc is `kitty-specs/mission-lifecycle-dispatch-drg-closeout-01KV0S99/drg-orphan-residual.md` (a dated section after its last section).

### Subtask T004: Nag-test hermeticity (FR-017)

- In `tests/specify_cli/cli/commands/test_upgrade_command.py`, these tests depend on the nag being enabled:
  - `test_agent_check_json_prompts_when_update_available`
  - `test_agent_check_guidance_when_upgrade_command_unavailable`
  - `test_agent_check_uv_tool_command_targets_latest_version`
  - `test_cli_update_available_dry_run_shows_nag`
- Add `monkeypatch.delenv("SPEC_KITTY_NO_NAG", raising=False)` to each, or use one local fixture used only by these tests, adding a `monkeypatch` parameter where it is missing.
- Do not edit `tests/conftest.py`: the root fixture is under a single-permitted-edit gate.
- Prove it: with `SPEC_KITTY_NO_NAG=1` exported, the four tests failed before the change and pass after it.
- In `docs/development/testing/testing-flakiness.md`, under the baseline-red gotcha section, add a short "Harness environment leaks" entry. It names `SPEC_KITTY_NO_NAG`, `SPEC_KITTY_NO_UPGRADE_CHECK` and `SPEC_KITTY_NON_INTERACTIVE` as values agent containers export. It says that the root fixture keeps pre-existing `SPEC_KITTY_*` values by design, and that the remedy is a test-local `delenv`.

## Definition of Done

- The T001 test was red before T002 and is green after it.
- These pass with `SPEC_KITTY_NO_NAG=1` still exported, except `test_6155_*` (#6416):
  - `tests/specify_cli/cli/commands/test_upgrade_command.py`
  - `tests/specify_cli/cli/commands/test_doctrine_regenerate_graph.py`
  - `tests/specify_cli/upgrade/`
- The regression marker is converted to a focused unit test before review.
- `ruff check`, `ruff format --check --force-exclude` and `mypy --strict` on the changed files are clean.

## Risks

- **A broad guard could mask a migration that wrote before raising.** Limit the guard to `NotInsideRepositoryError` and say why in a comment.

## Reviewer Guidance

- Verify no shipped migration file changed.
- Verify the guard does not record a ledger entry.
- Verify the tests ran with the env var still exported.

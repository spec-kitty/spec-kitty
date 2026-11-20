---
work_package_id: WP01
title: Red-first reproduction, then Codex home protection (committed block + clone-local exclusion)
dependencies: []
requirement_refs:
- FR-006
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-007
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- C-004
planning_base_branch: fix/7729-codex-home-gitignore
merge_target_branch: fix/7729-codex-home-gitignore
branch_strategy: Planning artifacts for this mission were generated on fix/7729-codex-home-gitignore. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7729-codex-home-gitignore unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
- T008
phase: Phase 1 - Reproduce and fix
history:
- at: '2026-11-20T18:05:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/
create_intent:
- src/specify_cli/agent_utils/codex_home.py
- src/specify_cli/upgrade/migrations/m_4_0_0rc9_exclude_project_local_codex_home.py
- tests/specify_cli/agent_utils/test_codex_home.py
- tests/specify_cli/upgrade/migrations/test_m_4_0_0rc9_exclude_project_local_codex_home.py
- docs/changelog/unreleased/7729-codex-home-gitignore.fixed.md
execution_mode: code_change
owned_files:
- tests/specify_cli/upgrade/migrations/test_p0_repro_7729_codex_home_exposed.py
- src/specify_cli/agent_utils/codex_home.py
- src/specify_cli/agent_utils/ignore_entries.py
- src/specify_cli/upgrade/migrations/m_4_0_0rc9_exclude_project_local_codex_home.py
- src/specify_cli/upgrade/migrations/order_manifest.txt
- tests/specify_cli/agent_utils/test_codex_home.py
- tests/specify_cli/agent_utils/test_ignore_entries.py
- tests/specify_cli/upgrade/migrations/test_m_4_0_0rc9_exclude_project_local_codex_home.py
- docs/changelog/unreleased/7729-codex-home-gitignore.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Red-first reproduction, then Codex home protection

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

## Objectives & Success Criteria

### Red-first (first commit, before any product change)
Extend the existing open-P0 reproduction (`p0_repro(issue=7729)`) so it pins the right fix, red-first, before any product change (Charter Standing Order 4, `test-first-bug-fixing`):

- **T001**: drive the upgrading-clone case through `MigrationRunner(project).upgrade("4.0.0rc9")` (the entry point `spec-kitty upgrade` uses), on a ledger that settles every migration except the rc8 narrowing and any `.codex`-protection step, instead of calling the rc8 migration's `apply()` alone. Keep the issue's 13 Codex home files and the assertion that none is untracked afterwards.
- **T002**: add the pulled-clone half: clone A upgrades and commits `.gitignore` + the committed ledger; clone B (holding the Codex home files and `.cursor/rules/x.md`) pulls, then runs the upgrade; assert no `.codex/` file in clone B is untracked and the run's warnings name `.cursor/rules/x.md`.

Both tests keep the `p0_repro(issue=7729)` marker in the red-first commit; T007 removes it. Both must FAIL on current sources with `SPEC_KITTY_RUN_P0_REPRO=1`.

## Context & Constraints

- Seam: `tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py` (`_ledger_era`, `MigrationRunner(...).upgrade(..., include_worktrees=False)`).
- The `tmp` Codex path must stay spelled split (`test_no_tmp_paths_in_tests.py`).
- Do not weaken the existing assertion.

### Fix


- **T003** `agent_utils/codex_home.py`: one definition of the Codex home layout (committed state rows, home markers) and `is_codex_home(project_path, environ)`: markers present, or `CODEX_HOME` resolves to `<project>/.codex`.
- **T004** `ignore_entries.py`: the committed block's Codex rows come from that layout (everything but `config.toml`); fix the misleading comment. Keep `.codex/config.toml` un-ignored (existing pin).
- **T005** New migration `4.0.0rc9_exclude_project_local_codex_home` (`clone_local_effect = True`): `detect()` = git shows untracked files in a legacy agent folder; `apply()` adds `.codex/` to the common-dir `.git/info/exclude` when `.codex/` is a Codex home with visible files, re-reads status, and warns with the agent-folder files git still shows. Idempotent; never deletes or untracks.
- **T006** Order-manifest entry (appended; `target_version` 4.0.0rc9 is monotonic).
- **T007** Tests: `test_codex_home.py`, committed-block coverage in `test_ignore_entries.py` (12 home files ignored, `config.toml` not), migration unit tests (plain folder, home markers, `CODEX_HOME` env, dry-run, idempotency, not a repo, no agent folder). Remove the `p0_repro` marker from the reproduction (T001/T002) so it guards every PR.
- **T008** Changelog fragment `docs/changelog/unreleased/7729-codex-home-gitignore.fixed.md`.

## Context & Constraints

- C-001: `m_4_0_0rc8_narrow_agent_gitignore.py` stays byte-identical.
- C-002: the committed block never reads local files for Codex rows.
- Complexity ≤ 15, ruff/mypy clean, no suppressions.

## Validation

```bash
uv run --frozen pytest tests/specify_cli/agent_utils tests/specify_cli/upgrade -q
uv run --frozen pytest tests/architectural/test_migration_order_manifest.py tests/architectural/test_no_tmp_paths_in_tests.py tests/architectural/test_lifted_root_gitignore_contract.py -q
SPEC_KITTY_RUN_P0_REPRO=1 uv run --frozen pytest tests/specify_cli/upgrade/migrations/test_p0_repro_7729_codex_home_exposed.py -q   # expected: green
```

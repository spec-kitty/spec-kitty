---
work_package_id: WP02
title: Stamp-first classification in the command-globalization migration
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-006
- NFR-001
- NFR-003
- SC-001
- SC-003
- SC-004
planning_base_branch: issue-6954-upgrade-empty-home-command-migrations
merge_target_branch: issue-6954-upgrade-empty-home-command-migrations
branch_strategy: Planning artifacts for this mission were generated on issue-6954-upgrade-empty-home-command-migrations. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6954-upgrade-empty-home-command-migrations unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-upgrade-empty-home-command-migrations-01M6EJQR
base_commit: null
created_at: '2026-11-02T17:55:30.291155+00:00'
subtasks:
- T008
- T009
- T010
- T011
phase: Phase 2 - Fix
history:
- at: '2026-11-02T17:10:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/migrations/
create_intent:
- tests/upgrade/test_globalize_commands_stamp_classification.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/upgrade/migrations/m_3_1_2_globalize_commands.py
- tests/upgrade/test_globalize_commands_stamp_classification.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Stamp-first classification in the command-globalization migration

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` from the frontmatter before parsing the rest of this prompt.

## Objectives & Success Criteria

Make `_SafeGlobalizeCommandsBase` (in
`src/specify_cli/upgrade/migrations/m_3_1_2_globalize_commands.py`) decide `keep` vs
`remove` from the project's own `metadata.yaml` stamp, and keep the operator-home checks
only for shapes that carry no usable stamp. WP01's red tests must go green; every existing
test for the three migrations and `compat` must stay green.

## Context & Constraints

- Current behaviour, measured (see `research.md`): `_classify()` asks
  `_global_runtime_present()` (is `~/.kittify/missions` populated?) and
  `_global_command_file_present()` (is the exact file under `Path.home()/...`?). Under an
  empty home both answer "no", so a version-marked, generated project-local command file is
  kept and the ledger records `success`, freezing that decision.
- The migration's own docstring already establishes that a version-marked file is ours and
  that a 3.1.2+ project has global commands by design. The project stamp is the evidence
  the ledger is allowed to depend on (ADR `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md`
  §3: `skipped` is re-evaluated, so `detect()`/`apply()` must be a function of project state).
- Read `ProjectMetadata` from `specify_cli.upgrade.metadata` (the canonical owner, as
  `compat.py` does) and `get_global_command_dir` from
  `specify_cli.runtime.agent_commands` (the canonical owner of global agent command paths).
- Do **not** edit `compat.py`, `uses_centralized_runtime()`, the ledger, or the migration
  registry — all owned elsewhere (C-002; `compat.py` is in flight under #6946).
- Do not weaken `_HOLD`: a file without a version marker is user-authored or unproven and
  is preserved for manual review, in every case and on every machine.

## Files

- Modify: `src/specify_cli/upgrade/migrations/m_3_1_2_globalize_commands.py`
- Create: `tests/upgrade/test_globalize_commands_stamp_classification.py`
- Read: `src/specify_cli/upgrade/metadata.py`, `src/specify_cli/runtime/agent_commands.py`,
  `src/specify_cli/upgrade/compat.py`

## Subtasks

- **T008** Add a private helper on the base class, e.g.
  `_is_past_globalization_boundary(project_path) -> bool`, that loads
  `ProjectMetadata.load(project_path / ".kittify")` and returns
  `Version(metadata.version) >= Version(self.target_version)`. Return `False` for no
  metadata, `InvalidVersion`, and `TypeError` (an unquoted numeric stamp parses as a
  float). Document that "cannot date the project" is not evidence of a modern project.
- **T009** In `apply()`, compute the boundary once; when it is true, treat the global
  runtime and the exact global replacement as satisfied (do not call the home readers) so a
  marked file is `remove`d. When it is false, call them exactly as today. Keep the
  `_HOLD` check first in `_classify()`.
- **T010** In `_global_command_file_present()`, resolve the directory through
  `get_global_command_dir(agent_key)` using `AGENT_DIR_TO_KEY` for the root, falling back
  to the historical `Path.home() / agent_root / subdir` shape only when the root has no
  agent key (the legacy `.codex/prompts` case). Keep the function's name and its
  never-raise behaviour.
- **T011** Unit tests for the helper (dated at/above the boundary, dated below it, absent
  metadata, unparseable stamp, numeric stamp) and for `_classify()` ignoring the home on a
  dated project; plus a test that `3.2.0a4_safe_globalize_commands` inherits the same
  rule (threshold from `self.target_version`, not a constant).

## Definition of Done

- `uv run pytest tests/upgrade/test_empty_home_command_migrations.py
  tests/upgrade/test_globalize_commands_stamp_classification.py tests/upgrade/test_compat.py
  -q` is green.
- `uv run ruff check` and `uv run mypy` clean on the changed module (repo config).
- The WP01 red tests pass without being edited to pass; if a red test's expectation was
  wrong, say so in the review-cycle note rather than silently changing the assertion.

---
work_package_id: WP02
title: '#5964 upgrade untrack scoped to spec-kitty-projected .agents/skills paths'
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- SC-001
- NFR-001
- C-001
planning_base_branch: fix/5964-5434-4796-govern-user-content
merge_target_branch: fix/5964-5434-4796-govern-user-content
branch_strategy: Planning artifacts for this mission were generated on fix/5964-5434-4796-govern-user-content. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/5964-5434-4796-govern-user-content unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-govern-user-content-safety-01M4NWGM
base_commit: 712caec82fa7fa265cca177d3b978ecf168806b9
created_at: '2026-10-11T17:26:23.470920+00:00'
subtasks:
- T005
- T006
- T007
- T008
phase: Phase 2 - Fixes
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/
create_intent:
- tests/specify_cli/upgrade/migrations/test_agents_skills_ownership_selection_5964.py
execution_mode: code_change
model: claude-opus-5-5
owned_files:
- src/specify_cli/upgrade/migrations/m_3_2_5_agents_skills_gitignore_backfill.py
- src/specify_cli/upgrade/autocommit.py
- tests/specify_cli/upgrade/migrations/test_agents_skills_ownership_selection_5964.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '5964'
---
# Work Package Prompt: WP02 – #5964 upgrade untrack scoped to projected paths

## ⚡ Do This First: Load Agent Profile
Load `python-pedro` via `/spk-charter-profile-load`, then `spec-kitty charter context --action implement --json`.

## Problem (grounded at HEAD 3498b426)
`src/specify_cli/upgrade/migrations/m_3_2_5_agents_skills_gitignore_backfill.py::_untrack_tracked_paths` (def ~:66-104; enumerate ~:88, `git rm --cached -r` ~:92-96; call site `apply()` ~:136) untracks EVERY tracked path under `.agents/skills/`, consulting neither manifest. `upgrade/autocommit.py` then commits those staged deletions (`migration_index_untracks` ~:450, `index_deletions` ~:504, `safe_commit(index_deletions=...)` ~:539). A team's own committed skills are deleted and the deletion is pushed. WP01's `test_agents_skills_team_content_survives_5964.py` is RED on this.

## Approach (operator-confirmed; C-001)
Scope the untrack SELECTION to spec-kitty-projected paths only. A `.agents/skills/` path is projected iff:
- it matches the stable command-skill pattern (`.agents/skills/spec-kitty.<command>/...`) — reuse `skills/command_installer.py` (`_is_canonical_rel_path` / `_command_from_rel_path` / `CANONICAL_COMMANDS`), OR
- it is recorded as an `installed_path` in `.kittify/skills-manifest.json` (pack/charter skills, `skills/manifest.py::ManagedFileEntry`) OR in `.kittify/command-skills-manifest.json`.
Everything else stays tracked. The `.kittify/skills-manifest.json` FILE untrack itself is intended and stays. DO NOT touch `coordination.coherence.is_self_bookkeeping_churn` — it feeds the destructive-op guards and extending it would widen the data-loss into `consolidate`/`accept` (see research.md D1). Reuse the EXISTING ownership authority; do not fork a new predicate.
- T006 (defense-in-depth): in `autocommit.migration_index_untracks`, drop any `.agents/skills/` deletion that is not projected, so a stray staged deletion never lands in the upgrade commit.

## Acceptance
- WP01 `test_agents_skills_team_content_survives_5964.py` → GREEN.
- New unit `test_agents_skills_ownership_selection_5964.py`: a pack skill AND a command skill are both classified projected (untracked); a team skill is classified team (kept); covers the two-manifest + pattern paths.
- No regression in `tests/upgrade/test_gitignore_backfill_untrack.py` or `test_upgrade_carries_migration_untracks_5443.py`.

## Validation
`PWHEADLESS=1 .venv/bin/python -m pytest tests/upgrade/test_agents_skills_team_content_survives_5964.py tests/upgrade/test_gitignore_backfill_untrack.py tests/upgrade/test_upgrade_carries_migration_untracks_5443.py tests/specify_cli/upgrade/migrations/ -q`, plus `make test-fast`. `ruff`/`mypy --strict` clean; no suppressions. Record counts.

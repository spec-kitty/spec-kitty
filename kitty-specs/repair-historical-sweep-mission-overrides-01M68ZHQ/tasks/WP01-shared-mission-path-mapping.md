---
work_package_id: WP01
title: One path mapping for a project mission file
dependencies: []
requirement_refs:
- FR-003
- C-003
- NFR-001
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-repair-historical-sweep-mission-overrides-01M68ZHQ
base_commit: 7323374ac695d6db299f0af1416d106f45853621
created_at: '2026-10-31T12:50:00.000000+00:00'
subtasks:
- T001
- T002
- T003
phase: Phase 1 - Shared seam
history:
- at: '2026-10-31T12:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/runtime/
create_intent:
- tests/upgrade/test_migrate_integration.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/runtime/migrate.py
- tests/upgrade/test_migrate_integration.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6548'
- '#5280'
---

# Work Package Prompt: WP01 – One path mapping for a project mission file

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter
(`python-pedro`), and behave according to its guidance before parsing the rest of this prompt.

## Objective

`runtime/migrate.py` owns the question "which shipped file does this project file correspond to?".
It currently answers it with a private `_find_package_counterpart` whose `missions/<type>/<rest>`
branch was added for #6548. The repair migration this mission ships must ask the same question, and
the issue's own suggested fix asks for one helper used by both "so they keep from drifting again"
(#5101 territory).

Extract that mapping into a public helper and route the classifier through it. **No behaviour
change**: the flat `templates/`, `command-templates/` and `scripts/` layouts keep their existing
joins and their existing results.

## Subtasks

- **T001** — Add `shipped_mission_counterpart(rel: Path, package_root: Path) -> Path | None` to
  `src/specify_cli/runtime/migrate.py` and have `_find_package_counterpart` call it first. Docstring
  must state *why* both trees share the mapping (`<tree>/missions/<type>/<rest>` in `.kittify/` and
  in `.kittify/overrides/` both map to `<package missions root>/<type>/<rest>`) and cite #6548/#5280.
- **T002** — In `tests/upgrade/test_migrate_integration.py`, pin the helper directly: nested mission
  path resolves to the shipped file; a flat `templates/<name>` path returns `None` (the existing
  fallback joins own it); a mission path whose shipped file is absent returns `None`. Keep the
  existing #6548 regression test (`test_project_mission_copy_is_compared_with_the_package_mission`)
  unchanged and green — it is the proof the classifier still resolves through the mapping.
- **T003** — Run the targeted suites and the linters (see *Verification*).

## Files You Own

- `src/specify_cli/runtime/migrate.py` (the helper + delegation only; do not restructure
  `classify_asset` or `execute_migration`)
- `tests/upgrade/test_migrate_integration.py`

Do **not** touch `src/specify_cli/upgrade/migrations/**` in this WP — the repair owns those.

## Constraints

- The helper takes the `.kittify/`-relative (or `.kittify/overrides/`-relative) `rel`, never a
  hardcoded mission name. `execute_migration`'s `mission="software-dev"` default is half of the
  #6548 bug; the path is the authority.
- Keep the `len(rel.parts) > 2` guard: `missions/<type>/<name>` must not swallow a two-segment path.
- Return `None` when the mapped path exists but is not a file.
- No new imports beyond `pathlib` (already imported).

## Verification

```bash
uv run --frozen pytest tests/upgrade/test_migrate_integration.py -q
uv run --frozen pytest tests/upgrade/migrations/test_m_2_0_6_consistency_sweep.py -q
uv run --frozen ruff check src/specify_cli/runtime/migrate.py tests/upgrade/test_migrate_integration.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/runtime/migrate.py tests/upgrade/test_migrate_integration.py
uv run --frozen mypy src/specify_cli/runtime/migrate.py
```

Record the exact commands and pass/fail counts in the WP's acceptance notes; the PR quotes them.

## Definition of Done

- [ ] Helper exists, is public, documented, and is the only place the `missions/<type>/<rest>` join
      is written in `runtime/migrate.py`
- [ ] `_find_package_counterpart` delegates to it; no result changes for any existing layout
- [ ] New helper tests + the existing #6548 regression test pass
- [ ] ruff check, ruff format --check and mypy clean on the touched files

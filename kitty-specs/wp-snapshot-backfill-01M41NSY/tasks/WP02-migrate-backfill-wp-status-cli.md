---
work_package_id: WP02
title: spec-kitty migrate backfill-wp-status CLI
dependencies:
- WP01
requirement_refs:
- FR-007
- FR-005
planning_base_branch: issue-5579-wp-snapshot-backfill
merge_target_branch: issue-5579-wp-snapshot-backfill
branch_strategy: Planning artifacts for this mission were generated on issue-5579-wp-snapshot-backfill. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5579-wp-snapshot-backfill unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-wp-snapshot-backfill-01M41NSY
base_commit: d7fe32889867bb0428c1aec5edfc0c8f8a4ca12e
created_at: '2026-10-03T20:46:45.239932+00:00'
subtasks:
- T007
- T008
- T009
- T010
phase: Phase 2 - Operator surface
history:
- at: '2026-10-03T20:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/cli/commands/migrate/
create_intent:
- src/specify_cli/cli/commands/migrate/backfill_wp_status.py
- tests/cli/test_migrate_backfill_wp_status.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/cli/commands/migrate/backfill_wp_status.py
- src/specify_cli/cli/commands/migrate_cmd.py
- tests/cli/test_migrate_backfill_wp_status.py
- tests/architectural/test_json_contract_enumeration.py
- tests/cli/test_migrate_group_flags_4964.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – `spec-kitty migrate backfill-wp-status` CLI

## Do This First

Load profile `implementer-ivan`. Read the charter, mission spec/plan, and WP01's delivered API in `src/specify_cli/migration/wp_status_backfill.py` / `backfill_runtime_state.py`.

## Objective

Expose WP01's repair as `spec-kitty migrate backfill-wp-status`, following the pattern of `backfill-runtime-state` (`migrate_cmd.py` ~:1314) and larger bodies in `cli/commands/migrate/*.py` (e.g. `backfill_provenance.py`).

## Subtasks

- **T007**: register `@app.command(name="backfill-wp-status")`; options `--mission <handle>` (resolve via the canonical mission resolver; unknown handle → exit 1), `--dry-run`, `--evidence-manifest <path>`, `--json`. Help text includes an example and uses `--mission` (never `--feature`).
- **T008**: evidence manifest loader — YAML `missions: {<slug>: {reason: "<text>"}}`; reject missing/empty reason and slugs that do not resolve (fail closed, exit 1, nothing written).
- **T009**: human summary (scanned, seeded, would-seed, finished→done, snapshot-only reported, errors) and a stable `--json` payload; exit 0 on success, 1 on any per-mission error.
- **T010**: tests with typer `CliRunner` over a tmp repo corpus (dry-run writes nothing; live run seeds; manifest errors fail closed; JSON shape); update `tests/architectural/test_json_contract_enumeration.py` and `tests/cli/test_migrate_group_flags_4964.py` inventories as required (run them to see).

## Validation (targeted)

```
.venv/bin/python -m pytest tests/cli/test_migrate_backfill_wp_status.py tests/cli/test_migrate_group_flags_4964.py tests/architectural/test_json_contract_enumeration.py tests/architectural/test_safety_registry_completeness.py tests/unit/migration/ -q
uv run --frozen ruff check <files>; uv run --frozen ruff format --check --force-exclude <files>; uv run --frozen mypy --strict <files>
```

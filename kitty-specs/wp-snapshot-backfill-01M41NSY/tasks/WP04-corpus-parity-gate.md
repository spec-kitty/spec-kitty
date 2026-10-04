---
work_package_id: WP04
title: Corpus parity gate and sanctioned corrections
dependencies:
- WP03
requirement_refs:
- FR-009
planning_base_branch: issue-5579-wp-snapshot-backfill
merge_target_branch: issue-5579-wp-snapshot-backfill
branch_strategy: Planning artifacts for this mission were generated on issue-5579-wp-snapshot-backfill. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5579-wp-snapshot-backfill unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-wp-snapshot-backfill-01M41NSY
base_commit: d7fe32889867bb0428c1aec5edfc0c8f8a4ca12e
created_at: '2026-10-03T21:56:20.273067+00:00'
subtasks:
- T014
- T015
- T016
phase: Phase 4 - Gate
history:
- at: '2026-10-03T20:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: tests/specify_cli/migration/
create_intent:
- tests/specify_cli/migration/test_corpus_wp_snapshot_parity.py
execution_mode: code_change
model: sonnet
owned_files:
- tests/specify_cli/migration/test_corpus_wp_snapshot_parity.py
- tests/architectural/test_archive_root_byte_identical.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Corpus parity gate and sanctioned corrections

## Do This First

Load profile `implementer-ivan`. Read the charter Standing Order #5 (non-vacuous gate, empty-allowlist preference) and `tests/specify_cli/migration/test_dogfood_corpus_backfilled.py` (sibling pattern).

## Subtasks

- **T014**: `test_corpus_wp_snapshot_parity.py` — for every committed `kitty-specs/<slug>/` with `tasks/WP*.md`, compare the WP-file id set with `materialize(dir).work_packages` keys (in-process reducer; must not raise on a meta naming a deleted coordination branch). Fail listing every disagreeing Mission. Exemptions: a module-level mapping `{slug: (frozenset(snapshot_only_wp_ids), reason)}` used ONLY for snapshot-only WPs (bucket C); a `files_only` gap is never exemptable. Keep under 15 s (NFR-001).
- **T015 controls**: positive census (≥ 400 Missions scanned); self-mutation (copy a Mission to tmp, add an unseeded WP file → helper reports it); stale-exemption (an exemption whose Mission now agrees or is missing fails).
- **T016**: add every MODIFIED frozen file listed by WP03 to `_OPERATOR_SANCTIONED_CORRECTIONS` in `tests/architectural/test_archive_root_byte_identical.py`, with a dated comment block in the existing style: "(2026-10-03, operator decision by stijn-dejongh, Decision Moment 01M41NVK4T6Y912R0JBYS0A5DH, mission wp-snapshot-backfill-01M41NSY, #5579) … Follow-up: once in main's baseline these entries are dead weight and should be removed."

## Validation (targeted)

```
.venv/bin/python -m pytest tests/specify_cli/migration/ tests/architectural/test_archive_root_byte_identical.py -q
uv run --frozen ruff check <files>; uv run --frozen ruff format --check --force-exclude <files>; uv run --frozen mypy <files>
```

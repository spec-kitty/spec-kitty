---
work_package_id: WP01
title: WP-status gap planner and seed writer
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-010
- FR-011
- FR-012
- C-001
- C-002
- C-003
planning_base_branch: issue-5579-wp-snapshot-backfill
merge_target_branch: issue-5579-wp-snapshot-backfill
branch_strategy: Planning artifacts for this mission were generated on issue-5579-wp-snapshot-backfill. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5579-wp-snapshot-backfill unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-wp-snapshot-backfill-01M41NSY
base_commit: d7fe32889867bb0428c1aec5edfc0c8f8a4ca12e
created_at: '2026-10-03T20:16:21.796323+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Core repair
history:
- at: '2026-10-03T20:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/migration/
create_intent:
- src/specify_cli/migration/wp_status_backfill.py
- tests/unit/migration/test_wp_status_backfill.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/migration/wp_status_backfill.py
- src/specify_cli/migration/backfill_runtime_state.py
- tests/unit/migration/test_wp_status_backfill.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – WP-status gap planner and seed writer

## Do This First: Load Agent Profile

Load profile `implementer-ivan` (role implementer) and follow its guidance. Read `.kittify/charter/charter.md`, the mission `spec.md`, `plan.md`, `research.md`.

## Objective

The reduced snapshot (`specify_cli.status.reducer.materialize(feature_dir).work_packages`) omits WPs with no lane events (by design, ADR 2026-06-07-3). Add the canonical repair that seeds the missing events.

## Design (binding)

1. **Pure planner** `src/specify_cli/migration/wp_status_backfill.py` (no file writes, no `_unsafe` import):
   - `WpGap(files_only: frozenset[str], snapshot_only: frozenset[str])` from WP-file ids (frontmatter `work_package_id`; malformed files reported and skipped — reuse `status.wp_metadata.read_wp_frontmatter` like `status/bootstrap.py::_collect_wp_ids`) vs snapshot keys. Set-based.
   - `TerminalEvidence` resolution: `meta.json` `merged_at` then `accepted_at`, else an evidence-manifest entry `{slug: reason}` passed in; else none.
   - Seed construction: for each `files_only` WP, a `planned` seed (genesis → planned); when terminal evidence exists, also a forced `planned → done` (`force=True`, `reason` citing the evidence, `evidence=None`). Actor `migration:backfill_wp_status` (must start with `consolidation.wp_attribution.MIGRATION_ACTOR_PREFIX`). Event ids deterministic — reuse the deterministic-ULID helper `backfill_runtime_state` uses (`_seed_id` / `deterministic_ulid`), keyed on (mission_id or slug, wp_id, to_lane, "wp-status-backfill"). Timestamps deterministic (derive from `meta.json` `created_at` or a fixed epoch consistent with how the runtime backfill stamps; check `test_no_absolute_event_timestamp_mixture.py`).
   - Never touch WPs that already have lane events.
2. **Writer**: a new function in `src/specify_cli/migration/backfill_runtime_state.py` (e.g. `apply_wp_status_backfill(feature_dir, *, dry_run, evidence)`) that reuses the SAME `resolve_status_lock_root` + `feature_status_lock` + id-dedupe + `append_event_stream_atomic_verified` path the module already uses — so NO new entry in `status._unsafe.ALLOWED_CALLERS`, `tests/architectural/test_status_events_writes_gate.py` ledgers, `test_no_legacy_status_emit_callers.py`, `test_2093_authority_invariant.py`. Create the log if absent. Write target via `canonicalize_feature_dir` (degrade, never mint a coordination branch). Regenerate `status.json` via `materialize` only if `status.json` already exists. Also a corpus walker `apply_wp_status_backfill_repo(repo_root, *, mission=None, dry_run, evidence)` with `ensure_within_any` containment like `backfill_runtime_state_repo`. Return a result dataclass (slug, seeded, would_seed, files_only, snapshot_only, terminal reason, error).

## Subtasks

- **T001 (red first, separate commit)**: `tests/unit/migration/test_wp_status_backfill.py` — an issue-pinned `@pytest.mark.regression` test (#5579) building a fixture Mission (3 WP files, log seeding only WP01) asserting `materialize` counts all three after the repair entry point; RED before T002–T005 (import of the new function fails or count mismatches). After green, drop the `regression` mark (keep as focused unit test).
- T002–T004 planner as above.
- T005 writer as above.
- **T006 tests**: no-log Mission; `WPCreated`-only WP is seeded; finished Mission (merged_at) → all seeded WPs `done`, each forced event passes `status.transitions.validate_transition` / `status.wp_state` force rule; manifest evidence; no evidence → `planned`; pre-existing lane-evented WP untouched; idempotent second run appends 0; dry-run writes nothing; meta naming a deleted coordination branch does not raise; interleaving: running `backfill_runtime_state` before/after leaves seeded WP lanes unchanged; readers of `.evidence` on `done` (grep `zeitgeist_bridge.py`, acceptance) tolerate `None` — add a test if any path dereferences it.

## Validation (targeted)

```
.venv/bin/python -m pytest tests/unit/migration/ tests/migration/ tests/specify_cli/migration/ -q
.venv/bin/python -m pytest tests/architectural/test_status_events_writes_gate.py tests/architectural/test_status_unsafe_allowlist.py tests/architectural/test_no_legacy_status_emit_callers.py tests/architectural/test_2093_authority_invariant.py tests/architectural/test_no_absolute_event_timestamp_mixture.py tests/architectural/test_layer_rules.py -q
uv run --frozen ruff check <files>; uv run --frozen ruff format --check --force-exclude <files>; uv run --frozen mypy --strict <files>
```

Complexity ≤ 15 per function. Append a line to `kitty-specs/wp-snapshot-backfill-01M41NSY/traces/*.md` (out-of-map, allowed) for friction/decisions.

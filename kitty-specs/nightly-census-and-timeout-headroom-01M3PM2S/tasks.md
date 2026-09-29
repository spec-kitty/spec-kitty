# Work Packages: Nightly census re-pin and timeout headroom

Mission `nightly-census-and-timeout-headroom-01M3PM2S` — #5367, #5378. Planned under `planner-priti`.

## Subtask Format: `[Txxx] [P?] Description`

## Path Conventions

Repo-root-relative paths; no `kitty-specs/` paths in code_change WPs.

## Work Package WP01: Census honesty — #5367 (Priority: P1) 🎯 MVP

**Goal**: SC-011 census counts only genuine raw material; test green.
**Independent Test**: `pytest tests/specify_cli/bulk_edit/test_occurrence_map_field_paths.py` RED (26≠19) → GREEN.
**Prompt**: `tasks/WP01-census-honesty.md`

### Included Subtasks

- [ ] T001 Record red-first evidence: census test fails `26 == 19` on the branch base.
- [ ] T002 Remove the `references:` block from `packs/built-in/toolguides/{java,javascript,python}-supply-chain.toolguide.yaml`.
- [ ] T003 `spec-kitty doctrine regenerate-graph`; confirm only `pack-manifest.yaml` hashes change (no `*.graph.yaml`).
- [ ] T004 Re-pin `test_governance_occurrences_and_files_match_sc011`: `len(raw) == 20`, add `common-docs` to `raw_files` and `raw_files & migrate_files`, provenance note naming `3e09226f`/#5324; fix stale "5 of 7"/"7 RAW files" docstring counts touched by this change.

### Implementation Notes

The removed refs are inert (extractor path-only resolver). Do not add outbound edges (design decision DD-1).

### Parallel Opportunities

Independent of WP02.

### Dependencies

None.

### Risks & Mitigations

Any `*.graph.yaml` diff after regeneration ⇒ refs were not inert; stop.

## Work Package WP02: Nightly timeout headroom — #5378 (Priority: P1)

**Goal**: every capped interpreter shard and the out-of-matrix leg has ≥1.5× measured headroom.
**Independent Test**: new `tests/ci/test_nightly_timeout_headroom.py` RED against current caps → GREEN.
**Prompt**: `tasks/WP02-nightly-timeout-headroom.md`

### Included Subtasks

- [ ] T005 Add `tests/ci/test_nightly_timeout_headroom.py`: parse `ci-nightly.yml` only; every interpreter shard (roster job keys) and `specify-cli-out-of-matrix` must carry a structured `# headroom:` comment and cap ≥ `ceil((max + 0:30) × 1.5)`; run it RED.
- [ ] T006 Raise caps in `.github/workflows/ci-nightly.yml`: shard 1 → 20, shard 2 → 31, shard 3 → 35, shard 5 → 35, out-of-matrix → 69 (shards 4, 6 keep 25); record the derivation as `# headroom:` comments (censored maxima as `>=`); update `_interpreter_shard_roster.py` docstring to point there; CHANGELOG entry for #5367/#5378.
- [ ] T007 Run `test_interpreter_shard_coverage.py`, `test_module_shard_registry.py`, `tests/ci/test_nightly_exit_code_honesty.py`, `tests/ci/test_interpreter_matrix_env_pinning.py`, the new test.

### Implementation Notes

Only `timeout-minutes:` values and comments change; suite run lines untouched.

### Parallel Opportunities

Independent of WP01.

### Dependencies

None.

### Risks & Mitigations

Workflow-shape tests parse `ci-nightly.yml`; keep job keys and run lines unchanged.

## Dependency & Execution Summary

- **Sequence**: WP01 ∥ WP02 (no dependencies).
- **Parallelization**: fully parallel; disjoint files.
- **MVP Scope**: WP01 (only test red on the nightly).

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP02 |
| FR-004 | WP02 |
| NFR-001 | WP01 |
| NFR-002 | WP01, WP02 |
| C-001 | WP02 |
| C-002 | WP02 |
| C-003 | WP01, WP02 |

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Red-first census evidence | WP01 | P1 | No |
| T002 | Remove toolguide refs | WP01 | P1 | No |
| T003 | Regenerate graph/manifest | WP01 | P1 | No |
| T004 | Re-pin census 19→20 | WP01 | P1 | No |
| T005 | Headroom test (red) | WP02 | P1 | Yes |
| T006 | Raise caps | WP02 | P1 | No |
| T007 | Gate files | WP02 | P1 | No |

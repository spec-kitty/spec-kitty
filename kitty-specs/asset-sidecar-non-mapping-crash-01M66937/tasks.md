# Work Packages: asset-sidecar-non-mapping-crash-01M66937

**Inputs**: Design documents from `kitty-specs/asset-sidecar-non-mapping-crash-01M66937/`
**Prerequisites**: plan.md (required), spec.md, research.md, data-model.md, quickstart.md
**Tests**: Required — the issue asks for a regression test per repository kind, and the charter's red-first discipline (DIRECTIVE_034) applies to defect fixes.
**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work package must be independently deliverable and testable.
**Prompt Files**: Each work package references a matching prompt file in `kitty-specs/asset-sidecar-non-mapping-crash-01M66937/tasks/`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/`, `tests/`

---

## Work Package WP01: Non-mapping sidecar skip in the base loader, red-first (Priority: P1) 🎯 MVP

**Goal**: A top-level non-mapping YAML document in any overlay or built-in sidecar is skipped with the usual `Skipping invalid …` warning instead of crashing `BaseArtifactRepository` load, proven red-first with a regression test per repository kind (#6735).
**Independent Test**: `uv run pytest tests/charter_offering/test_non_mapping_sidecar_skip.py -q` fails on pre-fix main (org-overlay cases) and passes after the fix; the existing `tests/charter_offering/test_base_org_layer.py` suite stays green.
**Prompt**: `kitty-specs/asset-sidecar-non-mapping-crash-01M66937/tasks/WP01-non-mapping-sidecar-skip.md`
**Requirement Refs**: FR-001, FR-002, FR-003

### Included Subtasks

T001 Author the red-first per-kind org-overlay regression tests (parametrized over the 11 `BaseArtifactRepository` kinds) in `tests/charter_offering/test_non_mapping_sidecar_skip.py`; run them and record the red on pre-fix main
T002 Author the built-in-tier regression tests (directive: crashes pre-fix via `_pre_validate`; asset: already skipped via Pydantic — pins uniform semantics) in the same module
T003 Implement the non-mapping guard in `src/charter/offering/base.py` — both `_apply_overlay_file` and `_load_built_in_items`, one shared helper, warning text in the pinned `Skipping invalid <layer> <kind> <file>: <reason>` shape
T004 [P] Add the `[Unreleased]` changelog entry in `docs/changelog/CHANGELOG.md` (bold impact-first lead with `(#6735)`, before/after, under 1,200 characters)
T005 Run the affected suites and gates: new module, `tests/charter_offering/test_base_org_layer.py`, the charter-offering fast lane, plus ruff and mypy on the touched files

### Implementation Notes

- Order is mandatory: T001/T002 red first (commit the red state), then T003 turns them green.
- The guard is an explicit `isinstance(data, Mapping)` check after the `None` early-return — never a wider `except` tuple (research.md D2).
- `None` (empty file) stays an early return with no warning (research.md D4).

### Parallel Opportunities

- T004 can be authored alongside T001-T003 (different file).

### Dependencies

- None (starting and only package).

### Risks & Mitigations

- Warning-text drift breaking `_parse_skipped_glossary_pack_warning` → reuse the exact pinned shape; the glossary-pack skip-parse tests stay green.
- Over-broad exception handling masking real bugs → explicit guard only.
- Per-kind fixture drift → one shared fixture factory parametrized over `(repository class, glob, minimal valid artifact)`.

---

## Dependency & Execution Summary

- **Sequence**: WP01 only — single cohesive defect fix.
- **Parallelization**: T004 alongside T001-T003.
- **MVP Scope**: WP01 is the whole mission.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| C-001 | WP01 |
| C-002 | WP01 |
| C-003 | WP01 |
| SC-001 | WP01 |
| SC-002 | WP01 |
| SC-003 | WP01 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Red-first per-kind org-overlay regression tests | WP01 | P1 | No |
| T002 | Built-in-tier regression tests | WP01 | P1 | No |
| T003 | Non-mapping guard in `src/charter/offering/base.py` | WP01 | P1 | No |
| T004 | Changelog `[Unreleased]` entry | WP01 | P2 | Yes |
| T005 | Suites and gates green | WP01 | P1 | No |

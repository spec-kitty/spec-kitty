---
description: "Work package task list for the charter offering public surface freeze"
---

# Work Packages: Freeze the charter offering public contract surface

**Inputs**: Design documents from `kitty-specs/charter-offering-surface-freeze-01M6BTTR/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/public-surface-census.md, quickstart.md
**Issue**: [#6285](https://github.com/spec-kitty/spec-kitty/issues/6285)

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`).

**Prompt Files**: Each work package references a matching prompt file in `tasks/`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** marks a subtask that can proceed in parallel.
- Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/`, `tests/`, `docs/`.

---

## Work Package WP01: Frozen census and its gate checks (Priority: P0)

**Goal**: Commit the machine-readable census of the offering public surface and pin the live surface, the facades and the reached-path classification to it inside the gate file that already owns those invariants.
**Independent Test**: With the census in place, adding a name to `charter.offering.api.__all__` (or removing a census row) makes `tests/architectural/test_charter_offering_public_surface.py` fail; the planted-mutation self-tests prove each new assertion can fail.
**Prompt**: `/tasks/WP01-frozen-census-gate-checks.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, NFR-004, C-001, C-002, C-003, SC-001, SC-002, SC-003

### Included Subtasks

T001 Add the census-pin checks to `tests/architectural/test_charter_offering_public_surface.py` first and run them red (census absent)
T002 Author `tests/architectural/charter_offering_public_surface.yaml` with the 12 surface rows (origin, disposition, facades, kind, today's type, signature, DTO target/status)
T003 Add the reached-path classification section and the `public_contract_delta` list, derived from the live scan and `test_doctrine_census.DISPOSITION`
T004 Add the facade-match check that reads `_FACADE_TABLE` and fails loudly if its shape changes
T005 Add planted-mutation self-tests for every new assertion (name set, origin, facade set, DTO annotation, delta)
T006 Run the four gate files green and record the timing delta

### Implementation Notes

- Extend the existing gate file; do not create a parallel gate (NFR-004) and do not change or remove its assertions (C-002).
- `inspect.signature()` strings for callables are pinned deliberately; a signature change must be a census change.
- No `src/` change in this WP.

### Parallel Opportunities

- T002/T003 (authoring the census) can proceed while T001 (checks) is being drafted, but T001 must be observed red before T002 lands.

### Dependencies

- None (starting package).

### Risks & Mitigations

- `_FACADE_TABLE` is private: the match check must fail on an unavailable/changed table rather than compare against an empty set.
- Signature-string churn: accepted as the price of the freeze; keep the diff in one file so review is cheap.

---

## Work Package WP02: Contract record (C-003, README, changelog) (Priority: P1)

**Goal**: Make the module and the maintainer-facing documentation state the frozen surface and the ADR-0004 DTO direction honestly.
**Independent Test**: `src/charter/offering/api.py`'s C-003 no longer claims OpenAPI conventions do not apply and names the generated-DTO direction; the offering README points at the census; the changelog carries an `[Unreleased]` entry with the issue reference; docs-freshness stays at 0 errors.
**Prompt**: `/tasks/WP02-contract-record-c003-readme-changelog.md`
**Requirement Refs**: FR-006, FR-007, FR-008, C-004, SC-004

### Included Subtasks

T007 Reword C-003 in `src/charter/offering/api.py` to the ADR-0004 generated-DTO direction, marking today's types transitional and pointing at the census; agree with the census `c003` note
T008 Add the "Public contract surface" section to `src/charter/offering/README.md` (what is frozen, where the census is, how to change it, what is not on the surface)
T009 Add the `[Unreleased]` changelog entry and verify docs freshness + the terminology guard

### Implementation Notes

- Docstring-only change in `api.py`; do not touch `__all__` or the imports (FR-002 owns that file's surface in WP01).
- Do not restate spec-kitty-charter ADR-0004 or claim DTO generation has landed; #6218 stays open and distinct (C-004).
- Changelog: bold impact-first lead with `(#6285)`, before/after, under 1,200 characters.

### Parallel Opportunities

- T007 and T008 are independent files; T009 depends on both being worded consistently.

### Dependencies

- WP01 (the census file it points at must exist).

### Risks & Mitigations

- Terminology gate (`test_no_legacy_terminology.py`) rejects "feature" language; write "mission"/"surface"/"seam" only.
- Docs freshness has a pre-existing warning baseline (13 warnings, 0 errors); do not chase those, only avoid new errors.

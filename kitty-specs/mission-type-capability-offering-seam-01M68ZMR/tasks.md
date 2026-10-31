# Work Packages: Mission-type capability contract on the offering seam

**Inputs**: Design documents from `kitty-specs/mission-type-capability-offering-seam-01M68ZMR/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/mission-type-capabilities-contract.md

**Tests**: Required. This is an exposure change on a frozen architectural seam: the red-first
seam test is WP01 and lands before any source change.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work
package is independently deliverable and testable.

**Prompt Files**: `tasks/WP01-seam-capability-test.md`, `tasks/WP02-capability-contract-module.md`,
`tasks/WP03-gates-record-and-changelog.md`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

Single project: `src/`, `tests/`, `docs/` at the repository root, repo-root-relative in all
frontmatter.

---

## Work Package WP01: Red-first proof of the seam capability contract (Priority: P0)

**Goal**: Write the failing seam test that pins the whole contract: the three symbols are on
`charter.offering.api`, a seam-only consumer reads both capabilities, the protocol's negative
control fails a non-conforming object, the typeless and custom-type reads are pinned, and the
offering module registers no `charter.activation` module.
**Independent Test**: `uv run pytest tests/charter_offering/test_mission_type_capabilities_seam.py`
fails red on the pre-change tree with `ImportError`/`AttributeError` naming the missing seam
symbols, and passes after WP02.
**Prompt**: `tasks/WP01-seam-capability-test.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-007, FR-008, NFR-002, SC-001, SC-003

### Included Subtasks

T001 [P] Author the red seam test module (built-in family parametrisation through the seam read)
T002 [P] Add the protocol negative control and the frozen/value-equality assertions
T003 Add the subprocess layering test with its positive control (no `charter.activation` module)

### Implementation Notes

- The test module imports the capability surface **only** from `charter.offering.api`; the
  resolved bundles come from `charter.activation` (that is the consumer's own tier) — the point
  is that the *contract* import is seam-only.
- Reuse the in-repo fixture idioms from `tests/charter/test_resolved_mission_type_context.py`
  (`.kittify/config.yaml` activation list; `_StubPack` for the org-layer custom type). Do not
  copy a prior mission's structure.
- The subprocess laysering test must run in a **fresh interpreter** and carry a positive control
  (a module that does import activation, proving the detector can see it).

### Parallel Opportunities

- T001 and T002 are separate fixtures in the same file; T003 is a separate concern.

### Dependencies

- None (starting package).

### Risks & Mitigations

- A vacuous layering test (in-process `sys.modules` check after other tests imported activation)
  — hence the subprocess + positive control.

---

## Work Package WP02: The capability contract module and its wiring (Priority: P0)

**Goal**: Land `charter/offering/missions/capabilities.py`, publish the three symbols on the
seam, re-export them through the `charter.missions` facade, and let `ResolvedMissionType`
satisfy the contract — turning WP01's red test green without importing activation from offering.
**Independent Test**: WP01's seam test passes; `uv run pytest tests/charter/` (targeted files
named in the prompt) stays green; `uv run mypy src/charter` reports no new diagnostics.
**Prompt**: `tasks/WP02-capability-contract-module.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-003, C-001, C-002, C-004

### Included Subtasks

T001 Create `charter/offering/missions/capabilities.py` (value object, protocol, read function)
T002 Add the three symbols to `charter.offering.api` (`__all__` stays sorted)
T003 [P] Re-export the three symbols from the `charter.missions` facade
T004 [P] Add the additive `ResolvedMissionType.capabilities` property

### Implementation Notes

- Module imports: `dataclasses`, `typing` only. No `charter.activation`, no `pydantic`, no I/O.
- `capabilities_of` coerces to `bool` and fails loud (`AttributeError`) on a non-conforming
  source; no silent `False` defaulting.
- The DTO property is a plain `@property` (not `cached_property`): it must add no state and no
  disk read.

### Parallel Opportunities

- T003 and T004 touch disjoint files and can land together.

### Dependencies

- WP01 (the test is the acceptance proof).

### Risks & Mitigations

- Touching `mission_type_profiles.py` overlaps #6327's file; keep the hunk beside the existing
  capability *properties*, not the capability *fields*.
- The strict facade-coverage gate fails if any of the three symbols is missed in the facade.

---

## Work Package WP03: Gates, ADR amendment and changelog (Priority: P1)

**Goal**: Make the seam addition honest and recorded: a `PUBLIC` census disposition row for the
new module, an ADR 2026-10-03-1 amendment for the additive seam symbols (the #6541 precedent),
and the `[Unreleased]` changelog entry.
**Independent Test**: the three gate files pass with the new symbols present, and each gate
names the new module/symbols in its failure message when the row/entry is removed.
**Prompt**: `tasks/WP03-gates-record-and-changelog.md`
**Requirement Refs**: FR-005, FR-006, NFR-003, C-003, SC-002, SC-004

### Included Subtasks

T001 Add the `PUBLIC` census row for `charter.offering.missions.capabilities`
T002 [P] Amend ADR 2026-10-03-1 with the additive seam symbols
T003 [P] Add the `[Unreleased]` changelog entry (impact-first, `(#6331)`, before/after)

### Implementation Notes

- The census row is the *only* way to satisfy the disposition gate; never loosen the gate.
- The ADR amendment mirrors the `LANGUAGE_TOKENS` amendment's shape: what crosses the seam, what
  stays internal, how it is narrowed and reached.
- Changelog format: bold impact-first lead with `(#6331)`, before/after, under 1,200 characters.

### Parallel Opportunities

- T002 and T003 are independent documents.

### Dependencies

- WP02 (the symbols must exist; the gates import the seam).

### Risks & Mitigations

- A `PUBLIC` row on a module the census never reaches is legal (the table is a documented
  superset), but the row must match the module path exactly — the gate resolves by
  longest-prefix.

---

## Dependency Summary

```
WP01 ──► WP02 ──► WP03
```

# Work Packages: Pack file-name collision diagnostic

**Inputs**: Design documents from `/kitty-specs/pack-file-name-collision-diagnostic-01M66YTQ/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md (decisions)

**Tests**: Required. This is a defect fix: every surface gets a failing test through
its real entry point before the code exists (ATDD, DIRECTIVE_034).

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages
(`WPxx`). Each work package is independently deliverable and testable.

**Prompt Files**: Each work package references a matching prompt file in
`kitty-specs/pack-file-name-collision-diagnostic-01M66YTQ/tasks/`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

Single Python package: `src/`, `tests/`.

## Subtask Index

| Txxx | Description | WP | Parallel |
|------|-------------|----|----------|
| T001 | Red test: `file_name_collisions()` reports the org-vs-built-in directive collision | WP01 | |
| T002 | Implement `FileNameCollision` + `IdentityIndex.file_name_collisions()` over the memoised tables | WP01 | |
| T003 | Share the per-stem declarations helper with `collision_error()` (message unchanged) | WP01 | |
| T004 | Agreement test with `ActivationIdCollisionError` plus same-id and disjoint controls | WP01 | |
| T005 | Red test: the validate door reports the collision as an error | WP02 | |
| T006 | Implement the collision leg in `validate_pack_with_org_charter` (pack + built-in, level-labelled) | WP02 | |
| T007 | CLI test: `charter pack validate` exits 1 and `--json` carries `category: file_name_collision` | WP02 | |
| T008 | Positive control: pack outside a repo, same-id override and disjoint pack stay clean | WP02 | |
| T009 | Red test: `doctor charter-packs` reports the chain collision in text and `--json`, RC=1 | WP03 | |
| T010 | Implement `_collect_file_name_collisions()` + `_run_file_name_collision_check()` | WP03 | |
| T011 | Render the finding and wire the leg on both doctor output paths | WP03 | |
| T012 | Determinism, no-crash and no-slowdown checks (NFR-002/003/004) | WP03 | |
| T013 | Changelog `[Unreleased]` entry with the `(#6743)` reference | WP04 | |
| T014 | Document `file_name_collision` in the two CLI/command docs | WP04 | [P] |
| T015 | Document it in the org-pack how-to | WP04 | [P] |
| T016 | Mission traces and issue-verdict records stay current | WP04 | |

---

## Work Package WP01: Identity collision query (Priority: P0)

**Goal**: Make "which file names stand for more than one declared id" a first-class
answer from `IdentityIndex`, derived from the tables it already builds, with one
message shared by every consumer.
**Independent Test**: on a fixture with an org directive named like the built-in
`024-locality-of-change` but declaring `ACME_024`, the query returns exactly one
record naming the file name and both declarations; on the same fixture with a
same-id override, and on a disjoint pack, it returns none.
**Prompt**: `tasks/WP01-identity-collision-query.md`
**Requirement Refs**: FR-001, FR-004, FR-005, NFR-001, NFR-002, C-001, C-005

### Included Subtasks

T001 Red test: `file_name_collisions()` reports the org-vs-built-in directive collision
T002 Implement `FileNameCollision` + `IdentityIndex.file_name_collisions()` over the memoised tables
T003 Share the per-stem declarations helper with `collision_error()` (message unchanged)
T004 Agreement test with `ActivationIdCollisionError` plus same-id and disjoint controls

### Implementation Notes

- Query only memoised `_table(kind)` entries; never call `_scan()` for a kind the
  caller did not ask for beyond the kinds it names.
- `collision_error()`'s message and attributes must stay byte-identical (C-005).
- Sort by `(kind, file_name)`; declarations in index precedence order (NFR-002).

### Parallel Opportunities

- T003 shares a helper with existing code; it can be done together with T002.

### Dependencies

- None (starting package). WP02 and WP03 depend on it.

### Risks & Mitigations

- Adding a scan by accident would violate NFR-001 → assert the query works on a
  spy/patch that fails the test if `_scan` runs twice for one kind.

---

## Work Package WP02: Validate reports the collision (Priority: P1) 🎯 MVP

**Goal**: `spec-kitty charter pack validate <pack>` reports the file-name collision
as an error naming the file, the layers, both ids and the rename advice.
**Independent Test**: a temp pack whose directive file reuses the built-in file name
with a different id fails validation with exit 1 and one `file_name_collision`
error; renaming the file makes the same pack pass.
**Prompt**: `tasks/WP02-validate-collision-leg.md`
**Requirement Refs**: FR-002, FR-006, FR-007, C-002, C-004

### Included Subtasks

T005 Red test: the validate door reports the collision as an error
T006 Implement the collision leg in `validate_pack_with_org_charter` (pack + built-in, level-labelled)
T007 CLI test: `charter pack validate` exits 1 and `--json` carries `category: file_name_collision`
T008 Positive control: pack outside a repo, same-id override and disjoint pack stay clean

### Implementation Notes

- Wire at `charter.activation.org_charter.validate_pack_with_org_charter`; do not
  import `charter.activation` from `charter.offering` (C-002).
- Reuse `ValidationIssue` / `ValidationResult` unchanged so `--json` needs no new schema.
- Label the validated pack's files by its declared `pack_level`, falling back to `org`.

### Parallel Opportunities

- T005 and T007 are independent tests; T008 depends on T006.

### Dependencies

- Depends on WP01.

### Risks & Mitigations

- A pack validated outside any repository must behave identically (C-004) → test
  from a temp dir with no `.kittify/config.yaml` in the ancestor chain.

---

## Work Package WP03: Doctor reports the collision across the chain (Priority: P2)

**Goal**: `spec-kitty doctor charter-packs` reports the collision across the
configured project/org/built-in chain, in text and JSON, and exits 1.
**Independent Test**: a temp repo whose org and project packs ship the same tactic
file name with different ids reports one finding naming both layers and both ids;
the same fixture with distinct file names is unchanged.
**Prompt**: `tasks/WP03-doctor-collision-leg.md`
**Requirement Refs**: FR-003, FR-007, NFR-002, NFR-003, NFR-004

### Included Subtasks

T009 Red test: `doctor charter-packs` reports the chain collision in text and `--json`, RC=1
T010 Implement `_collect_file_name_collisions()` + `_run_file_name_collision_check()`
T011 Render the finding and wire the leg on both doctor output paths
T012 Determinism, no-crash and no-slowdown checks (NFR-002/003/004)

### Implementation Notes

- Follow the existing `_run_cross_grain_check` / `_run_operating_procedures_check`
  pattern: always write the structured list, append to `org_drg["errors"]` when non-empty.
- The existing `Collisions:` (same-id override) section and `PackHealth` are untouched.

### Parallel Opportunities

- T011 (renderer) can proceed while T010 lands, but both touch doctor wiring.

### Dependencies

- Depends on WP01.

### Risks & Mitigations

- A broken chain must not raise → wrap the collection in the established
  `except Exception` + `org_drg["errors"]` recording (NFR-003).

---

## Work Package WP04: Changelog and docs (Priority: P3)

**Goal**: an operator finds the new error where they look for it.
**Independent Test**: the changelog entry names issue #6743 with before/after; the
two command docs list the new finding; the how-to tells a pack author to rename.
**Prompt**: `tasks/WP04-changelog-and-docs.md`
**Requirement Refs**: FR-002, FR-003

### Included Subtasks

T013 Changelog `[Unreleased]` entry with the `(#6743)` reference
T014 [P] Document `file_name_collision` in the two CLI/command docs
T015 [P] Document it in the org-pack how-to
T016 Mission traces and issue-verdict records stay current

### Implementation Notes

- Impact-first bold lead, then before/after, under 1,200 characters.
- Wording must match the shipped message (rename one of the files).

### Parallel Opportunities

- T014 and T015 are independent files.

### Dependencies

- Depends on WP02, WP03 (final wording).

### Risks & Mitigations

- Changelog conflicts with concurrent missions → keep both sides on rebase.

---

## Parallelization

- WP01 lands first; WP02 and WP03 then proceed independently (different files).
- WP04 runs after WP02 and WP03 so the docs match the shipped wording.

## MVP scope

WP01 + WP02: the issue's headline example is then reported by `charter pack validate`.

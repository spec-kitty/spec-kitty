# Work Packages: An org DRG fragment carries its effective pack root

**Inputs**: Design documents from `/kitty-specs/org-drg-fragment-pack-root-01M66YJG/`
**Prerequisites**: plan.md (required), spec.md (user stories)
**Issue**: spec-kitty/spec-kitty#6731 (follow-up to #6418)

**Tests**: Explicit testing work is included — this is a defect removal whose acceptance is
"the same refusals, one authority", so the red-first proof and the pinned refusals are the deliverable.

**Organization**: Two work packages with disjoint file ownership. WP01 makes the fragment carry its
root and collapses both offering predicates onto it. WP02 deletes the activation wrappers and
re-points the doctor onto the offering facade. WP02 depends on WP01, so they run in sequence.

## Path Conventions

- Single project: `src/`, `tests/`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** marks a subtask that can proceed in parallel (different files).
- Subtasks are reference rows; record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

---

## Work Package WP01: One authority for the pack root and the containment verdict (Priority: P0)

**Goal**: `OrgDRGFragment` carries the effective root its loader already resolved; both
containment predicates take only the fragment and read that root; the activation wrappers and the
registry re-read are gone; both doctor halves reach the predicates through the `charter.drg`
facade — with identical findings and exit codes.
**Independent Test**: a fragment loaded by `load_org_pack` reports its effective root, serializes
without it and refuses to judge containment once the root is gone; both predicates report the same
escapes as before when called with one argument; one `_collect_org_layer_data` run reads the pack
registry exactly once; the #6418 doctor refusal matrix still exits 1 for escapes and 0 for
contained controls.
**Prompt**: `/tasks/WP01-fragment-carried-root.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, FR-008, NFR-001, NFR-002, NFR-003, NFR-004, C-001, C-002, C-003, C-004, SC-001, SC-002, SC-003, SC-004

### Included Subtasks

T001 [P] Red tests for the carried root and the fragment-only body predicate in `tests/charter_offering/drg/test_org_body_path_escapes.py`
T002 [P] Red tests for the fragment-only asset predicate in `tests/charter_offering/assets/test_org_asset_path_escapes.py`
T003 Implement `OrgPackRootUnavailableError`, the `_pack_root` private attribute, the `pack_root` property and the `find_body_path_escapes(fragment)` signature in `src/charter/offering/drg/org_pack_loader.py`
T004 Implement `find_asset_path_escapes(fragment)` in `src/charter/offering/assets/repository.py`
T005 Re-export the new offering names through the `charter.drg` facade, with `__all__` members that have live callers
T006 Run the two offering test modules, ruff and mypy on the touched modules
T007 Red counting test: one registry read per doctor run, in `tests/specify_cli/cli/commands/test_doctor_charter_packs_org_layer.py`
T008 Delete `find_org_body_path_escapes`, `find_org_asset_path_escapes`, `_org_pack_roots_by_name` and their now-unused imports from `src/charter/activation/drg_activation.py`
T009 Re-point the JSON half (`src/specify_cli/cli/commands/_charter_pack_collect.py`) onto `charter.drg` and aggregate per fragment
T010 Re-point the human half (`src/specify_cli/cli/commands/_profile_health_render.py`) the same way, keeping the "not checked" channel
T011 Re-point the four monkeypatch targets in the doctor tests and assert the deleted names are gone, with `load_org_drg` as the positive control
T012 Verify: doctor module, offering modules, activation-seam gate, dead-symbol gate, ruff, mypy, and the end-to-end doctor run

### Implementation Notes

- Stamp the root at `load_org_pack`'s single success return, after discovered nodes are appended.
- Keep every judgement rule and docstring claim that is still true; only the signature and the
  root's provenance change.
- Aggregate the doctor's per-fragment results in fragment order so finding order, messages and JSON
  arrays are unchanged.
- Keep the two `except Exception` channels and their exact message prefixes
  (`org-layer body_path check failed:`, `org-layer asset path check failed:`), and the human
  half's `not checked` rendering.
- `load_org_drg` keeps its `charter.activation.drg_activation` import: the baseline rows stay
  accurate, no row is added or drained.

### Parallel Opportunities

- T001 and T002 are independent files; T009 and T010 are independent files.

### Dependencies

- None. **Why one package**: the offering signature change and the doctor/activation changes are
  one atomic refactor. Splitting them left the branch with a broken `doctor charter-packs` and no
  independently deliverable package (review finding F1 on the first WP01 head).

### Risks & Mitigations

- A predicate that silently falls back to a default root would hide the FR-007 case → the typed
  error is required and tested through the dump/reload path.
- Deleting a symbol while a test still monkeypatches it reads as a silent pass → assert absence
  positively, with `load_org_drg` as the positive control.
- The seam gate is shrink-only in both directions → run it, and do not edit
  `charter_activation_boundary_baseline.yaml`.

---

## Dependency & Execution Summary

- **Sequence**: one work package, no cross-package sequencing. Within it: offering layer (T001–T006)
  then activation/doctor (T007–T012), two readable commit slices of one deliverable.
- **Parallelization**: T001/T002 (different test modules) and T009/T010 (different doctor halves).
- **MVP Scope**: WP01 is the whole mission; it changes no operator-visible behaviour.

> **Revision**: an earlier two-package split (WP01 offering, WP02 doctor) was rejected at review
> (finding F1): it cut through one atomic refactor, leaving `doctor charter-packs` broken at the
> first package's head. WP02 is canceled; T007–T012 moved into WP01.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| FR-004 | WP01 |
| FR-005 | WP01 |
| FR-006 | WP01 |
| FR-007 | WP01 |
| FR-008 | WP01 |
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| NFR-003 | WP01 |
| NFR-004 | WP01 |
| C-001 | WP01 |
| C-002 | WP01 |
| C-003 | WP01 |
| C-004 | WP01 |
| SC-001 | WP01 |
| SC-002 | WP01 |
| SC-003 | WP01 |
| SC-004 | WP01 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Red tests: carried root + fragment-only body predicate | WP01 | P0 | Yes |
| T002 | Red tests: fragment-only asset predicate | WP01 | P0 | Yes |
| T003 | Fragment root carriage + body predicate | WP01 | P0 | No |
| T004 | Fragment-only asset predicate | WP01 | P0 | No |
| T005 | `charter.drg` facade re-exports | WP01 | P0 | No |
| T006 | Offering-layer verification (tests, ruff, mypy) | WP01 | P0 | No |
| T007 | Red counting test: one registry read per doctor run | WP01 | P0 | No |
| T008 | Delete the activation wrappers and the re-read | WP01 | P0 | No |
| T009 | JSON half onto the facade | WP01 | P0 | Yes |
| T010 | Human half onto the facade | WP01 | P0 | Yes |
| T011 | Re-point doctor test monkeypatches, assert absence | WP01 | P0 | No |
| T012 | Doctor + architectural gate verification | WP01 | P0 | No |

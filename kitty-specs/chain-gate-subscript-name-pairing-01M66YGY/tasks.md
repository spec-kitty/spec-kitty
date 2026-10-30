---
description: "Work package task list for chain-gate-subscript-name-pairing-01M66YGY"
---

# Work Packages: Chain gate classifies subscript assignment and name-keyed dict comprehensions correctly

**Inputs**: `spec.md`, `plan.md`, `research.md` in `kitty-specs/chain-gate-subscript-name-pairing-01M66YGY/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md
**Issue**: #6732 (parent #6418, PR #6756)

**Organization**: One work package. The change touches one module, and both halves of the
classifier fix share its fixtures, so splitting it would create two packages that only
green together.

## Subtask Format: `[Txxx] [P?] Description`

Subtasks are reference rows; completion is recorded with
`spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/`, `tests/` — this mission changes only
  `tests/architectural/test_org_pack_chain_single_authority.py` plus the changelog.

---

## Work Package WP01: Classify subscript collectors and name-paired dict comprehensions (Priority: P0)

**Goal**: Rule 2 of the chain single-authority gate flags hand-built ROOTs-only chains
assembled through `x[k] = p.effective_root(r)` inside an `enumerate(<registry>.packs)`
loop, and stops flagging name-keyed assemblies — the subscript-keyed loop form and the
`{p.name: p.effective_root(r) ...}` dict comprehension.
**Independent Test**: `uv run pytest tests/architectural/test_org_pack_chain_single_authority.py`
reds on the new fixtures before the classifier change and greens after it, while the live
census over `src/` stays at zero hits.
**Prompt**: `/tasks/WP01-chain-gate-classifier.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, SC-001, SC-002, SC-003, SC-004

### Included Subtasks

T001 Record the pre-fix red: run the new subscript-loop fixture and the name-keyed
`DictComp` fixture through `_scan_source` on the unmodified classifier and capture the
output (no hit / spurious hit) as PR evidence.
T002 [P] Plant the violation fixtures: `enumerate(...)` + `roots[i] = p.effective_root(r)`
and `{p.effective_root(r): p.name ...}`, asserting the hit kinds.
T003 [P] Plant the non-violation fixtures on the same idioms:
`by_name[p.name] = p.effective_root(r)` inside the same `enumerate(...)` loop, and
`{p.name: p.effective_root(r) ...}` for the comprehension.
T004 Unwrap a single-argument wrapping call (for example `enumerate(...)`) in
`_is_packs_iter` so an indexed `.packs` iteration is still recognised.
T005 Collect subscript-assignment values in the loop analysis and judge name pairing from
the loop's collected values plus the subscript keys, never over the whole loop body.
T006 Exempt a `DictComp` whose key carries a `*.name` attribute, while a `DictComp` whose
key is a bare `effective_root(...)` stays a violation.
T007 Update the module docstring so the stated Rule 2 rule names subscript collection and
the name-keyed dict comprehension.
T008 Re-run the gate file plus the live census to confirm zero hits over `src/`, the empty
allowlist, the scanned-file floor and the owner-bypass control are unchanged.
T009 Prove the fix half by half: revert the `enumerate` unwrapping alone, then the
subscript collector alone, then the `DictComp` key rule alone; confirm a fixture reds each
time and restore.
T010 Add the `[Unreleased]` changelog entry for #6732 (impact-first lead, before/after).

### Implementation Notes

- Red first, and through the gate's own scanner: `_scan_source` is the entry point the
  census uses, so a fixture run through it proves the production path, not a new helper.
- Judge pairing over the loop's collected values and subscript keys, not over its whole
  body. A loop that merely mentions a name elsewhere is still a violation; a subscript key
  of `i` is not pairing evidence, and pairing stays loop-wide over collections so the
  existing `paired-loop` fixture keeps its meaning.
- The live tree already contains the name-keyed subscript idiom
  (`src/charter/activation/drg_activation.py::_org_pack_roots_by_name`), so over-widening
  the subscript rule reds the live census, not only a fixture.
- Keep the existing fixtures untouched; they pin behaviour that already worked.
- Do not run the full `tests/architectural/` sweep; run the gate file and, if needed, the
  charter activation unit tier.

### Parallel Opportunities

- T002 and T003 (the two fixture families) are independent edits in the same file; land
  them together with the classifier change so the file is never fixture-only.

### Dependencies

- None (single package). T004–T006 depend on T002/T003 existing to fail.

### Risks & Mitigations

- Over-broad pairing test swallowing real violations → pairing is judged per collected
  expression, and a roots-keyed `DictComp` violation fixture guards the exemption.
- A fixture that passes before the fix proves nothing → T001 records the pre-fix run for
  every new violation fixture, and T009 reverts each half.

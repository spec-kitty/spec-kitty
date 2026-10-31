# Work Packages: Glossary — activation ledger and active charter

**Inputs**: Design documents from `kitty-specs/glossary-activation-ledger-01M68JH9/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md, reasons-canvas.md

**Tests**: One focused regression test (requested by the mission's red-first constraint, C-004) plus the standing parity gate.

**Organization**: One work package for this small, single-concern documentation/data change.

**Prompt Files**: `tasks/WP01-glossary-activation-ledger.md`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Write `tests/glossary/test_activation_ledger_terms.py` and observe it fail on the pre-change tree | WP01 | no |
| T002 | Add the `activation ledger` term and refresh `active charter` in `.kittify/glossaries/spec_kitty_core.yaml` | WP01 | no |
| T003 | Author the identical entries in `spec-kitty-open-packs` and open the upstream PR | WP01 | no |
| T004 | Re-pin `packs/built-in.source.yaml` to the upstream commit and run `make sync-packs` | WP01 | no |
| T005 | Add `docs/context/charter.md` glossary anchors to the two activation module docstrings | WP01 | [P] |
| T006 | Fix the stale `active charter` location in `docs/guides/how-to/governance/troubleshoot-charter.md` | WP01 | [P] |
| T007 | Add the `[Unreleased]` changelog entry in `docs/changelog/CHANGELOG.md` | WP01 | [P] |
| T008 | Run the focused test, the parity gate, the docs gates and the no-legacy-terminology gate; record results | WP01 | no |

---

## Work Package WP01: Glossary entries, pack re-pin and pointers (Priority: P1) 🎯 MVP

**Goal**: Both glossary terms are correct in the seed and the shipped pack, the pack is re-pinned, the two activation docstrings point at the glossary, the stale guide line is fixed, and the docs gates are green.
**Independent Test**: The focused glossary test fails before the data change and passes after it; `tests/architectural/test_glossary_pack_parity.py` passes at the new pin; `check_docs_freshness --ci` reports errors=0.
**Prompt**: `tasks/WP01-glossary-activation-ledger.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, C-004

### Included Subtasks

T001 Write the focused failing glossary test
T002 Add/refresh both seed terms
T003 Author the pack entries upstream and open the open-packs PR
T004 Re-pin the built-in pack and sync
T005 Add the docstring glossary pointers
T006 Fix the stale guide line
T007 Add the changelog entry
T008 Run the focused and standing gates

### Implementation Notes

- Wording source: `docs/context/charter.md` "Active charter" and "Activation ledger" (already updated by #6496). Condense, do not copy the whole table cell.
- Seed key order: `surface`, `definition`, `confidence`, `status`.
- Pack key order: `confidence`, `definition`, `status`, `surface` (with `synonyms_to_avoid` retained on `active charter`).
- Pack content is authored in `spec-kitty-open-packs`; the core tree under `packs/built-in/` is fetched and must not be edited or committed (C-001).
- Re-pin with `spec-kitty charter pack vendor --pack built-in --ref <commit>`, then `make sync-packs`.

### Parallel Opportunities

- T005, T006 and T007 touch disjoint files and can proceed together once the definitions are fixed.

### Dependencies

- None (starting package). T004 depends on T003; T008 depends on all.

### Risks & Mitigations

- **Pin ordering**: the core pin references an open-packs commit from this mission's upstream PR; the operator merges open-packs first. Recorded in the PR `## Deferred`.
- **Parity drift**: seed and pack are edited in one pass and verified by the standing parity test; never weaken the gate.
- **Docs freshness churn**: run the named gate, not a full regenerated reference; record errors=0.

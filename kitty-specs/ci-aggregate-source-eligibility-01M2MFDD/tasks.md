# Tasks: CI Aggregate Source-Eligibility (main-verdict provenance)

**Mission**: `ci-aggregate-source-eligibility-01M2MFDD` · **Branch**: `fix/ci-aggregate-source-eligibility`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Research**: [research.md](./research.md)

Small, cohesive mission (2 WPs). Subtask completion is event-sourced — record with
`spec-kitty agent tasks mark-status Txxx --status done`; the rows below are reference rows, not checkboxes.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first unit tests for `resolve_source` (6 named branches + rejections + malformed) | WP01 | |
| T002 | Implement pure `resolve_source(...)` + `SourceDecision` variants (INV-A..C) | WP01 | |
| T003 | Implement edge `main()` (gh-at-edge injection; emit run-id + eligibility; INV-D/E) | WP01 | |
| T004 | Rewire `ci-aggregate.yml` `last-success` step to call the helper (guard byte-unchanged) | WP01 | |
| T005 | Execution-grounded wiring guard + guard-byte-unchanged pin | WP01 | |
| T006 | Local gates: pytest tests/ci, ruff check + format, terminology, actionlint | WP01 | |
| T007 | Annotate ADR #4360-A with both verified premise-falsifications | WP02 | [P] |
| T008 | Preserve ADR doctrine integrity + links | WP02 | [P] |
| T009 | Gates: terminology, docs-index sync, retired-surface scan | WP02 | [P] |

## Work Packages

### WP01 — Tested provenance source-eligibility surface + workflow wiring

- **Goal**: Extract the inline-shell source-selection into a pure, red-first-tested `scripts/ci/source_eligibility.py`, wire it into `ci-aggregate.yml`, and prove it with an execution-grounded guard. The ADR's named red-first entry point.
- **Priority**: P1 (MVP) · **Prompt**: [tasks/WP01-tested-provenance-source-surface.md](./tasks/WP01-tested-provenance-source-surface.md) (~230 lines)
- **Requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-008, NFR-001, NFR-003, NFR-004; C-001/C-002/C-003 (frozen boundaries), C-004/C-005 (verification)
- **Included subtasks**: T001, T002, T003, T004, T005, T006
- **Independent test**: `PYTHONPATH=$(pwd)/src pytest tests/ci/test_source_eligibility.py` — 6 branch cases green (red-first) + the wiring guard executes the real step + the guard-byte pin holds.
- **Dependencies**: none · **Owned files**: `scripts/ci/source_eligibility.py`, `tests/ci/test_source_eligibility.py`, `.github/workflows/ci-aggregate.yml`
- **Risks**: green-path leak (success-only/branch-scope must hold); fakeable test/guard; helper hard-exit regression.

### WP02 — Annotate ADR #4360-A with both verified premise-falsifications

- **Goal**: Record in the ratified ADR that the #4360-A mechanism is superseded post-Stage-1 and that the resulting failure is cosmetic (no consumer), so no agent re-derives the falsified premise.
- **Priority**: P2 · **Prompt**: [tasks/WP02-adr-annotation.md](./tasks/WP02-adr-annotation.md) (~120 lines)
- **Requirements**: FR-007, NFR-002, SC-004
- **Included subtasks**: T007, T008, T009
- **Independent test**: ADR renders with a dated, evidence-cited annotation of both corrections; ratified Decision Outcome unchanged; terminology guard green.
- **Dependencies**: none (independent write-scope `docs/adr/3.x/`) · **Owned files**: `docs/adr/3.x/2026-09-15-1-ci-main-verdict-topology.md`
- **Risks**: overreach into rewriting the ratified decision; unverified claims.

## Parallelization

- **WP01 ∥ WP02** — disjoint write-scopes (`scripts/ci`+`tests/ci`+one workflow vs `docs/adr/3.x`), no dependency → two lanes, fully parallel.

## MVP

WP01 is the MVP: the tested provenance surface + wiring is the mission's real deliverable. WP02 is the doctrine-fidelity companion.

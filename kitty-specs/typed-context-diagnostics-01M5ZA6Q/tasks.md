# Work Packages: Typed context JSON diagnostics

**Inputs**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/context-json-diagnostics.md`
**Branch contract**: planning base `issue-6460-typed-context-diagnostics`, merge target `issue-6460-typed-context-diagnostics`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red ATDD tests: context JSON `{code, message}`, doctor-by-code, per-code mapping | WP01 | |
| T002 | `GovernanceDiagnosticCode` + `GovernanceDiagnostic` in `_diagnostics.py`; `ERROR_CODES.md`; `api.py` export | WP01 | |
| T003 | Resolver producers emit typed entries; `collect_governance_diagnostics` text view | WP01 | |
| T004 | Context JSON serialises `{code, message}`; contract ledger comment | WP01 | |
| T005 | Doctor classifies by code; retire `UNKNOWN_SELECTION_DIAGNOSTIC` api re-export | WP01 | |
| T006 | Compact context and runtime prompt render `.message` | WP01 | |
| T007 | Update existing assertions; regenerate golden fixtures | WP01 | |
| T008 | `docs/api` (diagnostics shape + codes, interview `narrowed`) and rc8 changelog | WP01 | |
| T009 | Tidy-first: hoist the deferred `ReconciliationDelta` import in `reach_only.py` | WP02 | [P] |
| T010 | Red typing test for the slug helpers' parameter | WP02 | [P] |
| T011 | Annotate `created_slugs_by_kind` / `created_slugs`; keep `[]` for missing/foreign input | WP02 | [P] |

## WP01 – Typed governance diagnostics contract (P1)

**Prompt**: `tasks/WP01-typed-governance-diagnostics.md`
**Goal**: every governance diagnostic carries a closed code; context JSON emits `{code, message}` (schema 1.4.0); doctor classifies by code; text surfaces unchanged; docs and changelog describe it.
**Independent test**: `charter context --action implement --json` in a fresh project yields only objects with codes from the five-value set; doctor warns for a reworded `UNKNOWN_SELECTION_DROPPED` and not for a lookalike prefix.
**Dependencies**: none.

T001 Red ATDD tests: context JSON `{code, message}`, doctor-by-code, per-code mapping (WP01)
T002 `GovernanceDiagnosticCode` + `GovernanceDiagnostic`; `ERROR_CODES.md`; `api.py` export (WP01)
T003 Resolver producers emit typed entries; `collect_governance_diagnostics` text view (WP01)
T004 Context JSON serialises `{code, message}`; contract ledger comment (WP01)
T005 Doctor classifies by code; retire `UNKNOWN_SELECTION_DIAGNOSTIC` api re-export (WP01)
T006 Compact context and runtime prompt render `.message` (WP01)
T007 Update existing assertions; regenerate golden fixtures (WP01)
T008 `docs/api` and rc8 changelog (WP01)

**Risks**: golden fixtures and many string assertions change; duck-typed seam stubs.

## WP02 – Typed synthesis slug helpers (#6461 item 3) (P3)

**Prompt**: `tasks/WP02-typed-slug-helpers.md`
**Goal**: `created_slugs_by_kind` / `created_slugs` take `ReconciliationDelta | None`, no `object`, no suppression; missing or foreign input still yields `[]`.
**Independent test**: mypy reveals the concrete parameter type; existing foreign-input tests stay green.
**Dependencies**: none (parallel with WP01).

T009 Tidy-first: hoist the deferred `ReconciliationDelta` import (WP02)
T010 Red typing test for the slug helpers' parameter (WP02)
T011 Annotate the helpers; keep `[]` for missing/foreign input (WP02)

**Risks**: sibling mission M2 edits `reach_only.py`; keep the diff to the import and two signatures.

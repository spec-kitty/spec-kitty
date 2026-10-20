# Tasks: Charter follow-ups tidy-up (#6539-#6543)

**Mission**: `charter-followups-tidy-01M5CCYJ`
**Planning base / merge target**: `tidy-charter-6539-followups`
**Inputs**: `spec.md`, `plan.md`, `research.md`, `decisions/`

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first runner tests: flagged skip before detect, apply()-raise is failed | WP01 | |
| T002 | `requires_git_repository` ClassVar + runner pre-detect gate | WP01 | |
| T003 | apply()-level NotInsideRepositoryError handled as a failed migration | WP01 | |
| T004 | Instrumented full-registry non-git audit; flag every resolver caller | WP01 | |
| T005 | `upgrade --dry-run --verbose` preview honours the flag outside git | WP01 | |
| T006 | Docs: ADR 2026-10-17-1 note, AGENTS.md migration authoring line, runner docstrings | WP01 | |
| T007 | Red-first tests: no function-level import between authority and code reader; interview abort paths | WP02 | |
| T008 | New `charter.activation.language_settlement` module; move settlement out of `language_authority` | WP02 | |
| T009 | Split settlement into pure decide + explicit `store_language_settlement` | WP02 | |
| T010 | `charter.activation.api` re-exports + re-export gate update | WP02 | |
| T011 | Interview: store languages after answers, before promotion; surface a store failure | WP02 | |
| T012 | Docs: `docs/api/charter-commands.md` language timing | WP02 | |
| T013 | Red-first seam test: `LANGUAGE_TOKENS` importable, records/helpers not | WP03 | [P] |
| T014 | `LANGUAGE_TOKENS` derived tuple in `language_catalog` | WP03 | [P] |
| T015 | Seam export, PUBLIC census disposition, facade re-export with a live caller | WP03 | [P] |
| T016 | ADR 2026-10-03-1 amendment note (seam widened by `LANGUAGE_TOKENS`) | WP03 | [P] |
| T017 | Reconcile tests: shipped-but-unselected table edge resolved; unshipped URN dangling | WP04 | [P] |
| T018 | Non-vacuity proof: mutate classification, positive case goes red | WP04 | [P] |

## Phase 1: Parallel work packages

### WP01: Migration repository requirement (#6539)

**Prompt**: [tasks/WP01-migration-repository-requirement.md](tasks/WP01-migration-repository-requirement.md)
**Goal**: a migration that needs a git repository declares it. The runner skips it before any step outside a repository, the preview does too, and an apply()-time repository error is a failed migration.
**Priority**: P1. **Independent test**: the non-git runner tests plus the full-registry audit.
**Requirements**: FR-001, FR-002, FR-003, C-002, C-004, NFR-001..003, SC-001, SC-002

T001 Red-first runner tests: flagged skip before detect, apply()-raise is failed (WP01)
T002 `requires_git_repository` ClassVar + runner pre-detect gate (WP01)
T003 apply()-level NotInsideRepositoryError handled as a failed migration (WP01)
T004 Instrumented full-registry non-git audit; flag every resolver caller (WP01)
T005 `upgrade --dry-run --verbose` preview honours the flag outside git (WP01)
T006 Docs: ADR 2026-10-17-1 note, AGENTS.md migration authoring line, runner docstrings (WP01)

**Dependencies**: none. **Risks**: missing a transitive resolver caller would bring #6437 back as a recorded failure; the instrumented audit is the guard. Ledger drift is accepted (C-002).

### WP02: Language settlement: one-way dependency, write with the answers (#6540, #6542)

**Prompt**: [tasks/WP02-language-settlement.md](tasks/WP02-language-settlement.md)
**Goal**: the settlement lives in its own module, decides without writing, and the interview stores `languages:` after the answers and before promotion.
**Priority**: P1. **Independent test**: the AST import test and the interview abort and failure tests.
**Requirements**: FR-004, FR-005, FR-006, C-005, NFR-001..004, SC-003, SC-005

T007 Red-first tests: no function-level import between authority and code reader; interview abort paths (WP02)
T008 New `charter.activation.language_settlement` module; move settlement out of `language_authority` (WP02)
T009 Split settlement into pure decide + explicit `store_language_settlement` (WP02)
T010 `charter.activation.api` re-exports + re-export gate update (WP02)
T011 Interview: store languages after answers, before promotion; surface a store failure (WP02)
T012 Docs: `docs/api/charter-commands.md` language timing (WP02)

**Dependencies**: none. **Risks**: every abort path between the language step and the answers write; promotion re-reading `config.yaml`.

### WP03: `LANGUAGE_TOKENS` on the offering seam (#6541)

**Prompt**: [tasks/WP03-language-tokens-on-the-seam.md](tasks/WP03-language-tokens-on-the-seam.md)
**Goal**: a plain-string token tuple is public seam contract, and the catalog records and family helpers stay internal.
**Priority**: P2. **Independent test**: the seam import test plus the public-surface and census gates.
**Requirements**: FR-007, FR-008, C-003, SC-004

T013 Red-first seam test: `LANGUAGE_TOKENS` importable, records/helpers not (WP03)
T014 `LANGUAGE_TOKENS` derived tuple in `language_catalog` (WP03)
T015 Seam export, PUBLIC census disposition, facade re-export with a live caller (WP03)
T016 ADR 2026-10-03-1 amendment note (seam widened by `LANGUAGE_TOKENS`) (WP03)

**Dependencies**: none. It must not edit files WP02 owns. **Risks**: the frozen-seam widening must be documented.

### WP04: Reconcile table-edge classification tests (#6543)

**Prompt**: [tasks/WP04-reconcile-table-edge-tests.md](tasks/WP04-reconcile-table-edge-tests.md)
**Goal**: prove that reconcile classifies table edges like the validation gate.
**Priority**: P3. **Independent test**: the two new reconcile tests and the recorded mutation proof.
**Requirements**: FR-009

T017 Reconcile tests: shipped-but-unselected table edge resolved; unshipped URN dangling (WP04)
T018 Non-vacuity proof: mutate classification, positive case goes red (WP04)

**Dependencies**: none. **Risks**: none (test-only).

## Parallelization

All four WPs are independent and own disjoint files, so they can run in parallel.

## Closeout (not a WP)

The orchestrator handles these after consolidation:
- the changelog entry;
- the conformance-corpus case filed against epic #6099;
- history cleanup, the pre-PR squad, and the draft PR.

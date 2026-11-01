# Work Packages: Docsite URL baseline, moves ledger and single index files

**Inputs**: Design documents from `kitty-specs/docsite-url-ledgers-01M6BRMR/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md, research/code-grounding.md

**Tests**: Required. ATDD-first (charter C-011): each WP commits a failing acceptance test before its implementation.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). The topology is `single_branch`, so WPs run sequentially in the repository root checkout.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** marks a subtask that can proceed in parallel (different files or components).
- Subtasks are **reference rows**, not checkboxes. Record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Acceptance tests for the ledgers (red) | WP01 | |
| T002 | `scripts/docs/moves_ledger.py`, the single ledger authority | WP01 | |
| T003 | Seed `site/moves.yaml` and `site/url-baseline.txt` | WP01 | |
| T004 | Repoint `redirect_stub_generator.py` and regenerate the map | WP01 | |
| T005 | Re-pin the redirect generator and spine tests | WP01 | |
| T006 | `docs-pages.yml` trigger paths and baseline-drift report | WP01 | [P] |
| T007 | Acceptance test: no docs tooling default names `kitty-specs/` (red) | WP02 | |
| T008 | `rename_reconcile.py` reads the ledger | WP02 | |
| T009 | `bulk_ref_rewrite.py` and `relative_link_fixer.py` default to the ledger | WP02 | |
| T010 | Re-pin the reconcile and rewrite tests | WP02 | |
| T011 | Acceptance tests: one index per folder, README routes redirected (red) | WP03 | |
| T012 | Delete the ADR-era stubs; fold `architecture/README.md` into `index.md` | WP03 | |
| T013 | Append the four README routes to the ledger; regenerate the map | WP03 | |
| T014 | Repoint live references to the removed READMEs | WP03 | |
| T015 | Changelog fragment | WP03 | [P] |

---

## Work Package WP01: Standing URL baseline and moves ledger (Priority: P1)

**Goal**: Two committed ledgers under `site/`, one module that owns them, and DocFX's redirect map derived from the moves ledger. Includes #3914's reconcile.
**Independent Test**: `pytest tests/docs/test_moves_ledger.py tests/docs/test_redirect_stub_generator.py tests/docs/test_redirect_spine.py` is green, and `redirect_stub_generator.py check-map` reports the map fresh.
**Prompt**: `tasks/WP01-standing-url-baseline-and-moves-ledger.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-012, NFR-001, NFR-002, NFR-003, NFR-004, C-001, C-002, C-005, C-006

### Included Subtasks

T001 Acceptance tests for the ledgers (red) (WP01)
T002 `scripts/docs/moves_ledger.py`, the single ledger authority (WP01)
T003 Seed `site/moves.yaml` and `site/url-baseline.txt` (WP01)
T004 Repoint `redirect_stub_generator.py` and regenerate the map (WP01)
T005 Re-pin the redirect generator and spine tests (WP01)
T006 [P] `docs-pages.yml` trigger paths and baseline-drift report (WP01)

### Implementation Notes

- The seed is one throwaway script run once. Record the command in the ledger header; it is not committed tooling.
- The site walk comes from the local DocFX build recorded in the grounding note.

### Dependencies

- None (starting package).

### Risks & Mitigations

- The deploy `coverage` step now reads a baseline of about 965 routes. A PR-time mirror test and a local DocFX run protect it.

---

## Work Package WP02: No Mission-scoped occurrence map in docs tooling (Priority: P1)

**Goal**: Close #2358 for every script: `rename_reconcile.py`, `bulk_ref_rewrite.py` and `relative_link_fixer.py` default to `site/moves.yaml`.
**Independent Test**: the new defaults test is green; the reconcile and rewrite tests pass.
**Prompt**: `tasks/WP02-no-mission-scoped-occurrence-map.md`
**Requirement Refs**: FR-007, NFR-003

### Included Subtasks

T007 Acceptance test: no docs tooling default names `kitty-specs/` (red) (WP02)
T008 `rename_reconcile.py` reads the ledger (WP02)
T009 `bulk_ref_rewrite.py` and `relative_link_fixer.py` default to the ledger (WP02)
T010 Re-pin the reconcile and rewrite tests (WP02)

### Dependencies

- Depends on WP01.

### Risks & Mitigations

- The link rewriters take source-path pairs. `moves_ledger.source_pairs()` converts routes to `docs/` paths. Explicit `--occurrence-map` fixtures keep the legacy shape.

---

## Work Package WP03: One index file per folder (Priority: P2)

**Goal**: `adr/1.x`, `adr/2.x`, `adr/3.x` and `architecture` each keep only `index.md`, their `README.html` routes redirect, and nothing live points at the removed files.
**Independent Test**: the one-index test and the README-route assertions are green; `grep` finds no live reference to the removed READMEs.
**Prompt**: `tasks/WP03-one-index-file-per-folder.md`
**Requirement Refs**: FR-008, FR-009, FR-010, FR-011, C-003, C-004, C-007

### Included Subtasks

T011 Acceptance tests: one index per folder, README routes redirected (red) (WP03)
T012 Delete the ADR-era stubs; fold `architecture/README.md` into `index.md` (WP03)
T013 Append the four README routes to the ledger; regenerate the map (WP03)
T014 Repoint live references to the removed READMEs (WP03)
T015 [P] Changelog fragment (WP03)

### Dependencies

- Depends on WP01.

### Risks & Mitigations

- The `related:` edits overlap the parallel frontmatter migration (#6929). Keep them to removing or retargeting the dangling entry.
- Editing `site/moves.yaml` and `scripts/docs/redirect_map.yaml` lies outside this WP's owned files; WP01 owns them. That is an append-only, recorded out-of-map edit.

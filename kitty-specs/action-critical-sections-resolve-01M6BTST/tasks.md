# Work Packages: Action-critical charter sections resolve in the active charter

**Inputs**: Design documents from `/kitty-specs/action-critical-sections-resolve-01M6BTST/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md

**Tests**: Required. This is a defect fix: the regression test must be witnessed
failing through the production entry point before the renderer changes.

**Organization**: Two work packages. WP01 owns the code change and its tests;
WP02 owns the contract document and the changelog entry (planning surfaces only).

**Prompt Files**: `tasks/WP01-*.md`, `tasks/WP02-*.md`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files).
- Subtasks are reference rows; record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/`, `tests/`, `docs/`, `kitty-specs/`.

---

## Work Package WP01: Filter the advertised action-critical sections (Priority: P1) 🎯 MVP

**Goal**: `charter context` advertises only action-critical charter headings the
active charter resolves; a present heading keeps its verbatim body and recovery
fetch stanza, an absent (or empty, or fence-masked) heading is not advertised,
and the empty block header disappears when nothing resolves.
**Independent Test**: A minimal consumer charter with none of the three headings
produces zero `--include section:` lines through `build_charter_context`; a
charter with all three still produces three bodies and three stanzas.
**Prompt**: `/tasks/WP01-filter-advertised-sections.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, NFR-003, C-001, C-003, SC-001, SC-002, SC-003

### Included Subtasks

T001 [P] Write the failing regression test on a minimal consumer charter through `build_charter_context` in `tests/charter/test_context_action_critical_minimal.py`
T002 Add the resolving-heading predicate and filter `render_critical_section_bodies` in `src/charter/activation/context_renderers/section_bodies.py`
T003 Update `tests/charter/test_context_section_bodies.py` expectations that pin missing-heading advertising
T004 Update the renderer module docstring and `_render_fetch_stanza`/`render_critical_section_include` docstrings to state the filtered-set rule
T005 Run the targeted suites plus ruff and mypy on the touched surface

### Implementation Notes

- Red first: T001 must fail on the unpatched renderer for the right reason (three
  advertised selectors), then T002 makes it pass.
- Reuse `_extract_section_body`; do not add a second charter parser.
- `render_critical_section_bodies` keeps returning `""` when nothing resolves.
- Keep the direct `section:<slug>` placeholder behaviour (FR-004).

### Parallel Opportunities

- T001 can be written against the current behaviour before T002 lands; T003/T004
  are independent edits once T002's signature is settled.

### Dependencies

- None (starting package). WP02 depends on this package.

### Risks & Mitigations

- Token-budget substitution derives selectors from the rendered text → it cannot
  manufacture a selector for a heading no longer rendered; add a targeted check
  in the regression test if practical.
- ATDD anchors for present sections must stay green → run
  `tests/specify_cli/next/test_wp_prompt_governance_contract.py` in T005.

---

## Work Package WP02: Align the published contract and changelog (Priority: P2)

**Goal**: The resolver contract row, the verbatim-OR-fetch section of that
contract and the `[Unreleased]` changelog entry state the filtered-set rule, so
the shipped behaviour and its documented contract agree.
**Independent Test**: Reading the contract row and the changelog entry alone
tells a maintainer that missing headings are not advertised and why.
**Prompt**: `/tasks/WP02-contract-and-changelog.md`
**Requirement Refs**: FR-006, C-002, SC-004

### Included Subtasks

T006 Update the `Action-Critical Charter Sections` row and the verbatim-OR-fetch stanza section in `kitty-specs/wp-prompt-governance-payload-01KRR8HS/contracts/charter-context-resolver.md`
T007 Add the `[Unreleased]` entry for #6968 in `docs/changelog/CHANGELOG.md`
T008 Run the docs lint/freshness checks that cover the touched docs surfaces

### Implementation Notes

- The contract edit narrows the row's "Required when" and its content rule; do
  not rewrite the rest of the historical contract.
- Changelog: bold impact-first lead with `(#6968)`, before/after, under 1,200
  characters.
- No new doc page ⇒ no docs-index regeneration expected; verify rather than
  rebuild the whole reference (shared machine cache).

### Parallel Opportunities

- T006 and T007 are separate files and can be done in either order.

### Dependencies

- Depends on WP01 (the changelog names the shipped behaviour).

### Risks & Mitigations

- Changelog merge conflicts with other concurrent missions → keep the entry
  small and inside the existing `[Unreleased]` block's structure.

---

## Dependency & Execution Summary

- **Sequence**: WP01 → WP02.
- **Parallelization**: within WP01 the regression test can be authored while the
  predicate is designed; both WPs can be reviewed together.
- **MVP Scope**: WP01 alone fixes the reported defect; WP02 makes the fix
  documented and releasable.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| FR-004 | WP01 |
| FR-005 | WP01 |
| FR-006 | WP02 |
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| NFR-003 | WP01 |
| C-001 | WP01 |
| C-002 | WP02 |
| C-003 | WP01 |
| SC-001 | WP01 |
| SC-002 | WP01 |
| SC-003 | WP01 |
| SC-004 | WP01, WP02 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Regression test on minimal consumer charter | WP01 | P1 | Yes |
| T002 | Filter advertised headings in the renderer | WP01 | P1 | No |
| T003 | Update unit-test expectations | WP01 | P1 | Yes |
| T004 | Docstrings state the filtered-set rule | WP01 | P2 | Yes |
| T005 | Targeted tests, ruff, mypy | WP01 | P1 | No |
| T006 | Update the resolver contract | WP02 | P2 | Yes |
| T007 | Changelog entry for #6968 | WP02 | P2 | Yes |
| T008 | Docs lint/freshness check | WP02 | P2 | No |

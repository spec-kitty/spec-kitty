---
description: "Work package task list for the orchestrator error-code prose guard"
---

# Work Packages: Keep the orchestrator error-code prose enumerations honest

**Inputs**: Design documents from `kitty-specs/orchestrator-error-code-prose-guard-01M6EJQS/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md

**Tests**: Required — the guard is the deliverable. WP01 lands it red against the
unmodified docs and proves it fails closed; WP02 turns it green by making the
enumerations complete (spec SC-001, SC-002, SC-003, SC-005).

**Organization**: Two work packages, split along the red/green boundary that the
mission is really about: the guard is a `code_change` surface (a test module), the
enumerations are `planning_artifact`/docs surfaces. WP02 depends on WP01.

**Prompt Files**: `kitty-specs/orchestrator-error-code-prose-guard-01M6EJQS/tasks/WP01-*.md`,
`.../WP02-*.md`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- **Single project**: `src/`, `tests/`, `docs/` — this mission follows that layout.

---

## Work Package WP01: The red-first prose-enumeration guard (Priority: P1) 🎯 MVP

**Goal**: One contract test class that parses each documented enumeration region,
compares it with `orchestrator_api.allowed_error_codes` in both directions, reports
duplicates, and fails closed when an anchor is missing or the region is empty.
**Independent Test**: `uv run pytest tests/contract/test_orchestrator_api.py -q -k prose`
fails on the unmodified docs, naming the 22 missing codes in the API reference and the
23 in the skill table; the in-memory fixtures prove the fail-closed and duplicate paths.
**Prompt**: `/tasks/WP01-prose-enumeration-guard.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-008, FR-009, FR-010, NFR-001, NFR-002, C-001, C-002, C-003, SC-002, SC-003, SC-005

### Included Subtasks

T001 Add the surface constants and the pure region parser (`parse_enumeration_entries`) to the contract test module
T002 Add the anchor, empty-region and duplicate failure paths, driven by in-memory text fixtures
T003 Add the per-surface equality test against `allowed_error_codes` with sorted per-surface diffs and a same-fixture positive control
T004 Run the class against current `main`'s docs and record the RED output (22 and 23 missing) as the red-first proof

### Implementation Notes

- Red first: T004 must be a *recorded* red against the unmodified docs before any docs
  edit. Do not touch `docs/api/orchestrator-api.md` or the skill reference in this WP.
- The parser is pure over `(text, surface_kind)`; every fail-closed case is exercised
  without editing a real file (NFR-001: no network, no subprocess).
- Read the authority through the `orchestrator_api_contract` fixture; never add a
  literal code list to the test (FR-010, C-001).
- Do not modify or weaken `TestAllowedErrorCodes` (C-003).

### Parallel Opportunities

T001 → T002/T003 are sequential (same file). T004 needs both.

---

## Work Package WP02: Complete, bounded enumerations on both surfaces (Priority: P1)

**Goal**: `docs/api/orchestrator-api.md` and the shipped operator-skill reference each
enumerate all 80 contract codes as their own list item / table row, inside a single
anchor pair, with the sub-code tables left outside.
**Independent Test**: `uv run pytest tests/contract/test_orchestrator_api.py -q -k prose`
passes; removing one surface's fix turns it red again naming that surface's codes.
**Prompt**: `/tasks/WP02-bound-enumerations.md`
**Requirement Refs**: FR-006, FR-007, FR-009, NFR-003, NFR-004, C-004, C-005, SC-001, SC-004, SC-005

### Included Subtasks

T001 Wrap the API reference's canonical list in the anchor pair and restore the 22 missing codes with one-line meanings
T002 Wrap the skill reference's `## Error Code Summary` table in the anchor pair and add the 23 missing rows
T003 Verify the guard green, per surface, and re-verify red by reverting each surface on its own (half-by-half)
T004 Run the docs gates: markdownlint on both files, `check_docs_freshness --ci` errors=0, and the contract module green

### Implementation Notes

- Keep the contract-version history bullets and per-verb "Error codes:" narrative
  untouched (C-005): they are narrative, not enumeration.
- The `data.preflight_error_code`, `data.teardown_error_code` and origin-freshness
  tables stay outside the region (C-005, research D-1) — do not "tidy" them in.
- Both surfaces stay human-readable prose; no generated block, no link to the JSON
  (C-004).
- Annotations after a code are fine, but the leading backticked token must be the code.

### Parallel Opportunities

T001 and T002 touch different files and can proceed in parallel; T003/T004 need both.

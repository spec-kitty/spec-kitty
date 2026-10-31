# Work Packages: Reduce charter activate/deactivate write latency

**Inputs**: Design documents from `kitty-specs/charter-write-roundtrip-latency-01M68ZVK/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md

**Tests**: Testing work is explicit and requested (FR-004, FR-005): the mission exists to fix a
measured regression and pin it, so tests are a deliverable, not an afterthought.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work
package is independently deliverable and testable.

**Prompt Files**: Each work package references a matching prompt file in `tasks/`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single Python project: `src/`, `tests/`, `docs/`.

---

## Work Package WP01: Cheap, exact document equality and a single-pass section writer (Priority: P0)

**Goal**: `charter/activation/charter_yaml_io.py` stops paying a full serialise-and-reparse
comparison for a document it already holds, and can apply several owned sections in one
prepared write cycle, with **zero** change to any equality verdict or output byte.
**Independent Test**: the equivalence corpus and the byte-identity corpus both pass, and the
existing `tests/charter/**` suite is green with no assertion edits.
**Prompt**: `/tasks/WP01-equality-and-multi-section-prepare.md`
**Requirement Refs**: FR-002, FR-007, NFR-002, NFR-003

### Included Subtasks

T001 [P] Write the equality-equivalence corpus test (characterises today's verdicts before the change)
T002 Implement structural document equality with a leaf-level event fallback
T003 Add `prepare_charter_yaml_sections` and make `prepare_charter_yaml_section` delegate to it
T004 Write the byte-identity test: one prepared write over N sections == N prepared writes

### Implementation Notes

- T001 is the red-first guard for a behaviour-preserving refactor: it must pass against the
  **unmodified** implementation and keep passing afterwards. A test that cannot fail against the
  old code proves nothing here, so T001 additionally asserts the corpus contains at least one
  pair the *old* implementation calls unequal and one it calls equal for each category
  (identical, one leaf apart, one key apart, tagged scalar, anchor/alias, key order).
- T002 keeps `left == right` as the first clause (it is what makes the no-op case free) and
  keeps `_yaml_value_events` as the fallback, applied only where a subtree genuinely differs.
- T003 must route validation through the existing `_validate_section` / `_validate_removals` —
  one code path, not a parallel one — and must keep `precondition_changed` receipts working.

### Parallel Opportunities

- T001 and T003 touch different things and can proceed together; T002 depends on T001.

### Dependencies

- None (starting package).

### Risks & Mitigations

- The equality fallback exists for opaque tagged scalars, anchors and aliases. Getting it wrong
  in the *lenient* direction silently accepts a lossy render. Mitigation: T001's corpus is
  written first and includes the negative cases; the assertion is "verdicts are identical", not
  "the new one is at least as strict".
- `render_yaml_document`'s final verify is the alias guard; it must stay exactly as strict.

---

## Work Package WP02: One write cycle per compiled-charter refresh (Priority: P0) 🎯 MVP

**Goal**: `write_compiled_charter` refreshes `catalog` and `metadata` in one prepared write and
takes the preserved-timestamp decision from that same read.
**Independent Test**: `charter activate`/`deactivate` and `charter generate` targeted suites are
green with identical `charter.yaml` output, and the round-trip count drops from 10 to 2.
**Prompt**: `/tasks/WP02-single-write-cycle.md`
**Requirement Refs**: FR-001, FR-003, NFR-001

### Included Subtasks

T005 Rewire `write_compiled_charter` to one `prepare_charter_yaml_sections` call
T006 Derive `preserved_generated_at` from the document the merged writer loaded
T007 Prove output parity across the activation and generate suites

### Implementation Notes

- Order matters: the existing `catalog` write, then `metadata` write, then
  `provision_mission_type_activations`, then `restamp_bundle_hash` must stay in that order.
- The bootstrap branch (no existing `charter.yaml`) is untouched.
- Two callers: `specify_cli/cli/commands/charter/activate.py` (through `recompile_catalog`) and
  `.../generate.py`.

### Parallel Opportunities

- T005/T006 are one change; T007 runs after.

### Dependencies

- Depends on WP01 (the merged prepare API).

### Risks & Mitigations

- `charter generate` is the second caller and the one that would notice a semantic change in
  `_preserved_generated_at`; its suite is the guard.
- A no-op recompile must still not restamp `generated_at` and must still write no bytes.

---

## Work Package WP03: Repository-scale regression tests (Priority: P1)

**Goal**: A structural count that fails when a redundant document cycle returns (6 whole-document
round trips per recompile, against 18 for the two-cycle shape it replaced), and a
repository-scale timing measure that asserts a runner-relative ratio instead of seconds.
**Independent Test**: reverting WP02's single-cycle change turns the count test red; the ratio
test stays green under concurrent machine load.
**Prompt**: `/tasks/WP03-repository-scale-regression-tests.md`
**Requirement Refs**: FR-004, FR-005, NFR-002, NFR-004

### Included Subtasks

T008 [P] Write the round-trip count test and prove it red against the two-cycle implementation
T009 [P] Add the repository-scale ratio timing test with its limit in the shared helper

### Implementation Notes

- The count must be taken at a boundary that catches a redundant *parse*, not merely a redundant
  call, or a re-parse inside a single render slips past it.
- The fixture is a copy of this repository's own `.kittify/` (+ `packs/`), copied into
  `tmp_path`; nothing is mutated in place and no absolute checkout path is asserted.
- Per ADR `docs/adr/4.x/2026-10-05-2-runner-relative-performance-budgets.md`, every limit lives
  in `tests/_perf_helpers.py`; `tests/architectural/test_perf_limit_authority.py` must stay green
  and must not need an allowlist entry.

### Parallel Opportunities

- T008 and T009 are independent files.

### Dependencies

- Depends on WP01 and WP02.

### Risks & Mitigations

- `tests/architectural/test_performance_marker_guard.py` forbids a non-timing bare `assert` in a
  `performance`-marked test → use `assert_timing_budget` from the shared helper.
- A ratio whose floor is a *different* command can hide a regression that slows both. Use a
  floor that does not share the write path (a pure read) and record which floor in the docstring.

---

## Work Package WP04: Record the justified budget (Priority: P2)

**Goal**: The next engineer finds the read floor, the post-fix write cost, the ratio and what
would have to change to reach the charter's 2 s, and the changelog tells users what improved.
**Independent Test**: every figure in the ADR can be re-derived from the committed tests' output.
**Prompt**: `/tasks/WP04-record-the-budget.md`
**Requirement Refs**: FR-006, SC-005

### Included Subtasks

T010 Write the ADR recording the justified budget for repositories of this size
T011 Add the `[Unreleased]` changelog entry and regenerate the docs surfaces the ADR touches

### Implementation Notes

- ADR numbering/date: `docs/adr/4.x/2026-10-31-N-<slug>.md`, `N` chosen as the next free number
  for that date.
- Regenerate only what this ADR needs: the era index row and the page inventory. Verify with
  `scripts.docs.check_docs_freshness --ci` (errors=0) rather than trusting a full rebuild.

### Parallel Opportunities

- T010 before T011.

### Dependencies

- Depends on WP02 (needs the post-fix numbers) and WP03 (needs the test that re-derives them).

### Risks & Mitigations

- The shared machine's global docs cache is rewritten by other agents → regenerate only the
  touched surface and verify with the freshness check; report any non-determinism.

---

## Dependency & Execution Summary

- **Sequence**: WP01 → WP02 → WP03 → WP04.
- **Parallelization**: WP03's two test files are independent; WP01 and WP03's timing test can
  start once their prerequisites land.
- **MVP Scope**: WP01 + WP02 deliver the user-facing fix. WP03 makes it durable. WP04 records
  the budget.

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP02 |
| FR-002 | WP01 |
| FR-003 | WP02 |
| FR-004 | WP03 |
| FR-005 | WP03 |
| FR-006 | WP04 |
| FR-007 | WP01 |
| NFR-001 | WP02 |
| NFR-002 | WP01, WP03 |
| NFR-003 | WP01 |
| NFR-004 | WP03 |
| C-001 | WP01 |
| C-002 | WP01 |
| C-003 | WP03 |
| C-004 | WP01, WP02 |
| SC-005 | WP04 |

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Equality-equivalence corpus | WP01 | P0 | Yes |
| T002 | Structural equality with leaf fallback | WP01 | P0 | No |
| T003 | Multi-section prepared write | WP01 | P0 | Yes |
| T004 | Byte-identity corpus | WP01 | P0 | No |
| T005 | Rewire `write_compiled_charter` | WP02 | P0 | No |
| T006 | Preserved timestamp from the same read | WP02 | P0 | No |
| T007 | Output parity across activation/generate suites | WP02 | P0 | No |
| T008 | Round-trip count test (proved red) | WP03 | P1 | Yes |
| T009 | Repository-scale ratio timing test | WP03 | P1 | Yes |
| T010 | ADR: justified budget | WP04 | P2 | No |
| T011 | Changelog + docs surfaces | WP04 | P2 | No |

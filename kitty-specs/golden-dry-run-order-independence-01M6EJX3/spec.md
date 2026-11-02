# Mission Specification: Golden dry-run rendering is order-independent

**Mission Branch**: `kitty/mission-golden-dry-run-order-independence-01M6EJX3`
**Created**: 2026-11-02
**Status**: Draft
**Input**: Issue #7030 — `test_golden_applied_dry_run` is order-dependent: its repair-preview count
depends on whether an earlier test materialized the isolated home.

## Problem

`tests/upgrade/test_upgrade_outcome_rendering.py::test_golden_applied_dry_run` drives the real
`spec-kitty upgrade --dry-run` command and pins its complete rendered output. One line of that
output — the supporting-repair preview — is computed live by
`upgrade_module._supporting_repair_preview`, which assesses the pytest-isolated home
(`tests/conftest.py::_isolated_worker_home`, keyed per xdist worker, not per test). On an empty
isolated home the assessment yields 125 create effects; after an earlier test in the same worker
has run a real upgrade and materialized that home, the same fixture yields 1.

So the golden passes when the module runs whole (`test_golden_applied_run` materializes the home
first) and fails when it is selected alone (`-k`, `--lf`, `-x` after a failure, or a CI shard
that splits the module). The difference is environment state, not code under test. Reproduced on
`main` at `9aed3a80`:

```text
- Would repair 1 supporting surface paths (including 0 manifests). Use --plan-json
+ Would repair 125 supporting surface paths (including 0 manifests). Use --plan-json
```

This is a test-quality defect (`DIRECTIVE_041`: judge the test). The production preview is
correct; the golden is asserting the state of a shared worker home it does not own.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The golden passes however it is selected (Priority: P1)

As a maintainer, I want the dry-run golden to pass identically when its node is selected alone and
when the whole module runs, so a shard, `-k` or `--lf` run reports the code's behaviour rather
than the fixture's history.

**Why this priority**: P1 — the defect blocks node-selected and sharded runs of an otherwise
green module, and it teaches contributors to distrust a real golden.

**Independent Test**: Run
`pytest tests/upgrade/test_upgrade_outcome_rendering.py -k golden_applied_dry_run -q` alone in a
fresh process, then the whole module. Both must pass, twice in a row, with no grader change to the
pinned text.

**Acceptance Scenarios**:

1. **Given** an isolated worker home that no earlier test has materialized, **When** the golden
   dry-run node runs alone, **Then** it passes and prints the pinned dry-run text.
2. **Given** the same module run whole (an earlier test has materialized the home), **When** the
   golden dry-run node runs, **Then** it passes with exactly the same pinned text.
3. **Given** the golden's pinned text, **When** the supporting-repair preview is *not* consulted
   during a dry run, **Then** the golden fails — the preview line is still covered by the golden,
   not silently dropped.

---

### User Story 2 - The golden stays a rendering oracle (Priority: P2)

As a reviewer, I want the golden to keep pinning the full rendered dry-run output — table,
preview notice, dry-run banner, migration sections and closing line — so the fix removes the
environment dependency without weakening what the test proves.

**Why this priority**: P2 — the fix must not trade a flaky assertion for a weaker one.

**Independent Test**: The golden still asserts equality against one complete expected-output
constant; a one-character change to any rendered line makes it fail.

**Acceptance Scenarios**:

1. **Given** the fixed golden, **When** a rendered line changes (banner, table, section order,
   closing line), **Then** the golden fails.

### Edge Cases

- A future refactor that stops consulting the preview during a dry run must fail the golden
  (the pinned preview line is an assertion, not decoration).
- The matrix rows in the same module already stub the preview; the golden must use the same
  seam so the module has one way to make the preview deterministic.
- An incomplete preview (`notice, incomplete=True`) is a different branch; the golden's fix must
  not change which branch it exercises (a complete preview prints in text mode).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Node-selected golden passes | As a maintainer, I want the dry-run golden to pass when selected alone so node-selected and sharded runs are trustworthy. | High | Open | [build] | no |
| FR-002 | Whole-module golden unchanged | As a maintainer, I want the same pinned text when the module runs whole so both selections agree. | High | Open | [ratchet] | no |
| FR-003 | Golden still pins the preview line | As a reviewer, I want the golden to fail if the dry run no longer emits the supporting-repair preview so the fix does not weaken coverage. | High | Open | [ratchet] | no |
| FR-004 | No production change | As an operator, I want the fix confined to the test seam so shipped `spec-kitty upgrade` behaviour is untouched. | Medium | Open | [ratchet] | yes — paired with the unchanged `src/` diff (zero production lines) in the same PR |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Deterministic under repetition | Two consecutive single-node runs and one whole-module run all pass with no intervening state reset. | Reliability | High | Open |
| NFR-002 | No suite growth | The mission adds at most one focused regression assertion in the existing golden test; no new test file and no new subprocess pytest run. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No weakened gates | The fix must not skip, xfail, deselect or loosen any assertion; the expected output stays an exact-match golden. | Technical | High | Open |
| C-002 | Existing seam | Determinism comes from stubbing `upgrade_module._supporting_repair_preview` — the seam the module's matrix rows and `tests/upgrade/test_upgrade_integration.py` already use — not from a new test-only hook in `src/`. | Technical | High | Open |
| C-003 | Issue #7030 scope | Only the dry-run golden's environment dependency is in scope; the shared per-worker home fixture (`tests/conftest.py::_isolated_worker_home`) is not changed by this mission. | Technical | Medium | Open |

### Key Entities

- **Golden dry-run test**: `test_golden_applied_dry_run`, the characterisation oracle that pins the
  full rendered text of `spec-kitty upgrade --dry-run`.
- **Supporting-repair preview**: `_supporting_repair_preview(project_path) -> (notice, incomplete)`,
  the only environment-derived input the golden still read live.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `pytest tests/upgrade/test_upgrade_outcome_rendering.py -k golden_applied_dry_run -q` passes from a clean process, where it currently fails with `125` vs `1` paths. — [build] · no-op passable: no
- **SC-002**: `pytest tests/upgrade/test_upgrade_outcome_rendering.py -q` passes, and the pinned dry-run text is byte-identical to today's expected constant. — [ratchet] · no-op passable: no
- **SC-003**: `git diff --stat origin/main -- src/` is empty for this mission. — [ratchet] · no-op passable: yes — paired with SC-001, which cannot pass unless the test seam changed

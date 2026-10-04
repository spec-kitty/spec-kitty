# Mission Specification: Regression-slice test cleanup

**Mission Branch**: `issue-5618-regression-slice-cleanup` (target and merge branch)
**Created**: 2026-10-04
**Status**: Draft
**Input**: User description: "Regression-slice cleanup: deliver spec-kitty/spec-kitty issues #5618, #5619, #5620, #5621, #5622 as one mission — apply the test-suite-quality-assessment ledger verdicts (MARKER-ONLY, SPLIT-BY-KIND, SHIFT-LEFT with seam unit tests first, RETIRE only with planted-break-proven guards, FIX weak oracles), add the unguarded _load_charter_scope_config unit test (#5620 priority), and make the two chmod-based unreadable-path tests root-independent (#5622). Test-only; no product changes under src/."

## Intent Summary

- **Primary actor**: a Spec Kitty maintainer (or CI on their behalf) who runs the per-PR test
  suite and reads its result as the release signal.
- **Trigger**: the 2026-10-04 `test-suite-quality-assessment` run over the
  `regression`-marked slice produced per-file verdict ledgers in issues #5618, #5619, #5620
  and #5621, plus a root-only failure report in #5622.
- **Desired outcome**: the `regression` marker covers only tests that are genuinely
  issue-pinned reproductions; slow end-to-end files whose contracts are held by cheaper seam
  tests are trimmed to one smoke per behaviour family; every retired or trimmed test names a
  covering guard that was shown to go red on a planted break; the one unguarded fix
  (charter scope config loading) gains a guard; and the suite gives the same verdict whether
  it runs as root or not.
- **Rule that must always hold**: no behaviour loses its last guard. A test is removed only
  when a named, cheaper guard goes red on a planted break of the same behaviour; if the guard
  stays green, the test stays.
- **Boundary**: this is test-suite work. Product code is not changed; a real product defect
  found along the way is filed as a separate issue.
- **Discovery**: satisfied by the operator brief (non-interactive run); recorded as decision
  `01M42WD0X2R1EWYZSB0ZEYET84`.

## Domain Language

| Term | Meaning here | Avoid |
|------|--------------|-------|
| `regression` marker | Issue-pinned reproduction test (per `tests/regression/README.md`) | using it as a speed tier or a "this once was a bug" label |
| Verdict | One of MARKER-ONLY, SPLIT-BY-KIND, SHIFT-LEFT, RETIRE, FIX, KEEP from the ledger | "cleanup" without a verdict |
| Planted break | A temporary edit to product code that disables the behaviour a test names, run against named test files only, then reverted | "mutation run" over whole directories |
| Covering guard | The named cheaper test that holds a behaviour after a slower test is trimmed | — |
| Smoke | The one end-to-end test kept per behaviour family after a SHIFT-LEFT | — |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Unguarded fix gains a guard (Priority: P1)

A maintainer reverts the #4600 fix in the charter scope config reader. Today no test notices.
After this mission a unit test at that reader goes red, naming the offending file.

**Why this priority**: it is the only defect class in the slice with no working guard (#5620).

**Independent Test**: plant the break (the reader returns nothing instead of raising) and run
only the new unit test file; it must fail, and pass again once reverted.

**Acceptance Scenarios**:

1. **Given** a charter config file that is not valid UTF-8, **When** the scope config is
   loaded, **Then** a charter pack config error naming that file is raised.
2. **Given** a charter config file with malformed YAML, **When** the scope config is loaded,
   **Then** a charter pack config error naming that file is raised.

---

### User Story 2 - Marker means what it says (Priority: P2)

A maintainer selects `-m regression` and gets only issue-pinned reproductions, not unit,
component or contract tests that merely sat in a file with a module-level marker.

**Why this priority**: the mislabel spreads the slow-lane label onto fast tests and keeps
them out of the fast tier.

**Independent Test**: collect `-m regression` before and after; every file the ledgers mark
MARKER-ONLY contributes zero tests afterwards, and SPLIT-BY-KIND files contribute only the
pinned tests.

**Acceptance Scenarios**:

1. **Given** a MARKER-ONLY file, **When** the suite collects with `-m regression`, **Then** no
   test from that file is selected, and the file's tests still run under their tier marker.
2. **Given** a SPLIT-BY-KIND file, **When** collected with `-m regression`, **Then** only the
   ledger-named issue pins are selected.

---

### User Story 3 - Slow end-to-end files shrink without losing coverage (Priority: P2)

A maintainer's per-PR run no longer replays consolidate/abort or CLI end-to-end flows once
per decision-table row when a seam test already pins each row.

**Independent Test**: for each trimmed family, a planted break in the product turns the named
covering guard red, and the kept smoke still passes on the unbroken tree.

**Acceptance Scenarios**:

1. **Given** a SHIFT-LEFT file, **When** trimmed, **Then** one smoke per behaviour family
   remains and the trimmed rows are held by named seam tests.
2. **Given** a seam the ledger says has no direct unit test, **When** the e2e is trimmed,
   **Then** the seam unit test was added first, in an earlier commit.

---

### User Story 4 - Root and non-root runs agree (Priority: P3)

A maintainer running the suite as root in a cloud container sees the same result as CI
running as a regular user.

**Independent Test**: run the two #5622 tests as root; they skip (or pass) with a stated
reason instead of failing.

**Acceptance Scenarios**:

1. **Given** the suite runs with effective uid 0, **When** an unreadable-path test runs,
   **Then** it does not fail because root bypasses file mode bits.

### Edge Cases

- A covering guard stays green on the planted break: the test is not redundant; keep it and
  record that in the PR body.
- A ledger row names a file or test that no longer exists or has changed shape on `main`:
  apply the verdict's intent to the current shape and record the deviation.
- A removed marker leaves a test with no tier marker: give it the tier marker its siblings use
  so CI marker routing stays complete.
- A ledger row was not planted by the review ("needs an over-trigger break; not done"): plant
  it now or keep the test.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Guard the charter scope config reader | As a maintainer, I want a unit test that fails when the charter scope config reader stops refusing undecodable or malformed config files so that the #4600 fix is guarded (#5620 item 1). | High | Open | [build] | no — proved red on the planted `return None` break |
| FR-002 | Retire or unmark the #4600 CLI replay | As a maintainer, I want the CLI replay that stays green on its own fix's revert unmarked or retired once FR-001 lands so that it no longer pretends to guard the fix (#5620 item 1). | Medium | Open | [build] | no — collection diff shows it leaves the `regression` slice |
| FR-003 | Apply the #5620 status/runtime/coordination ledger | As a maintainer, I want the remaining #5620 verdicts applied (RETIRE the #5513 file, FIX+unmark the #5440 file, SHIFT-LEFT #4642 with dispatch-mode unit tests first, SPLIT-BY-KIND the single-branch write-checkout e2e, unmark the trio truth table) so that the slice holds only real pins. | Medium | Open | [build] | no — each retirement carries a planted-break record |
| FR-004 | Apply the #5621 migration/upgrade/charter ledger | As a maintainer, I want the #5621 verdicts applied (four SPLIT-BY-KIND files, two MARKER-ONLY files, the #4962 SHIFT-LEFT port-then-retire, the T030 retirement) so that module-level markers stop spreading onto non-pins. | Medium | Open | [build] | no — collection diff plus planted breaks |
| FR-005 | Apply the #5619 CLI ledger | As a maintainer, I want the #5619 verdicts applied (MARKER-ONLY files, SPLIT-BY-KIND files, `_partition_paths_by_primary_kind` and `_slugify_feature_input` seam units before trimming the 4905 and non-ASCII e2e files, the 2745 oracle tightened) so that CLI pins sit at the right layer. | Medium | Open | [build] | no — the 2745 oracle is shown red on a planted break |
| FR-006 | Apply the #5618 consolidation/terminus/lanes ledger | As a maintainer, I want the #5618 verdicts applied (MARKER-ONLY and SPLIT-BY-KIND files; the #5569 deleted-branch REFUSE and approved-dependency PASS units added before trimming; SHIFT-LEFT files trimmed to one smoke per family) so that the slowest per-PR files shrink. | Medium | Open | [build] | no — each trim carries a planted-break record |
| FR-007 | Root-independent unreadable-path tests | As a maintainer running as root, I want the chmod-based unreadable-path tests to skip with a reason or inject the failure at the I/O seam so that root and non-root runs agree (#5622). | Medium | Open | [build] | no — the tests fail as root on the base and do not after |
| FR-008 | Planted-break evidence for every removal | As a reviewer, I want every RETIRE and every trimmed SHIFT-LEFT test backed by a recorded planted break (product edit, guard result, revert) so that no behaviour silently loses its last guard. | High | Open | [build] | no — a removal without a record fails review |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Per-PR runtime | Summed per-PR runtime of the files touched drops by at least 50% of what the ledgers estimate for the applied verdicts (≈820 s for #5618, ≈98 s for #5620), measured with `--durations` on the touched files before and after. | Performance | Medium | Open |
| NFR-002 | Fast seam tests | Every seam unit test added by this mission runs in under 1 s each on a developer machine. | Performance | Medium | Open |
| NFR-003 | Clean tooling | Changed and added test files pass `ruff check` and `ruff format --check --force-exclude` with zero findings and no new suppressions. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Test-only | No product code under `src/` changes, except where a test exposes a real defect; such a defect is filed as an issue instead of widening this mission. | Technical | High | Open |
| C-002 | No heavy sweeps | Verification runs named test files and named architectural gate files only (`NO_FULL_HEAVY_SUITES_IN_MISSION`); no `make test-full`. | Technical | High | Open |
| C-003 | `p0_repro` out of scope | The nightly `p0_repro` marker work on branch `claude/festive-hopper-f5txxs` is not touched. | Business | High | Open |
| C-004 | Marker routing stays complete | The marker/collection completeness gates (`tests/architectural/test_marker_job_completeness.py` and the collection completeness gate) stay green. | Technical | High | Open |
| C-005 | Planted breaks are reverted | Planted breaks are never committed; the final tree has no product diff from them. | Technical | High | Open |

### Key Entities

- **Verdict ledger**: the per-file table in each issue body (file, test count, runtime, verdict, covering guard, evidence).
- **Planted-break record**: product edit, guard files run, red/green result, revert confirmation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The charter scope config reader goes from zero guarding tests to at least one that fails on the planted break. — [build] · no-op passable: no
- **SC-002**: The number of tests selected by `-m regression` across the ledger files drops by every MARKER-ONLY and SPLIT-BY-KIND test the ledgers name. — [build] · no-op passable: no
- **SC-003**: 100% of removed tests are matched by a planted-break record naming a covering guard that went red. — [build] · no-op passable: no
- **SC-004**: The two #5622 tests produce no failure when the suite runs as root. — [build] · no-op passable: no

## Assumptions

- The ledgers' planted-break evidence (B1–B9 in #5618, A–H in #5619) is re-run for every
  removal this mission makes rather than trusted from the issue text.
- Ledger rows marked KEEP need no change.
- `main` may have moved since the ledgers were written; verdicts are applied to the current
  shape of each file.

# Mission Specification: Nightly reds 2026-10-03

**Mission Branch**: `kitty/nightly-reds-2026-10-03`
**Created**: 2026-10-04
**Status**: Draft
**Input**: Operator session brief "nightly reds 2026-10-03" (4.0.0 release scope). Grounding evidence: [research/nightly-red-memo.md](research/nightly-red-memo.md).

## Intent Summary

The nightly workflow reports three suites red on current `main` (run 37177460494, head `b2c466d7d1`):
the Python 3.13 interpreter shard 3 (#5418), the `specify_cli` out-of-matrix trees (#5258) and the
performance suite (#5419). A maintainer preparing the 4.0.0 release cannot trust the nightly signal
until every one of those failures has a named cause and either a fix or an explicit ruling.

The grounding squad named 32 failing tests in seven groups. None is a product defect and none is an
intentional `regression`-marked red. Six groups are tests or test support that lag a merged, intended
product change; this mission repairs those. The seventh (three wall-clock budget tests) is not
repaired here: the only fixes are a product start-up cost reduction or a change to the budget, and
both need an operator ruling.

Rule that always holds: a test goes green in this mission only because its expectation or its
fixture now matches shipped, intended behaviour. No budget is raised, no retry is added, and no test
is skipped or deselected.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Registry-count tests follow the command registry (Priority: P1)

A maintainer removes or adds a shipped command. The tests that count commands, shims and installed
files report the new numbers without a hand edit, while the one deliberate frozen snapshot of the
`doctor` command surface still forces a conscious update.

**Why this priority**: three tests in two suites fail on this cause, and the same cause will recur
at the next command change because pull-request CI does not run these trees.

**Independent Test**: run the three named test files; all pass, and the frozen `doctor` snapshot
lists `run-index` with its option and help expectations.

**Acceptance Scenarios**:

1. **Given** the dashboard command was removed from the shim registry, **When** the hybrid-install
   shape tests run, **Then** they expect exactly as many shim files and total command files as the
   registry declares.
2. **Given** the `doctor skills` JSON envelope test, **When** it runs, **Then** every key of the
   frozen envelope is still compared exactly and the command count equals the canonical command set.
3. **Given** `doctor run-index` is a registered subcommand, **When** the frozen-surface test runs,
   **Then** the frozen set, the option table and the help snapshot all include it.

---

### User Story 2 - Handle-equivalence matrix seeds a mission of the type it runs (Priority: P1)

A maintainer checks that a custom mission run resolves to the same run identity whichever handle
form selects the mission.

**Why this priority**: three parametrised cases fail in two suites.

**Independent Test**: run the handle-equivalence run-identity test; all three handle forms pass and
still compare run identity.

**Acceptance Scenarios**:

1. **Given** a mission seeded with the custom mission type, **When** the custom mission is run by
   slug, by mid8 and by numeric prefix, **Then** all three runs exit 0 and report one identity.
2. **Given** the other tests that share the seeding helper, **When** they run, **Then** they still
   seed a `software-dev` mission.

---

### User Story 3 - Migration sequencing test exercises only its own migrations (Priority: P1)

A maintainer adds a migration that writes to the project. The hosted-endpoint sequencing tests keep
passing because they apply only the two migrations whose order they assert.

**Why this priority**: two tests fail in two suites, and every future migration that touches the
file system would red them again.

**Independent Test**: run the `TestMigrationSequencing` class; both tests pass and neither touches a
path outside its temporary directory.

**Acceptance Scenarios**:

1. **Given** the applicable migration list for the 3.2.6 to 4.0.0rc5 upgrade, **When** the test
   reads it, **Then** it asserts both migrations under test are present and in the required order.
2. **Given** only those two migrations are applied, **When** they run, **Then** the end state is the
   one each test already asserts.

---

### User Story 4 - Source snapshot is complete when the checkout is shallow (Priority: P1)

The nightly performance job checks out one commit. The shared source snapshot built from that
checkout is a usable repository, so the installed-CLI owned-worktree test can run.

**Why this priority**: twenty parametrised cases fail in the performance suite.

**Independent Test**: build a snapshot from a depth-1 clone; history commands succeed in the
snapshot and in a clone of it.

**Acceptance Scenarios**:

1. **Given** a shallow source repository, **When** the snapshot builder runs, **Then** the snapshot
   records the shallow boundary and `git log` on its head succeeds.
2. **Given** a full-history source repository, **When** the snapshot builder runs, **Then** the
   result is unchanged from today.

### Edge Cases

- A new migration is retired or renamed: the sequencing test must fail loudly on the missing id, not
  pass by asserting nothing.
- The command registry gains a command: the derived counts follow; the frozen `doctor` snapshot and
  the single literal census in the command-installer tests still require a conscious edit.
- The snapshot source is already a full clone: `--update-shallow` is a no-op there.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Frozen doctor surface includes run-index | As a maintainer, I want the frozen `doctor` subcommand set, option table and help snapshot to include `run-index` so that the golden test matches the shipped surface. | High | Open | [ratchet] | no — the test is red on the base commit |
| FR-002 | Doctor skills count follows the canonical set | As a maintainer, I want the frozen `doctor skills` envelope to take its command count from the canonical command set, with every other key still compared exactly, so that a command change cannot stale it. | High | Open | [ratchet] | no — red on the base commit |
| FR-003 | Hybrid install shape follows the registry | As a maintainer, I want the hybrid-install shape tests to expect the shim and total file counts the registry declares so that they match the shipped install. | High | Open | [ratchet] | no — red on the base commit |
| FR-004 | Handle matrix seeds the run's mission type | As a maintainer, I want the run-identity test to seed a mission whose type equals the custom key it runs, leaving the shared default untouched, so that it tests handle equivalence and not a type conflict. | High | Open | [ratchet] | no — red on the base commit |
| FR-005 | Sequencing test applies only its two migrations | As a maintainer, I want the sequencing tests to assert presence and order from the applicable list and apply only the two migrations under test in a temporary project so that unrelated migrations cannot break them. | High | Open | [ratchet] | no — red on the base commit |
| FR-006 | Snapshot builder handles a shallow source | As a maintainer, I want the shared source snapshot builder to produce a readable repository from a shallow checkout so that tests cloning it see consistent history. | High | Open | [build] | no — a new test builds a snapshot from a depth-1 clone and fails on the base commit |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No green-washing | 0 budgets or timeouts raised except the one budget alignment ruled by the operator under C-002, 0 retries added, 0 tests skipped, deselected or deleted in the diff. | Reliability | High | Open |
| NFR-002 | Assertion strength kept | Each repaired test keeps every assertion it had other than the stale literal; 0 assertions removed without an equal or stronger replacement. | Reliability | High | Open |
| NFR-003 | Red-first evidence | Each of the 29 repaired test cases is recorded failing on base `b2c466d7d1` and passing on the branch, with command and counts. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Test-side only | Changes are limited to `tests/` and the changelog; no file under `src/` changes. | Technical | High | Open |
| C-002 | Budget tests changed only by ruling | `tests/performance/test_owned_checkout_perf.py` is not modified by any work package. Operator ruling 2026-10-04: align its budget to the 2.5 s the CLI start-up test already allows, as a closeout fold. The tests stay runner-dependent; follow-up: #5614. | Business | High | Open |
| C-003 | No heavy suites locally | Only named tests, their files and `make test-fast` run locally; the nightly suites are not run as a whole. | Technical | High | Open |
| C-004 | Out of scope | Suite-wide harness rework (see #5353), the stress and integration nightly trackers (see #5610, see #5611, see #5612), and the already closed shard-4 tracker (see #5562) are not addressed. | Business | Medium | Open |

## Assumptions

- The product changes that staled these tests are intended: mission-type conflict refusal (see #4965),
  `doctor run-index` (see #5390), dashboard removal (see #5530) and the coordination seed probe.
- The nightly performance job keeps its shallow checkout; the snapshot builder must cope with it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The 9 test cases shared by the shard-3 and out-of-matrix suites pass on the branch — [ratchet] · no-op passable: no
- **SC-002**: The 20 installed-CLI owned-worktree cases pass when the source checkout is shallow — [build] · no-op passable: no
- **SC-003**: The 3 budget cases are reported to the operator with measurements and options and changed only as the operator rules — [folded] · no-op passable: yes — reporting only; paired with C-002
- **SC-004**: The pull request names, per tracker issue, which failures it fixes and which it leaves — [build] · no-op passable: no

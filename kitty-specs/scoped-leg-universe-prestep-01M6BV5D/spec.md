# Mission Specification: Scoped heavy legs intersect the universe pre-step

**Mission Branch**: `scoped-leg-universe-prestep-01M6BV5D`
**Created**: 2026-11-01
**Status**: Draft
**Input**: GitHub issue #7001, "Scoped heavy legs: intersect the universe pre-step with the selected gates file" (follow-up from #6994 / PR #6996), plus operator guidance: run the governed mission from the issue to a green draft PR; never merge.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A scope-only leg stops paying for a universe it will not read (Priority: P1)

A contributor opens a pull request that touches only a path a few architectural
gates declare as their scan scope (a docs page, a kitty-specs file, a data file).
Since #6994 each heavy battery leg runs only those gates, but the shared
test-universe pre-step still asks its question of the leg's *whole* partition. The
partition holds the two universe-consuming gates in every leg, so both legs answer
"yes, collect" and each pays a full `pytest --collect-only` of the test tree (a cold
collection, because the store's cache key includes the commit and a new commit is
always a cache miss) even though not one selected gate reads the universe.

**Why this priority**: This is the whole issue. The saving is the largest single
cost a scope-only PR pays on the heavy legs after `uv sync`; a cold collection
measured 396.7 s on the development host (0.55 s when reused), against four selected
gates that never touch the universe.

**Independent Test**: On a clean checkout, write a selected-gates file naming one
non-consumer gate, run the leg's decision with that file, and see the pre-step
decline. With no gates file the same leg still answers "yes", so the probe is
non-vacuous on the same fixture.

**Acceptance Scenarios**:

1. **Given** a leg whose selected gates file names only gates that never call `collect_universe()`, **When** the leg decides whether to run the test-universe pre-step, **Then** it answers `false` and every universe step (key, restore, collect, save, check) is skipped for that leg.
2. **Given** a leg whose selected gates file names a gate that calls `collect_universe()`, **When** the leg decides, **Then** it answers `true` and the pre-step runs unchanged.
3. **Given** a leg with no gates file (whole-leg run, full mode, or any doubt from the scope selection), **When** the leg decides, **Then** it keeps today's answer for its whole partition.
4. **Given** a leg that names a gates file that is missing or unreadable, **When** the leg decides, **Then** the command fails with no answer, so the job goes red rather than silently skipping a pre-step a selected gate may need.

### User Story 2 - The pre-step and the leg agree on which files run (Priority: P1)

The plug-in that restricts a leg to its selected gates reads the gates file itself.
The decision must read the *same* file through the *same* parser, so the pre-step can
never believe a gate is selected that the leg then refuses to run, or vice versa.

**Why this priority**: Two readers of one file with two parsers is the classic second
source of truth; a drift here either loses a needed collection (a test collecting for
itself, which `check` reports as a failure) or pays for a collection nobody reads.

**Independent Test**: A round-trip test writes a selected-gates file through the
writer the CI scope step uses and asserts both readers (the plug-in's scope and the
pre-step's decision) resolve the identical set, including blank lines and duplicate
entries.

**Acceptance Scenarios**:

1. **Given** a gates file written by `battery_scope select`, **When** the plug-in decides its scope and the pre-step decides its consumers, **Then** both see the same gate set.
2. **Given** a gates file with blank lines and a duplicated gate, **When** either reader parses it, **Then** both produce the same de-duplicated set.

### User Story 3 - The operator can see the saving (Priority: P2)

A maintainer asks whether the change is worth landing. The reference page states
what a scoped leg now skips, on which kind of pull request, and with what measured
cost, and the changelog states the change with its impact first.

**Why this priority**: The issue's "Done when" asks for a measurable drop and for
further cheap wins to be noted; without the numbers the change is unfalsifiable.

**Independent Test**: The reference page's stored-universe section names the
decision's new input, and the changelog carries an `[Unreleased]` entry citing
(#7001) with a measurement.

**Acceptance Scenarios**:

1. **Given** the reference page for CI gate mechanics, **When** a reader looks up the `consumers` command, **Then** it documents the gates-file input and the fail-closed behaviour for a missing file.
2. **Given** the changelog, **When** a reader looks under `[Unreleased]`, **Then** an entry leads with the impact and cites (#7001).

### Edge Cases

- The scope step answered `run=false` (the leg holds none of the selected gates): the
  universe decision stays off before any file is read, as it is today.
- The gates file is empty but present (scoped leg, zero selected gates for this leg is
  already `run=false`; an empty file with `run=true` must not be read as "whole part",
  because that would re-widen the leg and pay for a collection it does not need). An
  empty file means "no selected gate consumes the universe", so the answer is `false` -
  the same answer the plug-in gives (it fails closed on a scoped leg with nothing of
  the part).
- The gates file names gates of the other leg only: the intersection with this leg's
  partition is empty, so the answer is `false`.
- A gate file that lists a path outside `tests/architectural/`: it is not a consumer
  candidate and cannot be part of the partition, so it changes nothing.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | The decision is intersected with the selected gates | As a CI operator, I want a scoped leg's universe decision to consider only the gates the diff selected, so that a scope-only leg does not collect a universe none of its gates reads. | High | Open | [build] | no |
| FR-002 | A consumer among the selected gates still collects | As a CI operator, I want the pre-step to run when a selected gate consumes the universe, so that no gate silently collects for itself. | High | Open | [ratchet] | no — paired with FR-001 on the same fixture (same file, consumer gate added) |
| FR-003 | No gates file keeps today's whole-part answer | As a CI operator, I want a whole-leg run, full mode, or any doubt to behave exactly as today, so that the change can never narrow a leg that was not scoped. | High | Open | [ratchet] | no — paired with FR-001 on the same fixture (file argument removed) |
| FR-004 | A missing or unreadable gates file fails closed | As a CI operator, I want the decision to fail with no answer when the named file cannot be read, so that a broken scope selection never silently skips a needed collection. | High | Open | [build] | no |
| FR-005 | One parser owns the gates file format | As a maintainer, I want the plug-in's scope and the pre-step's decision to read the selected-gates file through one parser, so that the two can never disagree about which files a leg runs. | High | Open | [build] | no — guarded by a writer/readers round-trip on one fixture |
| FR-006 | The workflow passes the leg's gates file to the decision | As a CI operator, I want `ci-router.yml` to hand the decision the file the scope step wrote, so that the intersection actually reaches CI. | High | Open | [build] | no — a workflow-shape test pins the wiring and rejects a decision that ignores the file |
| FR-007 | The saving is measured and documented | As a maintainer, I want the measured cost and the remaining cheap wins written down, so that a reader can judge the change and pick up the follow-ups. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | The decision stays cheap | The decision costs less than 5 s on a scoped leg, so skipping the pre-step is never paid back by the decision itself. Measured locally: 1.5 s for the partition plus AST scan. | Performance | High | Open |
| NFR-002 | No behaviour change for unscoped legs | For a leg with no gates file, the decision's answer and exit status equal today's for every battery partition. | Reliability | High | Open |
| NFR-003 | Fail closed, never skip silently | A missing, unreadable or malformed gates file produces a non-zero exit and no `true`/`false` answer on stdout. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | The plug-in's contract is unchanged | `SK_BATTERY_GATES_FILE` semantics in `battery_partition_plugin` (unset runs the whole part, missing file fails closed) stay as #6994 shipped them. | Technical | High | Open |
| C-002 | The universe itself is never narrowed | Only the *decision* is intersected. A leg that does collect still collects the whole test tree, because the consuming gates compare across the whole suite. | Technical | High | Open |
| C-003 | The pytest command line and the step order are untouched | The battery step's command line, the `select -> key -> restore -> collect -> save -> pytest -> check` order and every guard keep their shape. | Technical | High | Open |

### Key Entities

- **Selected gates file**: the newline-separated list of gate file paths one scoped leg will run, written by `scripts.ci.battery_scope` and read by both the battery plug-in and the universe decision.
- **Universe consumer**: a test file under `tests/architectural/` whose source calls `collect_universe()` (an AST scan; `test_universe_store.py` excluded because it fakes the collector).
- **Leg**: one `--battery-part` of the heavy architectural battery (a pair of xdist shards).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A scope-only PR (docs-only: 3 selected gates in leg 1/2, 4 in leg 2/2, none a consumer) skips the whole universe chain on both legs, removing a cold collection measured at 396.7 s on the development host; the decision itself costs 1.5 s. — [build] · no-op passable: no
- **SC-002**: A tests-only PR, whose selected gates do include `test_fast_tier_marker_completeness.py` and `test_same_tier_uniqueness.py`, keeps collecting on both legs. — [ratchet] · no-op passable: no — paired with SC-001 on the same decision and file format
- **SC-003**: The battery partition proof, the shard-registry gates and the workflow-shape tests stay green. — [ratchet] · no-op passable: no

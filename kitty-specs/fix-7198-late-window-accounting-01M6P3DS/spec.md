# Mission Specification: Account for every late-window change before the coordination branch goes

**Mission Branch**: `fix-7198-late-window-accounting`
**Created**: 2026-11-05
**Status**: Draft
**Input**: Issue #7198 — `consolidate`: a late coordination commit touching only `status.events.jsonl`
or `meta.json` is approved at exit 0 without being landed.

## Problem

`spec-kitty consolidate` proves the late window landed before it deletes the coordination branch.
PR #7124 (#6871) extended the projection and its post-projection proof
(`assert_late_window_landed`, `src/specify_cli/consolidation/bookkeeping_projection.py`) to **both**
run kinds: a first run now anchors the window at the coordination tip it captured
(`coord_tip_after_projection`) and a `--resume` keeps anchoring it at the persisted pre-mutation
snapshot.

The proof itself, however, only covers **coordination-kind records**. It skips, by two exemptions:

1. the two status byte-sets (`status.events.jsonl`, `status.json`), because the union /
   rematerialize stage "owns" them — but that stage unions the **coordination worktree's working
   tree**, not the branch's commits, so an event appended and committed on the coordination branch
   from a checkout other than the coordination worktree is unioned from nothing and then destroyed
   with the branch;
2. every non-coordination path (`meta.json`, any other PRIMARY-partition artifact), because the
   target "owns" them — so a late `meta.json` change on the coordination branch is dropped with the
   branch without ever being compared.

In both shapes the window is non-empty, the projection carries nothing, the assertion proves nothing
about the path, the run advances the approved tip to the branch tip, the projection teardown gate and
the branch-delete compare-and-swap match, and the coordination branch is deleted at exit 0. Before
#7124 the first-run shape at least refused at the gate; the exemption is what turns that refusal into
silent loss. `--resume` has behaved this way since #6857.

## Goal

Teardown approves a coordination tip only when **every** Mission-directory change in the late window
is either landed on the target or excluded by a rule that states, and where possible proves, why the
excluded bytes carry nothing the target lacks. Anything else refuses, keeps the coordination branch,
worktree and marker, and names its repair — on both run kinds, through the same assertion #7124
already calls.

Four dispositions, one per changed path in the window, replacing "skip unless coordination record":

- **landed** — the coordination bytes equal the target's committed blob (today's proof, unchanged);
- **landed by the union** — `status.events.jsonl`: every event identity committed on the coordination
  branch in the window is present in the target branch's committed log (the union's output is a
  superset, so byte equality is the special case, not the rule);
- **excluded as derived** — `status.json`: a reduced snapshot of that event log, rematerialized from
  the union by the projection itself, so its own bytes are never an independent record;
- **carried by the target's own copy** — a non-coordination document (today: `meta.json`) whose
  coordination-branch document is contained in the target's committed copy (the target re-authors it
  after the checkpoint: the mission-number bake, the baseline stamp, the marker flatten). Containment
  is recursive JSON object containment, so an added field is carried, a changed or removed field is
  not.

A window deletion keeps today's `DELETION_CANNOT_BE_EXPRESSED` refusal. A non-coordination path that
is neither landed nor carried refuses with its own kind and remedy: the projection cannot carry it and
the target has its own copy.

## Scope decisions

### Extend the #7124 assertion; do not build a second mechanism

`assert_late_window_landed` is already called on both run kinds, after the projection, before the
approved-tip advance and before the gate. Widening what it proves — rather than adding a parallel
"late window completeness" check somewhere else — keeps the ordering guarantee #7124 established:
nothing is approved that this assertion did not cover, and every refusal keeps the triple for the
same operator recovery.

### "Deliberately excluded" must be a rule with a reason, not a skip

The defect is exactly an exemption nobody checked. Each exclusion this Mission keeps is written down
with why the excluded bytes cannot carry a lost record (derived snapshot; target re-authors the
document and the coordination copy is contained in it), and each is exercised by a test that also
shows the *non*-excluded case refusing on the same fixture. No exclusion is silently widened: a new
status-like or primary-like file lands in the refusing bucket until a rule names it.

### No new CLI flag, exit code or error code

The refusals ride the existing `COORD_LATE_PROJECTION_REFUSED` envelope and the existing
`CoordinationTeardownError` exit-1 path. Two refusal kinds are added to
`LateProjectionRefusalKind` (one per remedy, as #6791 established: status events are not landed by
copying a file, and a non-coordination record is not repairable by the same command), so the
enum↔remedy bijection test still holds.

## User Scenarios & Testing

### User Story 1 - A status event committed on the coordination branch is never dropped (Priority: P1)

An operator (or a concurrent writer from another checkout) appends an event to
`status.events.jsonl` and commits it on the coordination branch. The coordination worktree's copy
does not have it, so the union stage cannot carry it. Teardown must not advance the approved tip and
must not delete the branch while that event is missing from the target's log.

**Why this priority**: this is the first shape the issue names and the one that destroys a status
transition at exit 0 with no signal at all.

**Independent Test**: build the first-run and resume fixtures, commit one event on the coordination
branch outside the coordination worktree, run teardown, and assert the refusal, the surviving branch,
the unadvanced approved tip, and the event present once the operator lands it.

**Acceptance Scenarios**:

1. **Given** a late window whose only change is an event appended to the coordination branch's
   `status.events.jsonl` outside the coordination worktree, **When** teardown runs, **Then** it
   refuses with the status-events kind, the coordination branch still exists and the mission's
   coordination marker is intact.
2. **Given** the same fixture with the event also present in the target branch's committed log,
   **When** teardown runs, **Then** the window is proven landed and teardown completes.
3. **Given** a first run and a `--resume` over the same fixture, **When** each runs, **Then** both
   reach the same verdict.

### User Story 2 - A late `meta.json` change is landed or refused, never dropped (Priority: P1)

A late change to `meta.json` (or another target-owned document) is committed on the coordination
branch. If the target's committed copy already carries the change, teardown proceeds. If it does not,
teardown refuses with a remedy that lands the change or reverts it, instead of deleting the branch.

**Why this priority**: the second shape the issue names; it is the shape a review squad used as an
"exempt" fixture, so the exemption is load-bearing in the tests as well as the product.

**Independent Test**: commit a new key into the coordination branch's `meta.json`; run teardown; then
commit the same document (or a superset) on the target and run again, and assert the two verdicts.

**Acceptance Scenarios**:

1. **Given** a coordination-branch `meta.json` whose document is not contained in the target's
   committed copy, **When** teardown runs, **Then** it refuses with the non-coordination kind and
   keeps the triple.
2. **Given** a coordination-branch `meta.json` whose document IS contained in the target's committed
   copy (the bake / stamp / flatten case), **When** teardown runs, **Then** the window is proven
   carried and teardown completes.

### User Story 3 - The established proofs are not weakened (Priority: P2)

Coordination-kind records keep `RECORD_NOT_LANDED`, deletions keep
`DELETION_CANNOT_BE_EXPRESSED`, the gate-matrix evidence guard keeps its kinds, and `status.json`
alone never turns a clean run into a refusal.

**Independent Test**: the existing late-teardown projection, projection-teardown, teardown-refusal and
CAS-branch-delete suites pass; the only edits are fixtures that used an exempt path to isolate a
different leg, and each is re-pinned to a path that is still exempt by an explicit rule.

**Acceptance Scenarios**:

1. **Given** the existing suites, **When** they run, **Then** every case passes with no assertion
   weakened and no case deleted.
2. **Given** a window whose only change is `status.json`, **When** teardown runs, **Then** it
   proceeds: the derived snapshot is excluded by rule, not by accident.

### Edge Cases

- A window that changes both a coordination record and `meta.json`: the record is projected and
  proven; the `meta.json` change is judged by containment. One refusal, naming the offending paths.
- A window that deletes `status.events.jsonl` entirely: the target still holds the log, so the
  existing deletion refusal fires (a projection cannot express a deletion).
- An unparseable `status.events.jsonl` on either side, or an unparseable `meta.json`: refuse
  fail-closed (an unreadable log cannot prove containment), never treat "cannot parse" as "landed".
- A path that appears in the window with no committed target copy at all: not landed, not carried,
  refuse.
- Both empty: nothing to prove, no refusal (a clean run stays a clean run).

## Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Prove every window path | As an operator, I want teardown to judge every path the late window changed so that no committed change is dropped with the coordination branch. | High | Open | [build] | no |
| FR-002 | Status events proved by containment | As an operator, I want a status event committed on the coordination branch proved present in the target's committed event log so that an event the union stage cannot see is never lost. | High | Open | [build] | no |
| FR-003 | Unlanded status event refuses | As an operator, I want that case to refuse with a remedy that lands the event so that the run cannot exit 0 while dropping it. | High | Open | [build] | no |
| FR-004 | Derived snapshot excluded by rule | As a maintainer, I want `status.json` excluded because it is a reduced snapshot of the proved event log so that the exclusion is a stated rule, not an unexamined skip. | Medium | Open | [build] | no |
| FR-005 | Primary document carried by the target | As an operator, I want a coordination-side `meta.json` change accepted when the target's committed copy already contains it so that the bake/stamp path does not manufacture refusals. | High | Open | [build] | no |
| FR-006 | Unlanded primary document refuses | As an operator, I want a coordination-side primary change the target does not carry to refuse so that a lost `meta.json` edit is visible and recoverable. | High | Open | [build] | no |
| FR-007 | One kind per remedy | As an operator, I want each new refusal to name the repair that actually clears it so that the remedy never repeats the refusal. | Medium | Open | [ratchet] | no |
| FR-008 | Both run kinds | As an operator, I want the same verdict on a first run and a `--resume` over the same window so that the guarantee does not depend on how the landing was reached. | High | Open | [build] | no |
| FR-009 | No new operator surface | As a maintainer, I want no new CLI flag, exit code or error code so that the refusal contract stays as #6791/#7124 fixed it. | Medium | Open | [ratchet] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded proof | The widened assertion adds at most O(paths in the window) git blob reads plus one parse per status log; no full-log walk beyond the two blobs it already reads. | Performance | Medium | Open |
| NFR-002 | Fail-closed on unreadable input | An unreadable or unparseable event log or metadata document refuses; no code path treats a read failure as "landed". | Reliability | High | Open |
| NFR-003 | Recovery is executable | Every new refusal names a command an operator can run in the checkout they are in, and keeps branch + worktree + marker. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Same assertion, same ordering | The widened proof stays inside `assert_late_window_landed`, called by `_land_late_coordination_commits` after the projection and before the approved-tip advance. | Technical | High | Open |
| C-002 | No second status authority | Status file classification stays with `_classify_status_bookkeeping_filename` / `MissionArtifactKind`; event identity stays with the canonical event-log reader. | Technical | High | Open |
| C-003 | No projection of primary artifacts | The mission does not start projecting `meta.json` or other primary artifacts; that exclusion is load-bearing (#5460, #2804) and out of scope. | Technical | High | Open |

### Key Entities

- **late window** — `base..coordination tip` over `kitty-specs/<slug>/`, where `base` is
  `coord_tip_after_projection` on a first run and `pre_mutation_coord_sha` on a `--resume` (#7124).
- **disposition** — the verdict the assertion reaches for one changed path: landed, landed-by-union,
  excluded-as-derived, carried-by-target-copy, or refused (with a kind).
- **approved tip** — `coord_tip_after_projection`, advanced only after the assertion proves the window
  it was advanced to.

## Success Criteria

- **SC-001**: A red test written first (an event committed on the coordination branch outside the
  coordination worktree, first run) fails on the unmodified tree and passes after the change — [build] · no-op passable: no
- **SC-002**: The same fixture under `--resume` reaches the same verdict, and a red test pins it — [build] · no-op passable: no
- **SC-003**: A late `meta.json` change refuses when the target does not carry it and passes when it
  does, both on the same fixture — [build] · no-op passable: no
- **SC-004**: The existing late-teardown, projection-teardown, teardown-refusal-resume and CAS
  branch-delete suites pass without weakening an assertion — [ratchet] · no-op passable: no
- **SC-005**: `uv run --frozen mypy` on the changed modules, `ruff`, the changelog-style and
  docs-freshness checks, and the architectural terminology test all pass — [ratchet] · no-op passable: no

## Non-Goals

- #7199 (`--resume` anchor advance after a proven window) and #7209 (`--skip-lanes` evidence window):
  different seams, owned by other agents in this batch. This Mission touches `phase_teardown.py`'s
  assertion call ordering but does not change the anchor-advance rule.
- #7121 (a first run with no recorded coordination anchor builds no window): unchanged, still
  documented as a residual.
- Projecting primary artifacts onto the target: excluded by design, not revisited here.
- Any change to `--abort`, rollback, retention, or the `--keep-branch` surface.

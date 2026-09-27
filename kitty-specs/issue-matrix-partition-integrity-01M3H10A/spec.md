# Mission Specification: Issue-Matrix Partition Read Integrity & Merge Verdict-Terminality

**Mission Branch**: `claude/spec-kitty-ci-failures-r0xui3`
**Created**: 2026-09-27
**Status**: Draft
**Input**: Closes #5171 (mission-review false hard FAIL) and #4943 (merge false PASS + verdict-terminality gap), parent epic #3044 (review-artifact & verdict integrity).

## Overview

The issue matrix records, per cited GitHub issue, whether a mission has discharged the
work that issue represents. On coordination-topology missions the **authored** verdicts
live on the coordination surface (written by `issue-verdict`); the copy in the primary
working tree is stale residue. Several gates that consume the matrix read the wrong
partition, and one finishing path skips the terminal-verdict rule entirely. The result
is a mission ledger a team cannot trust: reviews fail missions that are actually correct,
merges land missions that are actually incomplete, and an unresolved verdict can survive
onto the target branch with no work package left to discharge it.

This mission makes every issue-matrix consumer resolve the artifact's owning partition
before reading it — including reading the coordination **branch ref** when the
coordination worktree has been consolidated away — and makes merge enforce the same
terminal-verdict rule the interactive `done` transition already enforces.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reviewer reads the authored verdicts, not stale residue (Priority: P1)

A mission reviewer runs the post-merge mission review on a coordination-topology mission
whose issue verdicts were finalised (e.g. `#11 -> fixed`) on the coordination surface.

**Why this priority**: This is the reported P0 (#5171). Today the reviewer reads the
primary working-tree copy, sees the stale `in-mission` value, and reports a hard FAIL on
a mission whose record is terminal and correct — misattributing the failure to the
mission rather than the gate. It fires on *every* coord-topology mission whose verdicts
were finalised through `issue-verdict`.

**Independent Test**: Build a coord-topology mission with divergent matrices (`#11:
in-mission` in the primary checkout, `#11: fixed` on the coordination surface); run the
mission-review issue-matrix gate; assert it reports the terminal `fixed` and PASSes.
Same-fixture positive control: a genuinely unresolved `in-mission` row on the
coordination surface still FAILs.

**Acceptance Scenarios**:

1. **Given** a coord mission with `#11 -> fixed` on the coordination surface and stale
   `in-mission` residue in the primary checkout, **When** the mission-review issue-matrix
   gate runs, **Then** it reads `fixed` from the coordination partition and does not FAIL.
2. **Given** the same mission but with `#11` still `in-mission` on the coordination
   surface, **When** the gate runs, **Then** it FAILs and names `#11` (positive control —
   the gate can still see a real problem).
3. **Given** a flat (lanes / single_branch) mission with the matrix in the primary
   partition, **When** the gate runs, **Then** it reads the primary copy unchanged (no
   regression on branch-flat topologies).

---

### User Story 2 - Merge enforces the issue-matrix gate on coordination missions (Priority: P1)

The merge process evaluates the issue-matrix completeness gate before advancing the
target branch.

**Why this priority**: #4943's coordination leg. On coord topology the gate scans the
status-only coordination husk for gating references, finds no `spec`/`plan` there, and
reports "No gating issue references discovered — nothing to enforce" — a false PASS that
lets a mission with a missing row land even under `merge_gates.mode: block`. Reference
discovery must read the PRIMARY partition; verdicts must read the COORD partition.

**Independent Test**: Run the merge gate on a coord mission that cites `#1234` in its
spec but has no matrix row; assert it reports the missing row and fails under `block`,
identically to a lanes mission. Same-fixture positive control: the lanes arm of the same
fixture already fails today — both arms must fail after the fix.

**Acceptance Scenarios**:

1. **Given** a coord mission citing `#1234` with no matrix row and `mode: block`, **When**
   the merge gate runs, **Then** it discovers the reference from the primary spec
   directory and FAILs (not "nothing to enforce").
2. **Given** a coord mission whose gating rows are `in-mission`/absent in the primary
   residue but terminal (`fixed`) on the coordination surface, **When** the merge gate
   runs, **Then** it PASSes — proving it read the coordination verdicts, not the stale
   primary residue.
3. **Given** the same fixture inverted (primary `fixed`, coordination `in-mission`),
   **When** the merge gate runs, **Then** it FAILs and names the row — the same-fixture
   mirror proving FR-003 discovery and FR-004 verdict-read are each independently exercised
   (half-by-half).
4. **Given** a lanes mission with the same missing row, **When** the merge gate runs,
   **Then** it FAILs with the same diagnostic as the coord arm (parity control).

---

### User Story 3 - Merge refuses to land unresolved verdicts (Priority: P1)

The merge process records work packages `done` and advances the target branch.

**Why this priority**: #4943's second, orthogonal leg. The `in-mission` verdict is
documented as non-terminal — it must not survive to `done`/merge — but that rule is
enforced only by `move-task --to done`, which merge bypasses. So a mission whose matrix
still says `in-mission` merges with exit 0, every WP is recorded `done`, and the target
branch permanently carries a row claiming a fix no WP is left to deliver.

**Independent Test**: With a gating row at `in-mission`, run merge in `block` mode and
assert it refuses before the target advances and names the row; in `warn` mode assert it
prints the same list the `done` transition prints. Same-fixture positive control: the
identical mission with the row resolved to `fixed` merges cleanly.

**Acceptance Scenarios**:

1. **Given** a coord mission (post-consolidation: coordination worktree torn down, branch
   retained) with a gating row at `in-mission`/`unknown` on the coordination branch and
   `mode: block`, **When** merge runs, **Then** it resolves the verdict from the
   coordination branch ref and refuses before the target advances, naming the offending
   row(s).
2. **Given** the same state and `mode: warn`, **When** merge runs, **Then** it still
   advances and records the work packages `done` (warn does not block); the change from
   today is that it now prints the same unresolved-row list the `done` transition prints,
   not a changed landing outcome under `warn`.
3. **Given** the same mission with the row resolved to a terminal verdict on the
   coordination branch, **When** merge runs in either mode, **Then** it advances with no
   verdict-terminality complaint (positive control).

---

### User Story 4 - Verdicts stay readable after the coordination worktree is gone (Priority: P2)

Review and merge read the authored matrix after a mission has been consolidated and its
coordination worktree torn down, while the coordination branch is retained.

**Why this priority**: This is the depth decision (deep fix). The fail-soft resolution
falls back to the primary residue when the coordination *worktree* is unmaterialized —
which is the normal post-consolidation state (#5171's exact scenario: verdict authored
after merge, worktree gone, branch retained). Without reading the coordination **branch
ref**, both the reviewer and merge reproduce the stale-residue read even after the
partition wiring is "correct". This closes the class rather than the surface symptom.

**Independent Test**: Consolidate a coord mission so the coordination worktree is removed
but the branch is retained; author `#11 -> fixed` on the coordination branch; run
mission-review; assert it reads `fixed` from the branch ref, not the primary residue.

**Acceptance Scenarios**:

1. **Given** a consolidated coord mission (worktree removed, branch retained) with
   `#11 -> fixed` on the coordination branch, **When** the mission-review gate reads the
   matrix, **Then** it resolves the verdict from the branch ref and reports `fixed`.
2. **Given** the same consolidated mission, **When** the merge issue-matrix / terminal-verdict
   gate runs, **Then** it too resolves verdicts from the coordination branch ref: a coord
   `fixed` advances, and the same fixture with a coord `in-mission` refuses — proving the
   deep read threads the **merge** path, not only review.
3. **Given** the coordination branch has genuinely been deleted (its ref does not resolve
   via `git rev-parse --verify`), **When** the mission-review or merge gate attempts the
   read, **Then** resolution fails closed (refuse/raise) rather than silently reading the
   primary residue and passing vacuously.
4. **Given** the coordination ref resolves but the authored matrix is empty while gating
   references exist, **When** the gate reads it, **Then** it REFUSEs; **and** the same
   fixture with a non-empty authored matrix resolves the verdict (paired positive control).
5. **Given** the coordination ref resolves but the content probe raises (unreadable object /
   IO error), **When** the gate reads it, **Then** it REFUSEs; **and** the same fixture with
   a succeeding probe reads `fixed` (paired positive control).

### Edge Cases

- **Surface selection follows lifecycle phase, not worktree state.** The read resolves its surface via
  the same lifecycle-phase authority the write uses: PUBLISHED phase (Target Ref / `meta.target_branch`
  deleted + baseline + completion) ⇒ read the consolidated-primary ref; CONSOLIDATED / pre-consolidation
  on coord topology (the #5171 case) ⇒ read the coordination branch ref. A read that hardcodes either
  surface risks diverging from the write.
- **Resolved ref deleted vs present.** Existence via `git rev-parse --verify`: resolved ref present ⇒
  read content from it; ref absent ⇒ fail closed (FR-007 deleted leg); ref present but the content probe
  errors ⇒ fail closed (FR-007 probe leg) — a distinct path from ref-absent.
- **References on the husk.** If reference discovery ever reads the coordination husk, zero
  references are found and the gate passes vacuously — discovery must always anchor to the
  primary partition.
- **git-probe failure.** A failure probing the coordination ref (unreadable object, IO
  error) must REFUSE, never be absorbed into a vacuous PASS.
- **Empty authored set.** An empty matrix while gating references exist must not be read as
  "nothing to enforce".
- **Flat topologies unchanged.** single_branch / lanes route the matrix to the primary
  partition; their behavior must be byte-for-byte unchanged.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Mission-review resolves the issue-matrix partition before reading | As a reviewer, I want the issue-matrix gate to read authored verdicts from the coordination partition on coord topology so that a terminal, correct matrix is not reported as a hard FAIL. | High | Open | [build] | no — paired same-fixture control: a real `in-mission` on the coord surface still FAILs (Scenario 1.2) |
| FR-002 | Review Gate-4 doctrine reads verdicts from the correct partition | As a reviewer following the documented procedure, I want the documented Gate-4 steps to read authored verdicts from the correct (coordination) partition via a resolver-backed read so that following the procedure does not read primary residue. | High | Open | [build] | no — positive control: the rendered Gate-4 doctrine references the partition-aware read command/API (not merely the absence of a raw path, which FR-008 guards) |
| FR-003 | Merge gate discovers gating references from the primary partition on all topologies | As the merge process, I want gating issue references discovered from the primary spec directory so that a coord mission is not falsely reported as having "nothing to enforce". | High | Open | [build] | no — parity control: coord and lanes arms of one fixture must both FAIL on a missing row (Scenario 2.4) |
| FR-004 | Merge gate reads verdicts from the coordination partition | As the merge process, I want matrix verdicts read from the coordination partition so that authored verdicts, not primary residue, decide the gate. | High | Open | [build] | no — divergent fixture (primary vs coord) proves a terminal coord verdict PASSes and the inverted fixture FAILs (Scenarios 2.2/2.3) |
| FR-005 | Post-consolidation matrix read via the write's surface authority | As a consumer of coordination-partition artifacts, I want the authored matrix read from the same surface the write path used — resolved by the shared lifecycle-phase authority (coordination branch ref in the CONSOLIDATED/pre-consolidation case, consolidated-primary ref in the PUBLISHED case) — so verdicts stay readable after the worktree is gone and a read can never diverge from where the verdict was written. | High | Open | [build] | no — RED before the authority exists (post-consolidation read returns residue); positive control: verdict written then read back via the same authority resolves identically |
| FR-006 | Merge enforces the terminal-verdict rule | As the merge process, I want to apply the same `in-mission -> done` rejection `move-task` applies — refuse in block mode (naming rows), warn with the same list in warn mode — so that an unresolved verdict cannot land on the target. | High | Open | [build] | no — positive control: the same mission with a terminal verdict merges cleanly (Scenario 3.3) |
| FR-007 | Fail-closed resolution on ambiguity or probe failure | As a consumer, I want an unresolved/deleted coordination surface, an empty authored set with live references, or a git-probe error to REFUSE rather than fall back to primary residue or pass vacuously, so that a broken read is never a silent PASS. | High | Open | [build] | no — negative probe paired with the FR-005 positive read on one fixture |
| FR-008 | Regression guard against improvised issue-matrix path reads | As a maintainer, I want a non-vacuous gate asserting no mission-review doctrine step or gate consumer reconstructs a topology-dependent `issue-matrix` path by hand so that the partition-resolution regression cannot re-enter. | Medium | Open | [build] | no — self-mutation check: injecting a raw read must trip the gate |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Single read authority | All issue-matrix consumers route through the existing placement-seam read authority; a static audit finds zero direct working-tree `issue-matrix` reads in the review and merge gate consumers (count = 0). | Maintainability | High | Open |
| NFR-002 | Fail-closed integrity | 100% of ambiguity/probe-failure paths (deleted coord surface, empty authored set with live references, git-probe error) resolve to a refusal, never a vacuous PASS, proven by dedicated tests. | Reliability | High | Open |
| NFR-003 | Resolution latency | For a pinned fixture of 10 gating issues / 25 matrix rows on a retained coordination branch, mission-review and merge gate evaluation each complete in under 2s (charter CLI <2s bar), and the branch-ref read adds no measurable overhead versus the equivalent worktree read on the same fixture. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Reuse the canonical partition seam | Reuse the existing placement-seam resolution authority; do not introduce a second partition-resolution authority. Any shared helper is added to the runtime module that owns the seam, never to the CLI adapter layer. | Technical | High | Open |
| C-002 | Respect the enforced layer chain | Consumers in the CLI adapter layer resolve partitions by importing from the runtime seam module (a permitted edge); introduce no new outbound module edges. | Technical | High | Open |
| C-003 | ATDD red-first with same-fixture controls | Each fix ships a failing-first test through the real production entry point (the gate/CLI the runtime invokes), RED on the base and GREEN on the final commit; every refusal/absence assertion is paired with a same-fixture positive control, and each compound fix is proven half-by-half. | Process | High | Open |
| C-004 | Terminology canon | Use "Mission" (never "feature") and the canonical verdict vocabulary in all new prose, doctrine, and identifiers. | Business | Medium | Open |
| C-005 | No test suppression; re-judge buggy-behavior pins | No test is skipped, quarantined, or disabled to pass; any existing test that pins the wrong-partition (husk/residue) read is re-judged and corrected, not green-washed. | Process | High | Open |

### Key Entities

- **Issue matrix (coordination-partition artifact)**: per-issue rows keyed by `#NNNN`, each
  carrying a verdict from the canonical set (`unknown`, `in-mission`, `fixed`,
  `verified-already-fixed`, `deferred-with-followup`, `not-applicable`). Terminal verdicts
  are the resolved set; `in-mission` and `unknown` are non-terminal.
- **Coordination partition / coordination branch**: the surface where lifecycle artifacts
  (status, notes, trace, issue-matrix) and authored verdicts live on coord topology; may be
  materialized as a worktree (including a status-only "husk" carrying no spec/plan content),
  or exist only as a retained branch ref.
- **Primary partition**: the stable planning surface (spec, plan, tasks) and the source of
  gating issue-reference discovery, on every topology.
- **Gating issue reference**: a bare `#NNNN` citation in the spec that obliges a matrix row;
  context-only or PR/commit references are non-gating.
- **Consumers**: the mission-review issue-matrix gate (Gate 4), the merge issue-matrix
  completeness gate, and the merge done-bookkeeping path.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A coord-topology mission whose gating verdicts are terminal on the
  coordination surface passes mission review with zero false hard FAILs (down from 100% on
  affected missions today). — [build] · no-op passable: no
- **SC-002**: A coord-topology mission with a gating issue and no matrix row is reported
  identically to a lanes mission (no false "nothing to enforce" PASS) — parity across both
  topology arms of one fixture. — [build] · no-op passable: no
- **SC-003**: A mission with any gating row at `in-mission`/`unknown` cannot be landed by
  merge in `block` mode (refused, rows named) and prints the same list in `warn` mode; the
  same mission with terminal verdicts lands cleanly. — [build] · no-op passable: no
- **SC-004**: Authored verdicts remain readable by review and merge after the coordination
  worktree is torn down (branch retained); a deleted branch fails closed rather than reading
  residue. — [build] · no-op passable: no
- **SC-005**: Zero direct working-tree `issue-matrix` reads remain in the review and merge
  gate consumers, enforced by a non-vacuous regression guard that trips when a raw read is
  reintroduced. — [build] · no-op passable: no

## Assumptions

- The placement-seam partition-resolution authority already exists and is the canonical
  surface to adopt for FR-001–FR-004 (mirroring the existing healthy two-partition consumer).
  FR-005/FR-007's coordination-branch-ref content read is a NEW primitive layered on that
  seam — in scope per the operator's deep-fix decision, delivery-labelled `[build]`
  accordingly — and is not characterized as pure adoption.
- The canonical two-partition split pattern (discovery from primary, verdicts from
  coordination) is already demonstrated by an existing healthy consumer and is the reference
  shape to mirror for FR-001–FR-004.
- `#5171` and `#4943` are the same defect class (partition resolution for the issue-matrix
  kind) plus one orthogonal merge verdict-terminality gap; both are in scope by operator
  decision. The nightly P0s (#5169, #5172) are unrelated and out of scope.

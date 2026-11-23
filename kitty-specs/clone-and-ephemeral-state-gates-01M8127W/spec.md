# Mission Specification: Gates that work in teammate clones and ephemeral reviewers

**Mission Branch**: `kitty/mission-clone-and-ephemeral-state-gates-01M8127W`
**Created**: 2026-11-22
**Status**: Draft
**Input**: Operator request (2026-11-22): research and remediate #7809, #7806, #7802 and #7808, plus #7759 (folded in by operator ruling).

**Baseline**: the coordination-branch sibling (see #5936) is fixed by PR #7804, which this Mission builds on and does not redo.

## Context

Real Missions run in cloud sessions and teammate clones on 4.0.0rc9 broke at five gates. Four of them share one assumption: the state a gate needs is a local ref, already pushed where needed, and anchored on the target branch. A teammate's clone has branches only as remote-tracking refs, an ephemeral reviewer never pushes, and a docs work package is evidenced where nobody committed it. The fifth gate reads a CSS hex colour as an issue number.

Research, code grounding and an architect + researcher squad pass are recorded in `research.md`. Operator rulings are recorded as Decision Moments (`spec-kitty agent decision`), slots `specify.*`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A docs work package in a lane Mission gets a real lane (Priority: P1)

A Mission author writes a work package whose deliverable is a docs page and a changelog fragment (no source code). The Mission settles to a lane topology. Today that work package goes to the planning lane, whose branch is the target branch, so `move-task` refuses `IMPLEMENTATION_MISSING`, the review range holds only status commits, and `consolidate` refuses `UNATTRIBUTABLE_CONTENT_FORECAST` unless the author commits the docs on the target branch (often `main`, which teams never commit on). After this Mission, such a work package is an ordinary code work package with its own lane: it is implemented in a lane worktree, reviewed on its lane's range, approval-stamped, and consolidated like any other.

**Why this priority**: It blocks a Mission from reaching consolidation without committing on the target branch or forcing gates; it hits every lane Mission with a docs work package.

**Independent Test**: Finalize a lane Mission with one code work package and one docs-only work package; the docs work package lands on its own lane, and implement → for_review → review → approve → consolidate succeeds with its commits on the lane branch only.

**Acceptance Scenarios**:

1. **Given** a Mission that settles to a lane topology and a `planning_artifact` work package whose owned files are all under `docs/`, **When** `finalize-tasks` runs, **Then** that work package is recorded as `code_change`, gets its own lane in `lanes.json`, and the command prints a notice naming the work package and why.
2. **Given** that work package committed on its lane branch, **When** it is moved to `for_review`, reviewed and approved, **Then** no `IMPLEMENTATION_MISSING` refusal occurs and the review range contains the work package's own commits.
3. **Given** that work package approved, **When** `consolidate` runs, **Then** its content is attributed to the approved work package (no `UNATTRIBUTABLE_CONTENT_FORECAST`).
4. **Given** a `planning_artifact` work package that owns both a `kitty-specs/` path and a `docs/` path in a lane topology, **When** `finalize-tasks` runs, **Then** it refuses with the kitty-specs ownership refusal and a remedy telling the author to split the work package.
5. **Given** a `planning_artifact` work package whose owned files are all under `kitty-specs/`, **When** `finalize-tasks` runs, **Then** it stays on the planning lane, unchanged.
6. **Given** a Mission that settles to `single_branch`, **When** `finalize-tasks` runs, **Then** no work package kind is rewritten.

---

### User Story 2 - A teammate reviews a lane that exists only on origin (Priority: P1)

A reviewer clones the repository (or pulls) and runs `agent action review` for a work package whose lane branch exists only as a remote-tracking ref. Today the review's lane sync fails `LANE_AUTO_REBASE_FAILED` ("is not a local branch") and the reviewer must create the branch by hand. After this Mission, review creates the local lane branch from the owning remote's tracking ref, tracking it, and proceeds.

**Why this priority**: Every second-clone reviewer of a lane Mission hits it on the first review.

**Independent Test**: In a teammate's clone with the lane only on origin, `agent action review WP01` succeeds and the local lane branch exists, tracking the owning remote.

**Acceptance Scenarios**:

1. **Given** a teammate's clone where the lane branch is only `refs/remotes/<remote>/<lane>`, **When** the reviewer runs `agent action review`, **Then** a local lane branch is created from that ref with its upstream set, and the review claim succeeds.
2. **Given** a clone that holds no ref at all for the lane branch, **When** review runs, **Then** it still refuses, naming the missing branch.
3. **Given** a clone whose local lane-tip record for that lane names a commit that the remote-tracking ref does not contain, **When** review runs, **Then** it refuses with the destroyed-lane refusal instead of creating the branch at the older remote tip.

---

### User Story 3 - An ephemeral reviewer's approval survives without a push (Priority: P1)

A reviewer in a throwaway container claims a work package for review; the review claim merges the coordination branch into the lane, creating a local merge commit. The reviewer approves and pushes the status change but not the lane, then the container is reclaimed. Today the approval's stamp names that unpushed merge, and `consolidate` in another clone refuses `APPROVAL_STAMP_NOT_ON_LANE`. After this Mission, the approval also records the lane tip as it was before the review's own sync merge, and consolidation accepts whichever recorded stamp the lane contains.

**Why this priority**: It forces a full re-review of an already-reviewed work package and is easy to trigger by any agent reviewer.

**Independent Test**: Approve a work package in clone B without pushing the lane; consolidate in clone A succeeds when the implementer's pushed lane tip is the pre-sync tip.

**Acceptance Scenarios**:

1. **Given** a review claim that created a sync merge on the lane, **When** the work package is approved, **Then** the approval records both the lane head and the pre-sync lane tip.
2. **Given** that approval and a consolidating clone that never received the sync merge, **When** `consolidate` runs, **Then** the approval-stamp check passes on the pre-sync stamp and no `APPROVAL_STAMP_NOT_ON_LANE` refusal occurs.
3. **Given** a commit added to the lane after the approval (not the review's own sync merge), **When** `consolidate` runs, **Then** it is still refused `LANE_MOVED_AFTER_APPROVAL` (the bound is not weakened).
4. **Given** an approval whose stamps are both absent from the consolidating clone, **When** `consolidate` refuses, **Then** the refusal says the stamp object is absent from this clone and how to recover (push the lane from the reviewer's clone, or re-review), instead of saying the lane was rewritten.

---

### User Story 4 - A hex colour is never an issue (Priority: P2) — moved out of this Mission

> **Moved (2026-11-22):** operator ruling R68 moves #7808 into the Slice 5 Mission, together with #5297 and #5516. WP01 is canceled, the #7808 matrix row is deferred-with-followup, and FR-012 / SC-004 are owned by that Mission. The story is kept below for traceability.

A Mission's research quotes colours such as a hash followed by `000000`. Today issue-matrix discovery reads that as issue number 0 and blocks approval until someone records a verdict for an issue that does not exist. After this Mission, hex colour literals in CSS declaration form and any hash-number with a leading zero are never issue references.

**Why this priority**: A false gate with an easy workaround; small and independent.

**Independent Test**: A Mission artifact containing colour declarations produces no issue-matrix row for them, while real references on the same lines still do.

**Acceptance Scenarios**:

1. **Given** an artifact line with a colour declaration whose value is all digits (six or three digits), **When** discovery runs, **Then** no issue reference is produced for it.
2. **Given** a hash followed by a digit run starting with zero, **When** discovery runs, **Then** no issue reference is produced, in every issue-number pattern (artifact discovery, the Mission's source-issue detection and closing keywords).
3. **Given** a line that mentions a CSS word and also a real issue reference (for example "fix border regression" followed by a real issue number), **When** discovery runs, **Then** the real reference is still found.

---

### User Story 5 - A planning-lane work package's review range is honest (Priority: P2)

Folded from #7759. A planning-lane work package in a lane Mission gets a review range of coordination status commits that omits its real work. After this Mission, a docs work package has its own lane (User Story 1), so its range is its lane's commits; a planning-lane work package whose work is only under `kitty-specs/` gets a range on the branch where those artifacts are written, or the review context says the range is unavailable and why, never a bookkeeping-only range presented as valid.

**Why this priority**: Misleads a reviewer into thinking a range covers the work; mostly resolved by User Story 1.

**Independent Test**: The review context of a kitty-specs-only planning work package never prints a range made only of status commits as if it held the work.

**Acceptance Scenarios**:

1. **Given** a docs work package normalised to a code lane, **When** review runs, **Then** the review range is the lane range with the work package's commits.
2. **Given** a planning-lane work package whose derived range contains only status-bookkeeping commits, **When** review runs, **Then** the review context reports the range as unavailable with the reason, instead of printing it.

### Edge Cases

- A work package already started (claimed or later) on the planning lane when a re-finalize runs keeps its frozen lane membership; it is not moved.
- A docs work package depends on a code work package (or the reverse): the dependency still orders the lanes.
- The lane's owning remote is ambiguous (several remotes, none owns the branch): review does not pick one silently; it keeps today's refusal path.
- The origin check is off (`SPEC_KITTY_ORIGIN_CHECK=off`): review may create the lane branch from the tracking ref as last fetched, and says it was not refreshed.
- An approval recorded with no review sync merge (the lane head is the implementer's tip): the pre-sync stamp equals the lane head or is omitted; behaviour is unchanged.
- A hash-number in a code span that is a real issue (for example a backticked issue number) is still a reference.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Normalise docs work package kind in lane topologies | As a Mission author, I want a `planning_artifact` work package that owns any path outside `kitty-specs/` recorded as `code_change` when the Mission is in a lane topology, so that it gets its own lane, worktree, stamps and evidence. | High | Open | [build] | no — a kitty-specs-only planning work package on the same fixture must stay `planning_artifact` |
| FR-002 | Notice for a normalised work package | As a Mission author, I want `finalize-tasks` to name every work package whose kind it rewrote and why, so that the rewrite is never silent. | Medium | Open | [build] | no |
| FR-003 | Refuse mixed planning work packages in lane topologies | As a Mission author, I want `finalize-tasks` to refuse a `planning_artifact` work package that owns both `kitty-specs/` and other paths in a lane topology, with a split remedy, so that kitty-specs files never travel on a lane branch. | High | Open | [build] | no — a pure docs work package on the same fixture must pass |
| FR-004 | Docs work packages count toward topology settlement | As a Mission author, I want a docs work package that would get a lane counted as a code lane when the topology is settled by size, so that settlement and lane computation agree. | Medium | Open | [build] | no — the same Mission without the docs work package must settle as before |
| FR-005 | single_branch and started work packages unchanged | As a Mission author, I want no kind rewrite in `single_branch` Missions and no lane move for a started work package, so that existing Missions keep working. | High | Open | [ratchet] | yes — paired with FR-001's positive case on the same fixture |
| FR-006 | Review creates a remote-only lane branch | As a reviewer in a teammate's clone, I want `agent action review` to create the local lane branch from the owning remote's tracking ref with its upstream set, so that the review proceeds without manual git. | High | Open | [build] | no |
| FR-007 | Fail closed without a ref or with newer local lane work | As a reviewer, I want review to refuse when no ref exists for the lane branch, and to refuse with the destroyed-lane refusal when the local lane-tip record holds work the tracking ref lacks, so that a lane is never resurrected at an older tip. | High | Open | [build] | no — the remote-only case on the same fixture must succeed |
| FR-008 | One branch-materialisation rule | As a maintainer, I want the coordination branch (PR #7804), the lane branch and the lane base lookup to use one rule for "the owning remote's tracking ref of a branch" and one way to create a tracking local branch from it, so that the rules cannot drift. | Medium | Open | [build] | no |
| FR-009 | Record the pre-sync lane tip on approval | As a reviewer, I want an approval to record the lane tip from before the review's own sync merge alongside the lane head, so that the approval does not depend on a commit only my clone has. | High | Open | [build] | no |
| FR-010 | Bound accepts either recorded stamp | As an integrator, I want consolidation's approval-stamp check to accept the approval when the lane contains either recorded stamp and bound the approved claim on that stamp, so that an unpushed review merge does not block consolidation. | High | Open | [build] | no — a post-approval commit on the same fixture must still be refused |
| FR-011 | Precise remedy for an absent stamp | As an integrator, I want an approval-stamp refusal to say when the stamp commit does not exist in this clone and what to do, so that I do not mistake it for a rewritten lane. | Medium | Open | [build] | no |
| FR-012 | Hex colours are not issue references | As a reviewer, I want hash-number literals with a leading zero, and all-digit hex colour values in CSS declaration form, never discovered as issue references in any issue-number pattern, so that approval is not blocked by a non-existent issue. | Medium | Moved (Slice 5 Mission, ruling R68) | [build] | no — a real reference on the same line must still be found |
| FR-013 | Honest planning-lane review range | As a reviewer, I want the review context of a planning-lane work package to report the range as unavailable, with the reason, when the derived range holds only status-bookkeeping commits, so that I never review a range that omits the work. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No new remote contact | The lane-branch creation, stamping and attribution changes contact no remote (zero new remote-contacting git argv outside `kernel.git.remote`, as enforced by the remote-contact owner gate). | Reliability | High | Open |
| NFR-002 | No added latency on the common path | Review, approval and finalize run at most one extra local git invocation per lane or work package on the common path. | Performance | Medium | Open |
| NFR-003 | Coverage | New and changed lines reach at least 90% diff coverage (the CI diff-cover gate). | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Build on PR #7804 | The lane-branch creation reuses and generalises PR #7804's owning-remote resolver; no second resolver. This Mission's branch is stacked on PR #7804 and rebased onto `main` once it lands. | Technical | High | Open |
| C-002 | No push | No CLI path added by this Mission pushes a branch (the push boundary is unchanged; follow-up: #5858). | Technical | High | Open |
| C-003 | ADRs | The approval-stamp change amends ADR `2026-10-04-5`; the docs-lane rule and settlement count amend ADR `2026-11-06-3`; ADR `2026-11-08-2` gets a cross-reference for the review range. | Governance | High | Open |
| C-004 | Pack templates stay upstream | Template guidance for `execution_mode` lives in `spec-kitty-open-packs`; this Mission does not edit `packs/built-in/` and records the template change as a follow-up. | Governance | Medium | Open |
| C-005 | Out-of-matrix disclosure | Tests changed under out-of-matrix directories (`tests/specify_cli/cli/commands`, `tests/specify_cli/upgrade`, `tests/contract`) are named in the PR as running nightly only, and are run locally. | Process | Medium | Open |

### Key Entities

- **Work package kind** (`execution_mode`): `code_change` or `planning_artifact`; decides lane placement and workspace.
- **Planning lane** (`lane-planning`): the one lane for planning-artifact work packages; its branch alias is the target branch.
- **Approval stamp**: `policy_metadata.lane_head` on an approval; with this Mission, also the pre-sync lane tip.
- **Owning remote**: the remote that owns a branch (`branch.<b>.remote`, else the only remote, else `origin`).
- **Issue reference**: a hash-number or same-repo issue URL in a Mission artifact that may require an issue-matrix row.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A lane Mission with a docs-only work package reaches a successful consolidation with zero commits on the target branch outside consolidation itself and zero forced transitions. — [build] · no-op passable: no
- **SC-002**: A reviewer in a fresh teammate clone completes `agent action review` on a remote-only lane with zero manual git commands. — [build] · no-op passable: no
- **SC-003**: Consolidation succeeds in a clone that never received the reviewer's sync merge, with zero re-reviews and zero attestations. — [build] · no-op passable: no
- **SC-004** (moved to the Slice 5 Mission, ruling R68): An artifact containing colour declarations yields zero issue-matrix rows for them. — [build] · no-op passable: no

## Assumptions

- A docs-only work package in a lane topology is product work like code: it is fine for it to have a lane worktree.
- Existing Missions that already finalized keep their recorded kinds until a re-finalize; started work packages never move.
- The review sync merge only brings coordination-branch content (bookkeeping and planning artifacts) into the lane.

## Out of Scope

- The coordination-branch materialisation itself (PR #7804) and the remote-only recovery text work (PR #7796).
- Pushing lanes or status from any CLI path.
- Editing pack templates in this repository.

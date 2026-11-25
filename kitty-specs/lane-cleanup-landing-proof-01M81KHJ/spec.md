# Mission Specification: One landing proof for lane cleanup

**Mission Branch**: `kitty/mission-lane-cleanup-landing-proof-01M81KHJ`
**Created**: 2026-11-22
**Status**: Draft
**Input**: Issues #7747 (P1) and #7325; operator rulings "Ancestor blob + keep-code" (2026-11-22, Decision Moments 01M81KHZ, 01M81KJ2, 01M81KJ5, 01M81KJ7).

## Intent Summary

- **Primary actor**: an operator who runs `spec-kitty consolidate` on a `lanes_with_coord` Mission, and later `spec-kitty doctor workspaces --prune` on the same repository.
- **Trigger**: a clean, verified squash landing. The lanes synced with the coordination branch while they were implemented, so each lane carries older copies of Mission files the tool rewrote later: the status log and snapshot, `meta.json`, and each work package prompt's claim frontmatter.
- **Desired outcome**: every lane whose work is on the target is removed by consolidate, and doctor rates such lanes landed once the target is on the remote primary branch. A lane that holds anything the target lacks is kept, with its branch.
- **Rule** (operator rulings 2026-11-22 and 2026-11-23, Option A): a Mission file is set aside only when the lane never authored it. That is read from the lane's own commit graph: no commit the lane made itself changed the file, except a merge that took the file whole from the branch it merged in. A version the target's own history already holds also counts. The result of a merge, including a merge driver's or a conflict resolution's result, is never evidence for a Mission file. Everything else fails closed.
- **Second rule (#7325)**: a lane that reaches cleanup without a usable landing proof (no proof, no worktree, no branch, or an empty PASS anchor) is kept with a named code. It is never handed to the older branch delete, which cannot see an unlanded lane's unique commit.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consolidate removes the lanes it landed (Priority: P1)

An operator consolidates a three-lane `lanes_with_coord` Mission whose work packages were claimed with `implement` and approved. The squash landing verifies. Lane cleanup reports every lane `Removed`.

**Why this priority**: today every such landing keeps every lane (`NOT_LANDED_ON_NAMED_REMOTE`), so cleanup is a manual step after each Mission (#7747, P1).

**Independent Test**: drive a real three-lane fixture through claim, approve and squash consolidate, then read the cleanup report.

**Acceptance Scenarios**:

1. **Given** a landed three-lane `lanes_with_coord` Mission whose lanes differ from the target only in the coordination-written status log, snapshot, `meta.json` and work package claim frontmatter, **When** lane cleanup runs, **Then** every lane is `Removed` and their branches are gone.
2. **Given** the same Mission where one lane also edited its own work package prompt's body and that edit is not on the target, **When** lane cleanup runs, **Then** that lane is `Kept` and its branch survives.
3. **Given** a lane with product code the target lacks beside an older status log, **When** lane cleanup runs, **Then** the lane is `Kept`.
4. **Given** a lane whose copy of a Mission file reaches the target only through a merge driver's result, **When** lane cleanup runs, **Then** the lane is `Kept`.

### User Story 2 - Doctor prunes the same lanes (Priority: P1)

After consolidation the operator pushes the target to the remote primary branch and runs `spec-kitty doctor workspaces`. The released Mission's lanes are rated landed, and `--prune` removes them.

**Why this priority**: the remedy consolidate prints for a kept lane is `doctor workspaces --prune`, which today refuses the same lanes (`CONTENT_NOT_ON_PRIMARY`), leaving only a manual `git branch -D`.

**Independent Test**: push the landed fixture target to a bare remote's primary branch, run the doctor assessment, read the verdicts.

**Acceptance Scenarios**:

1. **Given** a released Mission's lane that carries only older coordination-written Mission files, **When** doctor assesses it against the remote primary branch, **Then** it is rated landed.
2. **Given** a worktree that is not a released Mission's lane, **When** doctor assesses it, **Then** the plain proof applies and Mission files are not set aside.

### User Story 3 - No lane leaves through the older remover without a proof (Priority: P2)

A lane reaches cleanup after its worktree was deleted, or with an empty PASS anchor, and its branch holds a commit no other ref reaches. Cleanup keeps the lane with a named code; the branch survives.

**Why this priority**: the older remover's branch delete compares against the lane's own expected tip, so an unlanded lane's unique commit is a blind spot (#7325).

**Independent Test**: delete a lane's worktree, add a unique commit on its branch, run cleanup with a landing proof; repeat with an empty PASS anchor.

**Acceptance Scenarios**:

1. **Given** a lane whose worktree is gone and whose branch holds a unique commit, **When** cleanup runs with a landing proof, **Then** the lane is `Kept` with `LANDING_PROOF_UNAVAILABLE` and its branch still exists.
2. **Given** a landing proof whose PASS anchor is empty, **When** cleanup runs, **Then** the lane is `Kept` with `LANDING_PROOF_UNAVAILABLE`.

### Edge Cases

- The lane deleted a Mission file the target still has: not set aside (the lane authored a deletion); the lane is kept.
- The target no longer has the Mission file the lane holds: not set aside; kept.
- Another Mission's files on the lane: never set aside for this Mission.
- Any git read error while proving: the lane is kept (fails closed).
- `mission close --discard` keeps its current remover (out of scope, #7325).
- A lane carrying consolidate's own auto-rebase merges that survived a rollback (#7767): out of scope; stays with the #5604 Mission.

## Domain Language

- **Landing proof**: the evidence that a lane's committed work is already on the landing ref. Not "absorption check" in user-facing prose.
- **Set aside**: a Mission file excluded from the landing proof because the lane never authored it.
- **Ancestor version**: a file version (blob) that the landing ref's own history already holds at that path.
- **Released Mission lane**: a lane of a consolidated or pr-accepted Mission (doctor FR-039 term).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | One public landing proof | As an operator, I want consolidate and doctor to judge a lane by the same landing proof so that they never disagree about whether it landed. | High | Open | [build] | no — a shared-caller test fails until both callers use it |
| FR-002 | Status log containment kept | As an operator, I want the lane's status log set aside only when every one of its event lines is on the target, as today. | High | Open | [ratchet] | yes — paired with the lane-only event negative on the same fixture |
| FR-003 | Never-authored set-aside | As an operator, I want the lane's `status.json`, `meta.json` and `tasks/WP*.md` of its own Mission set aside only when both the lane and the target have the file and the lane never authored its copy (no commit the lane made itself changed it, except a merge that took it whole from the merged-in side; or the target's history holds that version), so that tool-written claim frontmatter no longer keeps landed lanes. | High | Open | [build] | no — the three-lane fixture is Kept today |
| FR-004 | No merge evidence on Mission files | As an operator, I want no merge or merge-driver result counted as evidence for any `kitty-specs/**` path, so that a driver cannot make an unlanded lane look landed. | High | Open | [build] | no — the merge-driver negative is the control |
| FR-005 | Fail closed elsewhere | As an operator, I want every other change the lane made, every deletion the lane made, and every read error to keep the lane. The one deletion that does not is of the lane's own Mission status log: it is append-only and judged by its events, so a lane without a copy has none to lose. | High | Open | [ratchet] | yes — paired with the positive three-lane fixture |
| FR-006 | Consolidate and pr-mode accept adopt the proof | As an operator, I want consolidate's lane cleanup, and the lane cleanup of `accept --mode pr`, to remove every lane the proof shows landed (operator ruling 2026-11-23, 3A). | High | Open | [build] | no — red-first three-lane fixture and the pr-mode fixture |
| FR-007 | Doctor adopts the proof for released Mission lanes | As an operator, I want doctor to apply the set-aside to released Mission lanes, reading the Mission from that lane's own meta, and the plain proof elsewhere. | High | Open | [build] | no — red-first doctor verdict on the pushed fixture |
| FR-008 | Keep a lane with no usable proof | As an operator, I want a lane with a landing proof but no worktree, no branch, or an empty PASS anchor kept with `LANDING_PROOF_UNAVAILABLE`, its branch untouched. | Medium | Open | [build] | no — the unique-commit branch is deleted today |
| FR-009 | Decision recorded | As a maintainer, I want ADR 2026-11-06-1 (O3) amended to record the Mission-file set-aside, including the earlier status-log set-aside (#6736). | Medium | Open | [build] | no — reviewed in the diff |
| FR-010 | Lane's own changes only (ruling 2026-11-24, B) | As an operator, I want any file of the lane's own Mission that the lane never authored set aside whatever the target did with it, so that a planning edit after a lane's last sync no longer keeps it. Merge results stay distrusted; another Mission's files keep FR-005. | High | Open | [build] | no — the dogfood landing kept lanes a and b on `spec.md` |
| FR-011 | Snapshot as a projection (ruling 2026-11-24, C) | As an operator, I want the lane's own `status.json` judged by its status log's containment, never by authorship, so that consolidate's own auto-rebase no longer keeps the lane. | High | Open | [build] | no — the dogfood landing kept lane c |
| FR-012 | Mission-branch proof (ruling 2026-11-24, A) | As an operator, I want consolidate to prove, before the coordination teardown, each lane landed through the Mission branch (tip reached; every product path the lane changed (tree diff from its merge base) landed with the lane's blob or was changed again by another approved lane's own commit on the Mission branch that descends from the lane's last change to it, never by a revert or rewrite made outside the workflow (also one the other lane forked from: the Mission branch's own first-parent line is never a lane's work), a parallel edit or work only merged in, per the operator ruling of 2026-11-24 on Tier R B1 and the Tier R confirm pass; every product path the Mission branch integrated landed with its blob; Mission files accounted for), so that a lane a later lane rewrote is removed. Supersession is judged per path, not per line (operator ruling 2026-11-24, Tier R confirm 2 N1 (a)): an approved lane editing another line of the same file supersedes an out-of-workflow revert or rewrite of this lane's line; such a removal is recoverable: a lane only the Mission-branch proof discharged keeps `refs/spec-kitty/lane-tip/<branch>` at its removed tip and its `Removed` line names it (operator ruling 2026-11-24), while a lane the content proof discharged has its ref cleared (residual, #7838). Doctor after a push, a resume after the teardown and `orchestrator-api consolidate-mission` keep today's behaviour for this shape (residuals). | High | Open | [build] | no — the reworked three-lane fixture keeps lane a |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Proof cost | The proof for one lane makes at most one history walk per set-aside candidate file and completes in under 2 s on a fixture with 12 work packages. | Performance | Medium | Open |
| NFR-002 | Coverage | Every new branch of the proof and the new kept leg is executed by a direct unit test; diff coverage ≥ 90 %. | Reliability | High | Open |
| NFR-003 | Clean gates | ruff, `ruff format --check --force-exclude` and mypy report zero issues on changed files, with no new suppression. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No guard change | The destructive guard (`guarded_landed_removal`, its obligations) is not changed (#7302 out of scope). | Technical | High | Open |
| C-002 | #7767 out of scope | Auto-rebase merges surviving a rollback stay with the #5604 Mission. | Technical | High | Open |
| C-003 | `mission close --discard` unchanged | Its remover is a separate item. | Technical | Medium | Open |
| C-004 | Set-aside list closed | Only the four named Mission file kinds may be set aside when the lane changed them; matrices and other Mission files the lane changed fail closed. A file the lane left untouched (its copy is the merge base's) is no lane change. Amended by operator ruling 2026-11-24 (FR-010, FR-011): a file of the lane's own Mission the lane never authored is no lane change, and `status.json` is judged by its log. | Technical | High | Open |

### Key Entities

- **Lane tip**: the claim-validated commit cleanup proves.
- **Landing ref**: the local target at its PASS anchor (consolidate) or the remote primary tracking ref (doctor).
- **Mission bookkeeping file**: one of the four set-aside kinds under `kitty-specs/<mission>/`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a landed three-lane `lanes_with_coord` fixture, 3 of 3 lanes are reported `Removed` (today 0 of 3). — [build] · no-op passable: no
- **SC-002**: After the target reaches the remote primary branch, doctor rates 3 of 3 of those lanes landed (today 0 of 3). — [build] · no-op passable: no
- **SC-003**: Each named negative (own prompt body edit, product code beside the status log, merge-driver case, unique commit without a worktree, empty PASS anchor) keeps its lane and its branch: 5 of 5. — [ratchet] · no-op passable: yes — each is paired with SC-001 on the same fixture

## Assumptions

- Claim frontmatter is written on the coordination branch and reaches a lane only through the lane's creation point and its sync merges.
- Verified on a real three-lane squash landing (2026-11-22): the squash collapses the coordination history into one commit and the coordination branch is deleted before cleanup, so the lane's older Mission-file versions are not in the target's own history. "Never authored by the lane" is therefore read from the lane's own commit graph (operator ruling 2026-11-23, Decision Moment 01M81KXB).
- A lane's own commits are its first-parent commits that neither the landing ref nor any branch the lane merged in reaches; the coordination history a lane forked from is reached by its first sync merge.

## Known Residual

- A Mission-file version a lane merged in from a branch other than the coordination branch (for example a dependency lane) counts as not authored on this lane. That other lane is judged on its own, and only the four bookkeeping kinds can be set aside. Recorded in the ADR 2026-11-06-1 amendment (operator ruling 2026-11-23).

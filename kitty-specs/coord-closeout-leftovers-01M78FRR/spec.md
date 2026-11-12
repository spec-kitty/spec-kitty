# Mission Specification: Coordination closeout leftovers

**Mission Branch**: `kitty/mission-coord-closeout-leftovers-01M78FRR` (target `fix/7598-coord-closeout-leftovers`)
**Created**: 2026-11-12
**Status**: Draft
**Input**: Sub-epic #7598 (part of epic #7543): #7491, #4041, #5867, #7599, #7600, plus the folds the operator approved.

## Intent Summary (confirmed)

- **Primary actor:** an operator closing out a coordination-topology Mission (`lanes_with_coord`
  or `coord`) with `spec-kitty accept`, `spec-kitty consolidate` (fresh, `--resume`, `--abort`)
  and `spec-kitty archive`.
- **Trigger:** a closeout command stops, refuses, or finishes and prints guidance.
- **Desired outcome:** every refusal on the coordination closeout path names the actual blocker
  and a remedy that works when followed; following a refusal's own remedy never leads to a new,
  unrelated refusal; an archived Mission's coordination worktree, branch and marker can be
  reclaimed through one CLI command.
- **Invariant:** no closeout change may weaken a gate: a coordination commit that did not land
  is still refused, the compare-and-swap and destructive guards stay in force, unabsorbed work
  is never destroyed, and the one rollback authority stays the only rollback path.
- **Source of intent:** the committed research (`research/code-grounding.md`,
  `research/foldable-issues.md`) and four operator rulings recorded as Decision Moments
  (2026-11-12): persist the verified post-projection tip (#7491); a new `archive reclaim`
  command (#4041); named paths, a new error code and mode-aware remedies (#5867, #7600);
  folds #4380 item 2, flat-lanes "Next steps", and the stale squash-refusal rollback comment.

## Domain Language

| Term | Meaning here | Avoid |
|---|---|---|
| Coordination triple | The coordination worktree, the coordination branch, and the `coordination_branch` marker in `meta.json` | "coord stuff" |
| Late coordination window | Coordination-branch commits made after the merge captured the coordination tip, which teardown must prove landed | "late commits" without a base |
| Verified landing | A consolidation record whose reconciliation gate passed for the current target tip | "merged" |
| Archived Mission | A Mission with a record in `.kittify/archive/archived-missions.jsonl` | "closed" |
| Remedy | The next command or action a refusal prints | "hint" |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Resume after keeping the only copy completes (Priority: P1) — #7491

An operator consolidates a coordination Mission whose planning files were amended on the target
after a lane carried an earlier version. The run lands, then stops with
`COORD_TEARDOWN_KEPT_ONLY_COPY` because review-cycle files are untracked in the coordination
worktree. The operator commits them on the coordination branch as told and runs
`consolidate --resume`.

**Why this priority**: today the remedy leads to a permanent refusal naming files the operator
never touched; the Mission cannot finish teardown without hand-merging planning files.

**Independent Test**: drive the reproduction (lane edits a planning file, target edits it
differently, untracked review cycle) through `spec-kitty consolidate` then `--resume`.

**Acceptance Scenarios**:

1. **Given** a landed coordination Mission stopped by `COORD_TEARDOWN_KEPT_ONLY_COPY`, and planning
   files that differ between the coordination branch and the target only because of the
   merge's own lane content and the target's later amendments, **When** the operator commits the
   listed files on the coordination branch and runs `consolidate --resume`, **Then** the late
   commit is projected, teardown completes, and the exit code is 0.
2. **Given** the same Mission, **When** the operator's late coordination commit also edits a
   planning file that is not on the target, **Then** `--resume` still refuses with
   `COORD_LATE_PROJECTION_REFUSED` naming that file.
3. **Given** a resume of a run that never verified its landing, **When** `--resume` runs, **Then**
   the late window keeps today's base (the pre-mutation coordination snapshot).

---

### User Story 2 - Reclaim an archived Mission's coordination triple (Priority: P1) — #4041

An operator archives a terminal coordination Mission and wants its coordination worktree,
branch and marker gone, without hand-run git.

**Why this priority**: the space is unrecoverable through any supported command today and grows
with every finished Mission.

**Independent Test**: archive a landed coordination Mission, run `spec-kitty archive reclaim
<mission>`, then check `git worktree list`, the branch list and `meta.json`.

**Acceptance Scenarios**:

1. **Given** an archived Mission whose coordination branch's content has landed on the target,
   **When** the operator runs `spec-kitty archive reclaim <mission>`, **Then** the coordination
   worktree is removed, the coordination branch is deleted, the marker is flattened and the
   change is committed, and the command reports each step.
2. **Given** a Mission that is not archived, **When** reclaim runs, **Then** it refuses with a
   named code and changes nothing.
3. **Given** an archived Mission whose coordination worktree has uncommitted changes, **When**
   reclaim runs, **Then** it refuses, names the files, keeps the whole triple, and says how to
   proceed.
4. **Given** an archived Mission whose coordination branch holds commits whose content is not on
   the target, **When** reclaim runs, **Then** it refuses, names the branch and the unabsorbed
   commits, and keeps the triple.
5. **Given** an archived Mission whose triple was already reclaimed, **When** reclaim runs again,
   **Then** it reports that nothing is left to reclaim and exits 0.

---

### User Story 3 - The squash projection refusal names what did not land (Priority: P2) — #5867

**Why this priority**: the refusal gives no path, no code, and a remedy that repeats the failure.

**Independent Test**: provoke the squash projection refusal (coordination copy of a projected
bookkeeping file differs from the target's copy) and read the output.

**Acceptance Scenarios**:

1. **Given** a squash consolidation whose projected coordination bookkeeping did not land, **When**
   the gate refuses, **Then** the output carries a named error code, lists each path that did
   not land (up to a cap, with a count of the rest) with its reason, and gives a remedy per
   reason; the exit code and rollback behaviour are unchanged.
2. **Given** a transient git-probe failure, **When** the gate refuses, **Then** the remedy says a
   re-run may succeed; for a deterministic cause it does not tell the operator to simply resume.

---

### User Story 4 - accept's "Next steps" matches the topology (Priority: P2) — #7599

**Acceptance Scenarios**:

1. **Given** a coordination Mission accepted in local mode on its target branch, **When** accept
   prints "Next steps", **Then** it names the branch the record was committed to and points to
   `spec-kitty consolidate --mission <handle>`; it never says "No merge needed".
2. **Given** a flat `lanes` Mission with lanes still to consolidate, accepted in local mode on its
   target, **Then** "Next steps" points to consolidate, not "No merge needed".
3. **Given** a Mission with nothing to consolidate, accepted on its target, **Then** the existing
   "No merge needed" text stays.

---

### User Story 5 - An `--abort` refusal completes the abort (Priority: P2) — #7600

**Acceptance Scenarios**:

1. **Given** `consolidate --abort` cannot restore a branch because a checkout holds uncommitted
   edits, **When** it refuses, **Then** it names the checkout and tells the operator to commit or
   stash and re-run `--abort`; it does not tell them to `--resume`.
2. **Given** `--abort` finds a branch moved by another actor, **Then** the remedy names
   `consolidate --abort --release-branch <b> --release-reason "..."`.
3. **Given** `--abort` keeps a verified landing, **Then** it says the landing is kept and offers
   `--resume` explicitly as the way to finish teardown.
4. **Given** the same dirty-checkout error raised outside consolidation (for example the review
   lane fast-forward), **Then** its text does not tell the operator to resume a consolidation.

### Edge Cases

- A legacy consolidation record without the new persisted tip resumes with today's behaviour.
- A rollback that fully restores clears the persisted tip with the other coordination anchors.
- The persisted tip is not an ancestor of the live coordination tip (history rewritten): fall
  back to today's base.
- Reclaim on a Mission with no coordination topology (`single_branch`): refuse with a named code.
- Reclaim when the coordination worktree is already gone but the branch and marker remain:
  delete the branch and flatten the marker.
- Teardown that keeps the marker when the worktree is already gone (#4380 item 2) describes
  that state truthfully.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Resume completes after following the kept-only-copy remedy | As an operator, I want `consolidate --resume` after committing the files `COORD_TEARDOWN_KEPT_ONLY_COPY` named to complete teardown with exit 0 when the only coordination-vs-target differences come from the merge itself and the target's own later edits. | High | Open | [build] | no — red today with the reproduction (exit 1) |
| FR-002 | Real late changes still refuse | As a reviewer, I want a late coordination commit that changes a planning file not on the target to still refuse `COORD_LATE_PROJECTION_REFUSED` on resume, naming the file. | High | Open | [ratchet] | yes — paired with FR-001 on the same fixture as the positive control |
| FR-003 | Narrow base only after a verified landing | As a reviewer, I want the resume late window to start at the post-projection coordination tip only when the record shows a verified landing and that tip is an ancestor of the live coordination tip; otherwise at the pre-mutation snapshot. | High | Open | [build] | no — unit cells for both arms |
| FR-004 | Persisted tip follows the PASS anchor | As a reviewer, I want the persisted post-projection tip written with the reconciliation PASS anchor and cleared or restored wherever that anchor is. | High | Open | [build] | no — cell: a full-restore rollback leaves no persisted tip |
| FR-005 | Archive reclaim command | As an operator, I want `spec-kitty archive reclaim <mission>` to remove an archived Mission's coordination worktree, delete its coordination branch and flatten-and-commit its marker, reporting each step. | High | Open | [build] | no — red today (no command) |
| FR-006 | Reclaim refuses unsafe cases | As an operator, I want reclaim to refuse, with a named code and no change, when the Mission is not archived, has no coordination topology, has a dirty coordination worktree, or has coordination commits whose content is not on the target. | High | Open | [build] | no — one cell per refusal against a positive control |
| FR-007 | Reclaim is idempotent | As an operator, I want a second reclaim to report nothing left and exit 0, and a partial state (worktree gone, branch left) to finish the remaining steps. | Medium | Open | [build] | no |
| FR-008 | Archive points at reclaim | As an operator, I want `archive create` of a Mission that still has a coordination triple to print the reclaim command. | Low | Open | [build] | no |
| FR-009 | Squash projection refusal names paths | As an operator, I want the squash projection refusal to carry a named error code and list each path that did not land with its reason (capped, with a remaining count), and a remedy per reason. | Medium | Open | [build] | no — red today (no path in the output) |
| FR-010 | Topology-aware accept "Next steps" | As an operator, I want accept's local-mode "Next steps" to point to `spec-kitty consolidate --mission <handle>` and name where the record went whenever the Mission still has lanes or a coordination branch to consolidate, and to keep "No merge needed" only otherwise. | Medium | Open | [build] | no — red today for a coordination Mission |
| FR-011 | `--abort` refusals complete the abort | As an operator, I want each `--abort` refusal to name its blocker and the remedy that completes the abort (commit or stash the named edit then re-run `--abort`; `--release-branch` for a branch moved by another actor), and to offer `--resume` only for a kept verified landing, labelled as the way forward. | Medium | Open | [build] | no — red today ("resume the consolidation") |
| FR-012 | Neutral dirty-checkout error text | As an operator of any command, I want the dirty-checkout ref-advance error to describe the blocker without prescribing a consolidate command; each caller appends its own next step. | Medium | Open | [build] | no — cell on a non-consolidate caller |
| FR-013 | Truthful marker-kept teardown text (#4380 item 2) | As an operator, I want the teardown refusal that keeps the marker to describe the actual state of the worktree and branch. | Low | Open | [build] | no |
| FR-014 | Stale squash-refusal comment corrected | As a maintainer, I want the comment beside the squash projection refusal to state that the refusal exits through the rollback door. | Low | Open | [folded] | yes — documentation-only, reviewed by diff |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Complexity ceiling | Every touched function stays at cyclomatic complexity 15 or lower (ruff C901). | Maintainability | High | Open |
| NFR-002 | Lint and types clean | `ruff check`, `ruff format --check --force-exclude` and `mypy` report 0 new issues on changed files. | Maintainability | High | Open |
| NFR-003 | Coverage of new code | New and changed lines reach at least 90% line coverage in the targeted tests (CI diff-cover gate). | Reliability | High | Open |
| NFR-004 | Bounded refusal output | A refusal lists at most 20 paths and prints the count of the rest. | Usability | Medium | Open |
| NFR-005 | Command latency | `archive reclaim` on a Mission with one coordination worktree completes in under 5 seconds on a typical project. | Performance | Low | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | One rollback authority | No second rollback or restore path; `rollback.py` stays the only one, and the AST pin stays green. | Technical | High | Open |
| C-002 | Gates not weakened | Compare-and-swap advances, the projection teardown gate and the late-window proof keep refusing unlanded content; exit codes of existing refusals are unchanged. | Technical | High | Open |
| C-003 | Never destroy unabsorbed work | Reclaim goes through the destructive guard; a branch delete is bound to the expected tip and proven absorbed. At most one new named `operator_intent` caller is added to the routing gate pin (operator ruling). | Technical | High | Open |
| C-004 | Placement untouched | No change to the placement seam, spec-commit or safe-commit routing (sub-epic C, #7546). | Technical | High | Open |
| C-005 | Packs untouched | No edit under `packs/built-in/` or `packs/internal/`. | Technical | High | Open |
| C-006 | No new ratchet gates | No new size or ratchet gate; the archive core module stays record-only. | Technical | Medium | Open |
| C-007 | Terminology | Mission, not feature; name the sense of "primary" and "merge" in new text. | Business | Medium | Open |

### Key Entities

- **Consolidation record**: gains one optional field, the verified post-projection coordination
  tip, absent on legacy records.
- **Archive record**: read by reclaim to prove the Mission is archived; never written by reclaim.
- **Coordination triple**: the reclaim target.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The #7491 reproduction resumes to exit 0 with all planning files untouched, and its negative control still refuses — [build] · no-op passable: no
- **SC-002**: After `archive reclaim`, `git worktree list`, the branch list and `meta.json` show no coordination triple for the Mission, with no hand-run git — [build] · no-op passable: no
- **SC-003**: 100% of the closeout refusals this Mission touches name a blocker and a remedy that, when followed in the test, reaches exit 0 or a different named state — [build] · no-op passable: no
- **SC-004**: No refusal reachable from `consolidate --abort` tells the operator to resume, except the labelled kept-verified-landing case — [build] · no-op passable: no

## Assumptions

- "Content landed" for reclaim is proved by absorption of the coordination branch tip into the
  target (ancestor, or a no-op merge-tree), the same proof the lane cleanup uses; on git older
  than 2.38 reclaim refuses rather than guessing.
- A canceled archived Mission whose coordination branch holds unabsorbed work is refused and
  pointed at `spec-kitty mission close --discard`; reclaim never discards work.
- Legacy records stuck on #7491 recover on a fresh run, not on `--resume` (no migration).

## Out of Scope

- #4380 item 1 (orchestrator-api error code for a plain teardown error), #7301, #5784, #5791,
  #7121, #7300 (see `research/foldable-issues.md`).
- Lane worktrees of archived Missions that `doctor workspaces --prune` cannot already reclaim.

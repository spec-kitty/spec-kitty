# Mission Specification: A lane window that was never created names the shape it is in

**Mission Branch**: `issue-7120-lane-window-never-created`
**Created**: 2026-11-03
**Status**: Draft
**Input**: Issue #7120 — "A WP whose work was committed on the target/topic branch cannot reach `for_review`: the lane evidence window is unreadable and the refusal names no executable recovery".

## Context and scope

`move-task` refuses an unforced move into review territory when the work package's
implementation-evidence window (`planning_commit..<lane branch>`) shows no change to its
`owned_files`. The refusal is correct and stays correct: it is what stops a Mission from
recording a reviewable work package whose implementation nobody can point at.

The defect is what the refusal says. When the Mission never created its lane branches at all
— a `lanes` Mission whose single agent implemented on the target/topic branch, the normal shape
for a small fix (#6871, #7082, #6859) — the window ends at a branch that does not exist and
never did. `git diff` fails, the diff probe raises, and every failure of that probe reaches the
operator as the same sentence:

```
IMPLEMENTATION_UNREADABLE: WP02's evidence window <base>..<lane branch> (lane-b) could not be diffed
(...), so its implementation cannot be verified. Make the lane branch and the recorded planning
commit readable, then retry.
```

"Make the lane branch readable" is not something an operator can do. The branch does not exist;
creating it now would fabricate the very evidence the gate exists to check; `--force` bypasses a
review-evidence gate; and re-running `agent action implement` provisions a lane worktree for work
that already exists elsewhere. So an agent loops, and the Mission record stays `in_progress`
after the code shipped — #7082's "mission never closed though the code shipped" complaint.

**This Mission implements the issue's option 1: name the shape and a real next step, and stop the
loop.** It does not widen the evidence window. The issue's option 2 — judging a `lanes` Mission
on `planning_commit..target_branch` when its lane branch is absent, exactly as
`single_branch_evidence_window` already does for a `single_branch` Mission — changes what evidence
an approval rests on. That is a policy change that needs the operator's ruling, and it stays open
on #7120. #7121 (an anchorless coordination run) is a different axis and is out of scope.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An operator reads a refusal that names the shape it is in (Priority: P1)

A maintainer (or an agent acting for one) runs `spec-kitty agent tasks move-task WP02 --to
for_review` on a `lanes` Mission whose work was committed on the target branch and whose lane
branches were never created. The refusal still refuses, but it says which shape it detected, that
there is no lane window to restore, that creating the branch now would fabricate the evidence, and
that the evidence policy for this shape is unruled (#7120) — so the next step is to report it, not
to retry.

**Why this priority**: It is the whole point of the issue: the last gate between a finished
Mission and a reviewable work package currently gives an instruction that cannot be carried out,
and the agent loops. This story alone removes the loop.

**Independent Test**: Build the real-git fixture the issue describes (a `lanes` Mission, planning
commit recorded, the work package's change committed on the target branch, no lane branch), call
the pre-existing gate, and read the refusal.

**Acceptance Scenarios**:

1. **Given** a `lanes` Mission whose lane branches were never created, **When** a work package
   moves into review unforced, **Then** the refusal is `IMPLEMENTATION_UNREADABLE` and its text
   names the absent branch, states that the Mission's work is on the target branch instead, and
   says creating the branch would fabricate the evidence.
2. **Given** the same refusal, **When** the operator reads it, **Then** it names a next step that
   exists (report the shape; the ruling is #7120) and no longer contains the unsatisfiable
   instruction "Make the lane branch and the recorded planning commit readable, then retry".
3. **Given** the same Mission, **When** the work package moves into review, **Then** it does not
   move: the work package stays where it was, and nothing is fabricated to make it pass.

---

### User Story 2 - The restore remedy is named only where it is real (Priority: P2)

A lane branch that once existed and is gone (pruned, or never fetched) is a different shape with
a real remedy: restore it from the recorded lane-tip ref or the pull request's head. An operator
who has that shape keeps being told to restore it, and is not told the Mission "never created its
lanes".

**Why this priority**: Without this split the new sentence would be a second wrong answer for the
other shape — a pruned lane — which is the shape #6780 already handles.

**Independent Test**: Same fixture with a second lane branch present, and with a recorded
`refs/spec-kitty/lane-tip/<branch>` ref, and read the refusal.

**Acceptance Scenarios**:

1. **Given** a `lanes` Mission with at least one live lane branch, **When** the work package's own
   lane branch is absent, **Then** the refusal names restoring that branch from
   `refs/spec-kitty/lane-tip/<branch>` or the pull request's head, and does not claim the Mission
   never created its lanes.
2. **Given** a window whose branch resolves but whose diff cannot be read (a missing object, a
   corrupt ref), **When** the gate runs, **Then** the present, pre-existing "could not be
   diffed" refusal is unchanged — a present ref is never reported as an absent one.

---

### User Story 3 - `accept` and `consolidate` give the same answer (Priority: P3)

The same shape reaches `accept`/`consolidate` through `consolidation.wp_evidence`, whose per-work
-package `IMPLEMENTATION_UNREADABLE` cause line already distinguishes an absent tip from an
unreadable window. It gains the same never-created clause, so the two surfaces that refuse on this
axis do not disagree about the shape.

**Why this priority**: The issue names both files; a maintainer who reaches the later gate must not
be sent back to the earlier one's impossible instruction.

**Independent Test**: Evaluate evidence for an approved work package whose lane branch never
existed and assert the refusal's cause line.

**Acceptance Scenarios**:

1. **Given** an approved work package whose lane window never existed, **When** evidence is
   evaluated for `accept`/`consolidate`, **Then** its `IMPLEMENTATION_UNREADABLE` line carries the
   never-created cause and the missing ruling, and the verdict stays a refusal.
2. **Given** a work package whose lane branch was pruned and whose caller supplied a verified PR
   landing commit, **When** evidence is evaluated, **Then** the existing landed-window behaviour
   (#6780) is unchanged.

### Edge Cases

- A `single_branch` Mission: unchanged. It has no lane branches by design and windows
  `planning_commit..mission_branch`; its `SINGLE_BRANCH_*` codes and wording stay as they are.
- A `lanes.json` with no planning commit: unchanged `EVIDENCE_WINDOW_UNCOMPUTABLE` (remedy
  `finalize-tasks` exists and is named).
- A planning lane (window ends at the target branch): the tip is the target, which normally
  exists; if it is absent, the absent-branch path must not claim "this Mission never created its
  lanes" — the target branch is not a lane branch.
- A fetch/prune in progress: a branch ref that exists but cannot be read is NOT absent and keeps
  the unreadable wording (fail closed, #6780).
- An owned checkout / `--force`: the gate does not run, unchanged.
- Dependency-window widening (`widened_lane_paths`) failing: unchanged.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Absence is distinguished from unreadability | As an operator, I want the refusal to say the lane branch does not exist, so that I do not chase a git error that is really an absent branch. | High | Open | [build] | no |
| FR-002 | The never-created shape is named | As an operator, I want the refusal to say this Mission never created its lane branches and committed its work on the target branch, so that I recognise the shape instead of guessing. | High | Open | [build] | no |
| FR-003 | The unsatisfiable retry is gone | As an operator, I want the refusal to stop telling me to make an absent branch readable and retry, so that I stop looping. | High | Open | [build] | no |
| FR-004 | Fabrication is named as fabrication | As a maintainer, I want the refusal to say creating the branch now would fabricate the evidence the gate checks, so that no one talks themselves into it. | High | Open | [build] | no |
| FR-005 | The missing ruling is named | As a maintainer, I want the refusal to name the open ruling (#7120) and that the honest next step is to report it, so that the decision reaches a human. | High | Open | [build] | no |
| FR-006 | The restore remedy survives for a pruned branch | As an operator whose lane branch was pruned, I want to be told to restore it from the lane-tip ref or the PR head, so that the real recovery is not lost. | Medium | Open | [ratchet] | no |
| FR-007 | An existing-but-unreadable ref is unchanged | As a maintainer, I want a present ref that cannot be read to keep the pre-existing unreadable refusal, so that fail-closed behaviour is not weakened. | High | Open | [ratchet] | no |
| FR-008 | `accept`/`consolidate` carry the same cause | As an operator reaching the later gate, I want the same never-created cause, so that the two surfaces do not disagree. | Medium | Open | [build] | no |
| FR-009 | The gate still refuses | As a maintainer, I want the work package to stay where it was, so that a diagnosable refusal never becomes a pass. | High | Open | [ratchet] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | One extra probe on the failure path only | The absent-branch probe runs only after a diff has already failed, so a passing gate takes no additional git call (at most one `git show-ref` per absent candidate, never on the success path). | Performance | High | Open |
| NFR-002 | Fail closed | Any probe that cannot be read (git error, unreadable ref, non-git directory) reads as "not absent", so the refusal stands and nothing passes on an unknown. | Reliability | High | Open |
| NFR-003 | No new code or flag | No new evidence code, CLI flag, exit code or config key: `IMPLEMENTATION_UNREADABLE` keeps its meaning and its machine contract. | Compatibility | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No widening of the evidence window | The Mission may not change which window counts as evidence for a `lanes` Mission; option 2 of #7120 needs the operator's ruling and is out of scope. | Business | High | Open |
| C-002 | Single canonical authority | The absence probe and the cause text live in `consolidation/wp_evidence.py`, which both surfaces already call; no second copy of the rule in `move-task`. | Technical | High | Open |
| C-003 | Red first | The defect's test fails against the pre-fix source before the fix lands. | Technical | High | Open |

### Key Entities

- **Evidence window**: `(planning_commit, tip)`; the tip is a lane branch for a code lane, the target
  branch for a planning lane, the Mission branch for a `single_branch` Mission.
- **Absent branch ref**: a local branch ref that `git show-ref --verify` reports as `exit 1`; not
  the same as a ref that exists and cannot be read (`exit 128`).
- **Never-created lane shape**: a `lanes`/`coord` Mission in which no code lane of `lanes.json` has
  a branch — the Mission ran on its target branch.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The `move-task` refusal for the recorded #7120 fixture (the exact shape in the issue) no longer contains the sentence "Make the lane branch and the recorded planning commit readable, then retry" on the absent-branch path — that wording survives only for a ref that exists and cannot be read — and instead names the absent branch, the target-branch shape, the fabrication warning and the open ruling. — [build] · no-op passable: no
- **SC-002**: A `lanes` Mission with one live lane branch and one absent lane branch still carries the restore remedy (lane-tip ref or PR head) — the #6780-shaped case is not regressed. — [ratchet] · no-op passable: no
- **SC-003**: 100% of the unit tests that pin the unreadable branch of the evidence axis pass unchanged in meaning: a present-but-unreadable ref still refuses with "could not be diffed", and a refused work package never changes lane. — [ratchet] · no-op passable: no

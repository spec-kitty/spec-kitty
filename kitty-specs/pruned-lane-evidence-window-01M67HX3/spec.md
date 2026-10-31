# Mission Specification: Evidence survives a pruned lane branch

**Mission Branch**: `issue-6780-pruned-lane-evidence-window`
**Created**: 2026-10-30
**Status**: Draft
**Input**: GitHub issue spec-kitty/spec-kitty#6780 — "[bug] accept --mode pr may refuse every done work package with IMPLEMENTATION_UNREADABLE once lane branches are pruned (follow-up of #6715)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A PR-accepted Mission lands even after its lane branches are pruned (Priority: P1)

A maintainer runs a lanes Mission, implements and independently reviews its work
packages, merges the lanes into the mission branch and lands that branch with a
GitHub pull request. Afterwards the local lane branches are pruned — the normal
post-merge cleanup, since their content is on the target. The maintainer then
runs the terminal acceptance step for a PR-landed Mission:

`spec-kitty accept --mode pr --merge-commit <sha> --attest-first-landing-commit`

The acceptance succeeds. Each approved/done work package is still required to
show a real change to its `owned_files` in its evidence window; the window's tip
is the verified landing commit instead of a lane branch that no longer exists.

**Why this priority**: Today every work package refuses with
`IMPLEMENTATION_UNREADABLE`, which no attestation can lift, so the mission can
never be accepted through the documented `--mode pr` path once its lane branches
are gone. The deliverables are on the target; the refusal is a false negative.

**Independent Test**: Build a lanes Mission in a real git repository, merge the
lane branch into the mission branch, land the mission branch on the target with a
PR-shaped merge commit, delete the lane branch, then run the production entry
point `accept(mode="pr", merge_commit=<sha>, attest_first_landing=True)`: the
acceptance completes and records the merge as the review baseline.

**Acceptance Scenarios**:

1. **Given** a lanes Mission whose approved work package's lane branch was merged into the mission branch and landed on the target through a verified merge commit, **and** the local lane branch ref has been deleted, **when** `accept --mode pr --merge-commit <sha>` runs, **then** the work package passes the implementation-evidence gate, the acceptance completes, and `baseline_merge_commit`/`pr_merge_commit` are recorded.
2. **Given** the same fixture, **when** the accept runs, **then** the refusal no longer mentions `IMPLEMENTATION_UNREADABLE` and the working tree is left clean.

### User Story 2 - The gate still refuses a hollow work package (Priority: P1)

The fix must not turn the #6715 gate into a rubber stamp. The landed window is
judged exactly as the lane window was: a work package with no change to its
`owned_files` between the recorded planning commit and the landing commit still
refuses, with `IMPLEMENTATION_MISSING`, and still requires either real
implementation or the operator's no-implementation attestation.

**Why this priority**: #6715 exists because a claimed-but-never-implemented work
package landed as done. A window that is wider in the tip direction must not
become a window that proves nothing.

**Independent Test**: On the same fixture shape, leave one approved work package
without any committed change to its owned files and prune its lane branch; the
accept refuses with `IMPLEMENTATION_MISSING` naming that work package, and no
acceptance write happens.

**Acceptance Scenarios**:

1. **Given** a pruned lane branch and a verified landing commit, **when** an approved work package has no owned-file change in the landed window, **then** the refusal names `IMPLEMENTATION_MISSING` for it and nothing is written.
2. **Given** the same work package, **when** the operator supplies `--attest-no-implementation <WP> --attest-reason "<why>"`, **then** the attestation is accepted as the lift it is today (an attestation still cannot lift an unreadable window, only a missing implementation).

### User Story 3 - When nothing can stand in, the refusal says why and what to do (Priority: P2)

If no verified landing commit is available (an accept without `--merge-commit`,
or a lane branch that is gone during implementation), the refusal stays
fail-closed but becomes honest and actionable: it names the pruned/absent lane
branch as the cause and gives the two real remedies — restore/fetch the branch, or
run `accept --mode pr --merge-commit <sha>` so the evidence is judged against the
verified landing.

**Why this priority**: The current recovery line ("make the lane branch and the
recorded planning commit readable (restore or fetch them)") is the only advice an
operator gets, and in the PR-landed case it is advice that leads back to the same
blanket refusal for a mission whose work has already landed.

**Independent Test**: Delete the lane branch, run `accept` without
`--merge-commit`, and read the refusal: it names the absent lane branch ref, not
a generic "could not be diffed", and its recovery line names both remedies.

**Acceptance Scenarios**:

1. **Given** a deleted lane branch and no `--merge-commit`, **when** accept runs, **then** it refuses with `IMPLEMENTATION_UNREADABLE` and the text names the missing lane branch plus the `--merge-commit` remedy.
2. **Given** a lane branch that is present and readable, **when** accept runs, **then** the lane-branch window is used exactly as before and no fallback text appears.

### Edge Cases

- **Planning lane** (`lane-planning`): its window tip is the target branch, not a lane branch; it is unaffected unless the target ref itself is unresolvable, in which case it takes the same fallback when a landing commit is supplied.
- **Recorded planning commit is not an ancestor of the landing commit** (a mis-recorded `lanes.json`, or a landing commit from a different history): the fallback is refused — the window would not describe this Mission's work — and the refusal says so.
- **Unreadable landing commit** (the SHA was verified when the request was parsed but the object is gone): the window stays `IMPLEMENTATION_UNREADABLE`; the gate never passes on a git error.
- **A lane branch that exists but whose diff errors**: unchanged — no fallback is attempted, because the branch is readable and the failure has another cause.
- **`--no-commit` / `--diagnose`**: the same window choice, report-only, as today.
- **Dependency widening**: with a pruned lane branch the dependency windows must be taken against the same stand-in tip, never against the deleted branch name (which would reintroduce the blanket refusal).
- **single_branch Missions**: out of scope; they already window against the mission branch, which the landing keeps reachable.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Landed window for a pruned lane branch | As a maintainer of a PR-landed Mission, I want an approved work package whose lane branch was pruned to be judged against the verified landing commit, so that an accept that should pass does not refuse every package. | High | Open | [build] | no |
| FR-002 | Lane branch stays the first choice | As a maintainer, I want the lane-branch window used whenever the branch is readable, so that the fix cannot reinterpret a Mission whose lanes are intact. | High | Open | [ratchet] | no — paired with the pruned-branch arm on the same fixture |
| FR-003 | Hollow work package still refuses | As a maintainer, I want a work package with no owned-file change between the planning commit and the landing commit to refuse with `IMPLEMENTATION_MISSING`, so that #6715's gate keeps its teeth. | High | Open | [ratchet] | no — same fixture, one WP implemented and one not |
| FR-004 | Honest, actionable refusal without a landing commit | As an operator, I want the refusal to name the absent lane branch and the `--merge-commit` remedy, so that I am not told to "restore or fetch" a branch whose work already landed. | High | Open | [build] | no |
| FR-005 | Attestation planning reads the same window | As an operator, I want `--attest-no-implementation` on a PR-accepted Mission to be judged against the same window as the gate, so that one refusal does not contradict the other. | Medium | Open | [build] | no |
| FR-006 | Unresolvable stand-in fails closed | As a maintainer, I want the fallback skipped or refused when the planning commit is not an ancestor of the landing commit or the landing commit cannot be read, so that a window never describes someone else's history. | High | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded git probes | The fallback adds at most one ancestor probe and, only when the lane branch ref is absent, one extra `git diff` per lane; a Mission with readable lane branches issues no new probe at all. | Performance | High | Open |
| NFR-002 | No gate weakening | No skip, xfail, filter marker or silenced check is introduced; the pass criteria of the #6715 axis (`IMPLEMENTATION_MISSING`, `REVIEW_NOT_INDEPENDENT`, `EVIDENCE_WINDOW_UNCOMPUTABLE`) keep failing closed. | Reliability | High | Open |
| NFR-003 | One refusal text, every surface | The `--json` `error`/`error_code`/`error_codes` payload and the human refusal are produced from the same `EvidenceReport`, so the cause and remedy read identically on both. | Operability | Medium | Open |
| NFR-004 | No new operator flags | The fix uses the existing `--merge-commit` verification as the source of the landing commit; no new CLI flag, config key or environment variable is added. | Compatibility | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|--------|--------|
| C-001 | Scope is the evidence tip | Only the tip standing in for a pruned lane branch, the refusal text and the accept-side plumbing change; the owned-content, independence and cancellation rules of `consolidation/wp_evidence.py` are untouched. | Technical | High | Open |
| C-002 | Canonical seams only | Branch/ref readability is asked through the existing `specify_cli.lanes._git` / `specify_cli.consolidation.git_probes` seams; the landing commit comes from `consolidation.baseline.verify_pr_merge_evidence` via the accept request, never re-derived by string inspection. | Technical | High | Open |
| C-003 | Landed evidence is opt-in | The fallback only exists when the caller supplies a commit it has already verified as the PR landing; consolidate, `move-task` and orchestrator-api keep calling the axis without one and therefore keep today's strictness. | Business | High | Open |

### Key Entities

- **Evidence window**: `(planning_commit, tip)` pair whose tree diff decides the #6715 axis; the tip is a lane branch, the target branch (planning lane) or the mission branch (single_branch).
- **Verified landing commit**: the PR merge/squash commit that `accept --mode pr --merge-commit` verified before any acceptance write; the only stand-in tip this Mission accepts.
- **Evidence report**: `EvidenceReport` — refusal text, per-work-package verdict codes and lifted attestations; the single surface both output lanes render.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The reproduction — lanes Mission, lane merged into the mission branch, PR-shaped landing on the target, local lane branch deleted, `accept(mode="pr", merge_commit=…, attest_first_landing=True)` — fails on the pre-fix code with `IMPLEMENTATION_UNREADABLE` and passes after the fix, leaving a clean tree with the merge recorded — [build] · no-op passable: no
- **SC-002**: On the same fixture a work package with no owned-file change anywhere in the landed window still refuses with `IMPLEMENTATION_MISSING`, and no acceptance write occurs — [ratchet] · no-op passable: no
- **SC-003**: With the lane branch present, the lane-branch window is used and the new text never appears (the control arm on the same fixture) — [ratchet] · no-op passable: no
- **SC-004**: With the lane branch deleted and no `--merge-commit`, the refusal names the absent lane branch and the `--merge-commit` remedy, on both the human and `--json` lanes — [build] · no-op passable: no
- **SC-005**: The existing #6715 / #5939 evidence and independence test modules pass with no assertion weakened or skipped — [ratchet] · no-op passable: no

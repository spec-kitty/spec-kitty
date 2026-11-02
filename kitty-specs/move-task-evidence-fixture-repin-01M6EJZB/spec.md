# Mission Specification: Re-pin the move-task fixtures refused by the owned-file evidence gate

**Mission Branch**: `issue-7057-move-task-evidence-fixture-repin`
**Created**: 2026-11-02
**Status**: Draft
**Input**: GitHub issue [#7057](https://github.com/spec-kitty/spec-kitty/issues/7057) — "Red on main (out of matrix): 8 tests/tasks/test_move_task_git_validation_unit.py nodes refused with IMPLEMENTATION_MISSING", filed per the charter's Pre-existing Failure Reporting Rule while validating #7022.

## Mission Boundary

`tests/tasks/test_move_task_git_validation_unit.py` is an out-of-matrix directory
(`.github/ci-module-registry.yml`, `tests/tasks`), so per-PR CI never runs it. On
`origin/main` `9aed3a8012` (issue reported at `bec07fb57`) **8 of its 15 nodes fail**,
every one of them refused by the owned-file evidence gate before the behaviour under
test is reached:

```
IMPLEMENTATION_MISSING: WP01 cannot move into review: no change to its owned_files
in its evidence window <sha>..kitty/mission-017-test-feature-lane-a (lane-a).
```

**The gate is right; the fixtures are stale.** The gate (#6715, `8c5703e48f` plus the
`#6780` follow-ups `864f20fb9`, `998424417`, `c8383fe2d`) refuses a review-ward move
whose evidence window holds no change to the work package's `owned_files`. This
module's `git_repo_with_worktree` fixture (line 42) writes a WP01 with **no
`owned_files` at all** and then commits its lane deliverable as
`implementation.txt` at the repository root — a path no ownership glob can match, and
whose `lanes.json` `write_scope` is `src/**`
(`write_single_lane_manifest`, `tests/lane_test_utils.py`). With an empty pattern list,
`wp_evidence.has_owned_change` can never match, so every review-ward move is refused
before sibling guards (uncommitted work, kitty-specs contamination, event-persistence
readback, done-override, auto-commit recovery) get a chance to run.

The mission re-pins the fixture so it models a real Mission: the fixture WP declares
`owned_files`, its lane branch commits inside that ownership, and the done-transition
test names the approver that #6715's independence gate requires. **No production code
changes.** The refusal itself stays exactly as strict as it is on `main`; no test is
skipped, xfailed, deselected, retried or loosened, and the existing 15 nodes are the
ratchet.

Out of scope (hard): any change under `src/`; any change to the evidence gate, its
codes, its message or its ordering; the other out-of-matrix directories and other
files named by the "Nightly suite red" issues.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The out-of-matrix suite tells the truth again (Priority: P1)

A maintainer or agent validating a Landing reads
`tests/tasks/test_move_task_git_validation_unit.py` as evidence that `move-task`'s git
validation and merge-ancestry guardrails still behave. Today 8 of 15 nodes are refused
by an evidence gate that has nothing to do with what they test, so a genuine regression
in those guardrails would be hidden behind known noise — and the module cannot be run as
a pre-merge check at all.

**Why this priority**: red `main` == no release (charter Standing Order #9); the red is
cleared at the root, never green-washed.

**Independent Test**: Run the module on the planning base (8 failed, 7 passed) and on
the branch (15 passed), with no test selection or marker changes.

**Acceptance Scenarios**:

1. **Given** `origin/main` `9aed3a8012`, **When** `uv run --frozen pytest -q -p no:randomly -n0 tests/tasks/test_move_task_git_validation_unit.py` runs, **Then** the 8 nodes named in #7057 fail with `IMPLEMENTATION_MISSING` and the other 7 pass.
2. **Given** this mission's branch, **When** the same command runs, **Then** all 15 nodes pass, and the node set and markers are unchanged.

### User Story 2 - The fixture models the contract the gate enforces (Priority: P1)

A maintainer reading the fixture after this mission sees a Mission that a real
`finalize-tasks` could have produced: a WP whose `owned_files` are declared, a lane
branch whose commit lands inside that ownership, and a done transition that supplies the
reviewer identity an approval requires. When the #6715 gate is exercised, it is exercised
against honest evidence rather than being short-circuited by an empty ownership list.

**Why this priority**: without this the 8 reds cannot be cleared without weakening the
gate, which the charter forbids.

**Independent Test**: the fixture's WP01 frontmatter declares `owned_files`, the lane
branch's implementation commit touches a path inside it, and the evidence window
(`planning_commit..lane branch`) shows that change.

**Acceptance Scenarios**:

1. **Given** the fixture repository, **When** `git diff --name-only <planning_commit>..kitty/mission-017-test-feature-lane-a` is read, **Then** at least one changed path matches the fixture WP's `owned_files`.
2. **Given** the same fixture, **When** `move-task WP01 --to for_review` runs, **Then** the evidence gate passes and the assertion that the node actually makes (uncommitted work, event readback, kitty-specs contamination, auto-commit) is what decides the outcome.
3. **Given** a review-ward move with **no** owned change in its window, **When** it runs, **Then** the gate still refuses with `IMPLEMENTATION_MISSING` (the existing #6715 integration tests stay green and unchanged).

### User Story 3 - The done-override test names its approver (Priority: P2)

The `--done-override-reason` node tests a done transition without `--force`. Once the
evidence gate passes, the #6715 independence gate correctly refuses a move into `done`
that records the placeholder `user` as approver. The node supplies a reviewer identity,
as an operator would, so it still proves what it is named for (an unmerged branch may be
marked done with an explicit override reason).

**Independent Test**: the node passes with `--agent reviewer-renata` and would fail with
`REVIEW_NOT_INDEPENDENT` without it — the identity requirement is exercised, not bypassed.

### Edge Cases

- `test_move_to_for_review_still_validates` and `test_move_to_done_with_staged_but_uncommitted_fails` deliberately leave work **uncommitted**; the fixture's owned commit is on the lane branch, so the evidence gate passes and the uncommitted-work guard is still the one that fires.
- `test_for_review_auto_commits_uncommitted_deliverables` relies on the deferred readiness check: the evidence gate runs only after the auto-commit. The fixture's owned commit must be in the window *before* the auto-commit too, so the node still proves the recovery path rather than the gate.
- `test_move_for_review_blocks_when_lane_branch_has_kitty_specs_commits` commits a planning artifact on the lane; evidence passes on the fixture's owned commit, so the kitty-specs contamination gate (the node's subject) is still what refuses.
- `test_move_for_review_from_worktree_keeps_commit_history_unchanged` asserts the lane head message stays `Add implementation`; the fixture keeps that commit message.
- The module must stay green when run alone and with the rest of `tests/tasks`, with or without `-p no:randomly`.
- `tests/tasks` is out of matrix: no per-PR job runs it, so the mission's proof is a local run of the file plus the nightly shard that owns it (see `## Deferred` if a nightly slot cannot be observed).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Fixture WP declares owned_files | As a maintainer, I want the `git_repo_with_worktree` fixture's WP01 to declare `owned_files` that cover the lane deliverable, so that the #6715 evidence gate can match a committed change instead of refusing on an empty ownership list. | High | Open | [ratchet] | no — the 8 nodes stay refused by `IMPLEMENTATION_MISSING` without it |
| FR-002 | Lane commits inside the ownership | As a maintainer, I want the fixture's lane branch to commit its implementation inside the declared `owned_files` (and inside the lane's `src/**` write scope), so that the evidence window `planning_commit..lane-branch` shows a real owned change. | High | Open | [ratchet] | no — an out-of-scope deliverable is what makes the gate refuse |
| FR-003 | Done-override node names its approver | As a maintainer, I want `test_move_to_done_with_override_reason_succeeds_when_unmerged` to pass a real `--agent` identity, so that #6715's independence gate is satisfied honestly and the node still proves the done-override path. | High | Open | [ratchet] | no — the node fails `REVIEW_NOT_INDEPENDENT` without it |
| FR-004 | Gate and node set unchanged | As a reviewer, I want the module's 15 existing nodes, their names, markers and assertions to stay as they are (aside from the fixture and the one invocation's flag), and no change under `src/`, so that the fix cannot be a weakened gate or a skipped test. | High | Open | [ratchet] | no — `git diff` on `src/` is empty and the node count stays 15 |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|--------|--------|
| NFR-001 | Full module green | `uv run --frozen pytest -q -p no:randomly -n0 tests/tasks/test_move_task_git_validation_unit.py` reports 15 passed and 0 failed on the branch; the same command on the planning base reports the 8 named failures. | Reliability | High | Open |
| NFR-002 | Lint, format and types clean | The changed test file passes `ruff check`, `ruff format --check --force-exclude` and mypy with zero new issues and no new suppressions. | Quality | High | Open |
| NFR-003 | No cross-test dependency | The module passes alone, in file order, and under random ordering; the fixture stays self-contained in `tmp_path` with no shared state. | Reliability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|--------|--------|
| C-001 | No gate weakening | No skip, xfail, deselect, retry, marker change, assertion removal or `--force` added to reach green; the evidence gate's refusal text and ordering are untouched. | Process | High | Open |
| C-002 | No production change | Zero lines change under `src/`; the deliverable is the fixture, one invocation's flags, a changelog fragment and the Mission's own artifacts. | Scope | High | Open |
| C-003 | Smallest viable diff | Per `change-apply-smallest-viable-diff`: one test module, one internal changelog fragment, no unrelated reformatting or fixture rewrites. | Technical | Medium | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the branch, `tests/tasks/test_move_task_git_validation_unit.py` reports 15 passed, 0 failed (on the planning base: 8 failed, 7 passed) — [ratchet] · no-op passable: no
- **SC-002**: The fixture's WP01 declares `owned_files` and the lane branch's `Add implementation` commit touches a path matching it, so the evidence window shows an owned change — [ratchet] · no-op passable: no
- **SC-003**: `git diff` against the planning base shows no change under `src/`, and the module's collected node count stays 15 — [ratchet] · no-op passable: no
- **SC-004**: The #6715 gate's refusal for a WP with no owned change is still covered and passing (`tests/integration/test_6715_*`, unchanged) — [ratchet] · no-op passable: no

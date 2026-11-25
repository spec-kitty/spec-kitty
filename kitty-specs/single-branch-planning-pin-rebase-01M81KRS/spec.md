# Mission Specification: single_branch planning pin across a rebase

**Mission**: `single-branch-planning-pin-rebase-01M81KRS`
**Issues**: #7793, #7297 (items 1-6)
**Created**: 2026-11-22
**Status**: Draft

## Purpose

An operator who rebases a `single_branch` Mission's branch must keep the work already committed.
Today the documented remedy (`finalize-tasks --refresh-planning-commit --allow-orphaned`) moves the
recorded planning commit (`planning_commit_sha`, "the pin") to the branch tip. The Mission's
implementation evidence window, `pin..mission_branch`, is then empty, and `move-task --to for_review`
refuses `SINGLE_BRANCH_IMPLEMENTATION_MISSING` with nothing explaining why (#7793). The same pin
authority has related gaps (#7297): a later plain finalize replaces a derived pin, derivation walks a
branch other than the one the window reads, the warning and the refusal disagree, the pin can be too
early or too late, and `doctor` leaves a `None` pin or a fallback without a next step.

Reader: a Spec Kitty operator or agent running a `single_branch` Mission, and the core maintainers
who own the pin authority (`mission_finalize_planning_pin.py`, `lanes/planning_base.py`).

## Domain Language

| Term | Meaning | Do not confuse with |
|------|---------|---------------------|
| Pin | `lanes.json` `planning_commit_sha`: the base of the implementation evidence window | the lane-tip recorder refs |
| Evidence window | `pin..mission_branch` for `single_branch` (`lanes/single_branch_landing.single_branch_evidence_window`) | the review range |
| Pin branch line | the branch the pin is captured from, refreshed against and derived on | the merge target |
| Orphaned pin | pin object present, not an ancestor of the pin branch line tip (a rebase) | a foreign pin (object absent) |
| Patch-id match | the commit on the rebased branch whose `git patch-id` equals the orphaned pin's | a SHA match |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Rebase keeps committed work reviewable (Priority: P1)

A `single_branch` Mission. WP01 is implemented and committed, moved to `for_review`, rejected to
`planned`. The operator rebases the Mission branch onto `main`. `implement` refuses with the orphaned
pin remedy. The operator runs `finalize-tasks --refresh-planning-commit --allow-orphaned`.

**Why this priority**: it is the reported defect (#7793), observed on PR #7778; every rebase of a
`single_branch` Mission under review hits it.

**Independent Test**: the scenario above through the real CLI; `move-task WP01 --to for_review` is
accepted afterwards.

**Acceptance Scenarios**:

1. **Given** the rebased Mission above, **When** the operator re-pins with `--allow-orphaned`, **Then**
   the pin moves to the rebased copy of the recorded planning commit (same patch-id), the output names
   the match, and `move-task WP01 --to for_review` succeeds.
2. **Given** a rebase that dropped or rewrote the planning commit (no patch-id match on the branch),
   **When** the operator re-pins, **Then** finalize refuses with a named error code before writing,
   says the evidence window would lose the committed work, and leaves `lanes.json` unchanged.
3. **Given** a candidate pin that would leave the window without the Mission's committed owned-file
   changes, **When** any re-pin computes it, **Then** it refuses instead of writing it.

### User Story 2 - A derived pin survives a later plain finalize (Priority: P1)

A Mission whose `lanes.json` predates the pin gets one derived on its first plain finalize (#7210).
A second plain finalize must keep it (#7297 item 1).

**Independent Test**: finalize twice with real implementation merged; the second run reports the
derived pin preserved and the evidence gate still passes.

**Acceptance Scenarios**:

1. **Given** a derived pin, **When** a later plain finalize runs and planning files changed since,
   **Then** the pin stays and the run reports it as kept (not `refreshed`).
2. **Given** a derived pin, **When** the operator explicitly runs `--refresh-planning-commit`,
   **Then** the explicit refresh rules still apply (the freeze binds only the automatic path).

### User Story 3 - single_branch has a working route on a minted branch (Priority: P2)

A `single_branch` Mission whose branch `kitty/mission-…` was minted at create (default topology, or
explicit `single_branch` on a protected target) records and maintains its pin on that branch line,
the one the evidence window reads (#7297 item 2).

**Independent Test**: create such a Mission, finalize, and inspect the pin: it is a commit on the
mission branch; `--refresh-planning-commit` succeeds instead of refusing
`PLANNING_REFRESH_FAIL_CLOSED`; a rebase onto a newer `main` keeps `main`'s new commits out of the
evidence window.

**Acceptance Scenarios**:

1. **Given** a minted-branch `single_branch` Mission, **When** finalize captures the pin, **Then** it
   is the mission branch tip, not the target-branch tip.
2. **Given** that Mission, **When** derivation runs, **Then** it walks the mission branch.
3. **Given** that Mission rebased onto a newer `main`, **When** the evidence window is read, **Then**
   it contains no commit that only `main` carried.

### User Story 4 - Messages agree and name a next step (Priority: P2)

The finalize warning, the `move-task` refusal and `doctor mission-state --fix` describe the same
state the same way and each names a command or step that works (#7297 items 3 and 6).

**Acceptance Scenarios**:

1. **Given** no recorded pin, a resolvable tip and no derivable base, **When** finalize warns,
   **Then** the reason code and text say "no pin and none derivable" (not "tip uncapturable"), and
   name the next step.
2. **Given** a `doctor mission-state --fix` rebuild with no derivable base and no capturable tip,
   **When** the pin stays `None`, **Then** doctor warns and names the next step; the target-tip
   fallback warning also names one.
3. **Given** a `single_branch` evidence refusal, **When** its remedy is printed, **Then** it names
   the re-pin command that now works, not the retired "run finalize-tasks" advice.

### Edge Cases

- Tasks removed and later re-added: the derived pin anchors on the re-add, not the first add (#7297 item 4).
- Task files first committed under a non-`WP*` name and renamed later: the derived pin anchors on the
  first task file, not the rename (#7297 item 5).
- The orphaned pin matches more than one commit by patch-id: refuse (ambiguous), never guess.
- Lane-based (`lanes`, `lanes_with_coord`) Missions: behaviour unchanged; the patch-id rule applies to
  their `--allow-orphaned` re-pin only where it is the same authority.
- A pin already recorded as the target tip on a minted Mission (existing Missions): never silently rewritten.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Re-pin follows the planning commit by patch-id | As an operator, I want `--refresh-planning-commit --allow-orphaned` to re-point an orphaned pin to the commit on the pin branch line with the same patch-id, so that committed work stays inside the evidence window after a rebase. | High | Open | [build] | no — the #7793 reproduction refuses today |
| FR-002 | No match refuses with a named code | As an operator, I want a re-pin that finds no (or more than one) patch-id match to refuse with a named error code before writing, so that the pin never lands on a guess. | High | Open | [build] | no — today it re-pins to the tip |
| FR-003 | Never empty the window | As an operator, I want any re-pin whose candidate would drop the Mission's committed owned-file changes from the evidence window to refuse, so that the tool never strands committed work. | High | Open | [build] | no — paired with the FR-001 positive control on the same fixture |
| FR-004 | Derived pin frozen against plain finalize | As an operator, I want a derived pin preserved by a later plain finalize, so that a passing evidence gate does not turn into `IMPLEMENTATION_MISSING`. | High | Open | [build] | no — today run 2 reports `refreshed` |
| FR-005 | single_branch pin branch line is the mission branch | As an operator of a minted-branch `single_branch` Mission, I want capture, refresh and derivation to use the mission branch, so that the pin sits on the line the evidence window reads and refresh does not dead-end. | High | Open | [build] | no — today the pin is the target tip and refresh refuses |
| FR-006 | Finalize warning and reason agree | As an operator, I want the "no pin, none derivable" case reported with its own reason and a next step, so that the warning does not claim an uncapturable tip it prints. | Medium | Open | [build] | no — asserts the new reason code |
| FR-007 | Refusal remedies are live | As an operator, I want the `single_branch` evidence refusals to name the re-pin route that works, so that I do not run advice that cannot help. | Medium | Open | [build] | no — asserts the new remedy text |
| FR-008 | Derivation anchors on the latest re-add | As a maintainer, I want derivation to anchor on the commit after which the Mission's task files last appeared, so that a remove-and-re-add history does not widen the window. | Medium | Open | [build] | no — a re-add fixture |
| FR-009 | Derivation follows a rename into WP files | As a maintainer, I want derivation to anchor on the first task file of the Mission even when it was renamed to `WP*` later, so that real work is not refused. | Medium | Open | [build] | no — a rename fixture |
| FR-010 | doctor names the gaps | As an operator, I want `doctor mission-state --fix` to warn when the rebuilt pin stays `None` and to name a next step in both pin warnings, so that no rebuild is silent. | Medium | Open | [build] | no — asserts the warning text |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded git cost | A re-pin reads at most one `git patch-id` per commit in `merge-base(pin, tip)..tip` on the pin branch line, and finalize stays under 2 s on a 200-commit Mission branch. | Performance | Medium | Open |
| NFR-002 | Fail closed | Every git probe failure on the new paths refuses (re-pin) or keeps the recorded pin with a warning (automatic path); none writes a guessed pin. | Reliability | High | Open |
| NFR-003 | Quality gates | ruff, `ruff format --check --force-exclude` and mypy report zero issues on changed files, with no new suppressions; diff coverage at least 90 %. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | One authority | Reuse `consolidation.git_probes.patch_id_of` and `lanes.planning_base`; add no second patch-id or derivation helper. | Technical | High | Open |
| C-002 | Recorded pins are not rewritten silently | No path rewrites a recorded pin except an explicit operator refresh or the existing advance rule; existing Missions keep their pins. | Technical | High | Open |
| C-003 | Lane topologies unchanged | `lanes` and `lanes_with_coord` capture, refresh and evidence behaviour stays byte-identical, except for the derived-pin freeze (FR-004, topology-neutral by the operator ruling) and the derivation anchor (FR-008, FR-009). | Technical | High | Open |
| C-004 | ADR amendment | Amend ADR `docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md` with the rules and residuals. | Governance | High | Open |
| C-005 | Concurrent Missions | `tasks_move_task.py` and `single_branch_landing.py` overlap #7809; `mission_finalize.py` overlaps Slice 1a; `doctor` overlaps Slice 10. Keep edits local; whichever lands second rebases. | Process | Medium | Open |

### Key Entities

- **LanesManifest** (`lanes.json`): carries `planning_commit_sha`, `mission_branch`, `target_branch`.
- **PlanningCommitResolution**: one finalize run's pin decision (`action`, `sha`, `previous_sha`, `branch_tip`, `pin_class`, `refusal_reason`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The #7793 reproduction (commit, reject, rebase, re-pin, `move-task --to for_review`) exits 0 through the real CLI. [build] no-op passable: no
- **SC-002**: A no-match re-pin exits non-zero with a named code and leaves `lanes.json` byte-identical. [build] no-op passable: no
- **SC-003**: Three consecutive plain finalizes on a derived-pin Mission keep the same pin. [build] no-op passable: no
- **SC-004**: On a minted-branch `single_branch` Mission rebased onto a newer `main`, the evidence window lists no `main`-only commit. [build] no-op passable: no

## Assumptions

- The operator confirmed the FR-005 extension on 2026-11-23 (capture and refresh, not only derivation, follow the
  mission branch).
- Patch-id is computed with the existing `patch_id_of` (stable patch-id), so whitespace-only rebase
  conflicts that change the diff do not match; that case refuses (FR-002).

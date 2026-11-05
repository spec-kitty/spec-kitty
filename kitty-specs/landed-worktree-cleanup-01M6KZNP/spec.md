# Mission Specification: Landed worktree cleanup and upgrade worktree scope

**Mission Branch**: `issue-7173-landed-worktree-cleanup`
**Created**: 2026-11-04
**Status**: Draft
**Input**: Issue #7173, "Landed worktrees and branches are never cleaned up, and upgrade commits into all of them", plus the operator rulings of 2026-11-04 (Decision Moments `specify.*`).

## Intent Summary (confirmed 2026-11-04)

- **Actor:** a maintainer or operator of a clone that has accumulated landing worktrees.
- **Trigger:** a pull request has merged, often after the session that created its worktree ended; later the operator runs `spec-kitty doctor workspaces` or `spec-kitty upgrade`.
- **Outcome:** the operator sees which worktrees have landed and can remove them, and their local branches, with one command that refuses anything it cannot prove landed. `upgrade` no longer writes or commits into non-Mission worktrees unless the operator names them.
- **Invariant:** nothing removes work that cannot be proven landed. A dirty worktree, a worktree with a process running inside it, a worktree whose tip carries content not on the primary branch, and a Mission-owned worktree are never removed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See which worktrees have landed (Priority: P1)

An operator runs `spec-kitty doctor workspaces` in a clone with dozens of worktrees. Besides the existing husk report, the command lists every registered worktree with a verdict: landed, not landed (with the reason), Mission-owned (report only) or unproven (with the reason the proof could not run). For each landed worktree it prints the command that would remove it.

**Why this priority**: Without a read surface the operator has to work out by hand which worktrees are safe; that is the defect the issue records.

**Independent Test**: Build a repository with a landed, a dirty and an unpushed worktree; run the report; check each verdict, that nothing changed on disk, and that the exit code is the husk exit code.

**Acceptance Scenarios**:

1. **Given** a worktree whose branch was rebase-merged into the primary branch (its SHAs rewritten), **When** the operator runs `doctor workspaces`, **Then** it is listed as landed with its branch and tip SHA.
2. **Given** a worktree with an uncommitted change, **When** the report runs, **Then** it is listed as not landed with reason "uncommitted changes".
3. **Given** a worktree whose branch carries a commit the primary branch does not contain, **When** the report runs, **Then** it is listed as not landed with reason "content not on <primary>".
4. **Given** a Mission lane or coordination worktree, **When** the report runs, **Then** it is listed as Mission-owned and never as a removal candidate.
5. **Given** no husks and only landed worktrees, **When** the report runs, **Then** the exit code is 0 (landed worktrees are informational).

---

### User Story 2 - Prune landed worktrees safely (Priority: P1)

The operator runs `spec-kitty doctor workspaces --prune`. Each worktree proven landed is removed together with its local branch; every other worktree is left untouched and reported with its reason. For each removal the command prints the branch, the SHA and the command that recreates the branch.

**Why this priority**: Reporting alone leaves the pile in place; the issue's acceptance asks for removal without the maintainer working out which ones are safe.

**Independent Test**: Same fixture as story 1 plus a worktree with a running process; run `--prune`; only the landed, idle, clean worktree and its branch are gone, and the recreate command restores the branch at the printed SHA.

**Acceptance Scenarios**:

1. **Given** a landed, clean, idle worktree, **When** `--prune` runs, **Then** the worktree and its local branch are removed and `git branch <b> <sha>` is printed.
2. **Given** a landed worktree with an untracked file, **When** `--prune` runs, **Then** it is kept and reported.
3. **Given** a landed worktree in which a process has its working directory, **When** `--prune` runs, **Then** it is kept and reported.
4. **Given** a worktree whose tip carries an unpushed commit with content not on the primary branch, **When** `--prune` runs, **Then** it is kept.
5. **Given** a platform where the running-process proof cannot run, **When** `--prune` runs, **Then** no worktree is removed and each landed one is reported as unproven with the manual command.
6. **Given** `--fix` and `--prune` together, **When** the command runs, **Then** husks are removed under the existing `--fix` contract and landed worktrees under the `--prune` contract.

---

### User Story 3 - Upgrade leaves non-Mission worktrees alone (Priority: P1)

An operator runs `spec-kitty upgrade` in a clone with landing worktrees for open PRs. The preview and the normal output list every worktree under `.worktrees/` with what will happen to it. Non-Mission worktrees are skipped unless named with `--include-worktree <path>` (repeatable) or selected all at once with `--all-worktrees`.

**Why this priority**: Today a plain `upgrade` commits onto open PR branches; this is the hazard the issue records.

**Independent Test**: Repository with two non-Mission worktrees and one Mission worktree; run `upgrade --yes` with no flag, with `--include-worktree` naming one, and with `--all-worktrees`; inspect each branch's log and the printed dispositions.

**Acceptance Scenarios**:

1. **Given** non-Mission worktrees and no opt-in flag, **When** `upgrade --yes` runs, **Then** no file in them changes, no commit lands on their branches, and each is listed as skipped with the flag that would include it.
2. **Given** `--include-worktree .worktrees/a`, **When** `upgrade --yes` runs, **Then** only `a` is upgraded and committed; the others are listed as skipped.
3. **Given** `--all-worktrees`, **When** `upgrade --yes` runs, **Then** every non-Mission worktree is upgraded and committed, as before this Mission.
4. **Given** `upgrade --dry-run`, **When** it runs, **Then** the normal (non-JSON) preview lists every worktree with its disposition.
5. **Given** `--include-worktree` naming a path that is not a worktree under `.worktrees/`, **When** `upgrade` runs, **Then** it refuses before any write and names the path.

---

### User Story 4 - The landing runbook owns removal (Priority: P2)

A maintainer following `docs/development/how-to/pr-landing.md` finds a closing step that runs the report after the merge and the prune once the PR has merged.

**Why this priority**: Documentation alone does not solve the merge-outlives-the-session problem, but it gives the step an owner.

**Independent Test**: The runbook names `doctor workspaces` and `--prune` in a step after the hand-off.

**Acceptance Scenarios**:

1. **Given** the runbook, **When** a maintainer reaches the end of a landing pass, **Then** a step tells them how to find and remove landed worktrees.

### Edge Cases

- A detached worktree inside `.worktrees/` at a commit already on the primary branch: landed; the worktree is removed and no branch is deleted; the recreate hint is `git worktree add --detach <path> <sha>`, and a tip no local branch or tag reaches is kept at `refs/spec-kitty/discarded/detached/<sha>`. A detached worktree outside `.worktrees/` (a scratch checkout of another spec-kitty command) is excluded. (amended at closeout, #7173 squad)
- No `origin` remote, or no `origin/<primary>` ref: every worktree is unproven; nothing is removed.
- git older than 2.38: a tip that is an ancestor of `origin/<primary>` is still proven landed; any other tip is unproven.
- A stale `origin/<primary>` (not fetched): mostly under-reports, but it can vouch for content since rewritten off the remote's primary branch; so `--prune` keeps every removed tip that no local branch or tag reaches under `refs/spec-kitty/discarded/`. (amended at closeout, #7173 squad)
- The repository root checkout and the worktree the command runs from are never candidates.
- A worktree whose directory is missing (prunable in git terms) is reported, not removed by this command.
- A locked worktree (`git worktree lock`) is kept and reported.
- A branch checked out in a second worktree is not deleted.
- A squash-merged branch whose content is on the primary branch is proven landed by the merge-tree no-op proof.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Landed-worktree report | As an operator, I want `doctor workspaces` to list every registered worktree with a landed / not landed / Mission-owned / unproven verdict and reason so that I can see which are safe without working it out by hand. | High | Open | [build] | no |
| FR-002 | Offline landed proof | As an operator, I want "landed" proven offline against the local `origin/<primary>` ref (ancestor, or a merge-tree no-op for rebase and squash merges) so that no network or hosted lookup is needed. A stale ref can also vouch for content later rewritten off the primary branch, so every pruned tip that no local branch or tag reaches is kept under `refs/spec-kitty/discarded/` (amended at closeout, #7173 squad). | High | Open | [build] | no — rebase-merged positive control on the same fixture as the unpushed-commit negative |
| FR-003 | Prune proven-landed worktrees | As an operator, I want `doctor workspaces --prune` to remove a worktree and its local branch only when it is landed, clean (tracked and untracked), idle, unlocked and not Mission-owned so that nothing that cannot be proven landed is removed. | High | Open | [build] | no — landed-idle positive control beside each refusal case |
| FR-004 | Recreate hint | As an operator, I want every removal to print the branch, the SHA and the command that recreates it so that anything removed can be restored. | High | Open | [build] | no |
| FR-005 | Running-process proof | As an operator, I want a worktree with a process whose working directory is inside it never removed, and the proof's absence to mean report-only so that a live session is never pulled from under a process. | High | Open | [build] | no |
| FR-006 | `--fix` contract unchanged | As an operator, I want `--fix` to keep removing only unregistered husks so that its existing promise holds. | Medium | Open | [ratchet] | yes — paired with FR-003 on the same fixture |
| FR-007 | Upgrade skips non-Mission worktrees by default | As an operator, I want `upgrade` to leave non-Mission worktrees untouched unless named so that open PR branches never receive upgrade commits. | High | Open | [build] | no |
| FR-008 | Upgrade opt-in flags | As an operator, I want `--include-worktree <path>` (repeatable) and `--all-worktrees` to opt worktrees in, with an unknown path refused before any write, so that I can still upgrade the worktrees I choose. | High | Open | [build] | no |
| FR-009 | Upgrade names every worktree | As an operator, I want the normal preview and output, not only `--plan-json`, to list every worktree with its disposition (Mission, skipped and why, upgraded and committed) so that I know where upgrade writes before it does. | High | Open | [build] | no |
| FR-010 | Plan JSON reflects the policy | As an automation author, I want `--plan-json` to carry the per-worktree disposition and the opt-in selection so that machine readers see the same policy. | Medium | Open | [build] | no |
| FR-011 | Runbook removal step | As a maintainer, I want `pr-landing.md` to own a removal step using the report and `--prune` so that a landing pass ends with cleanup. | Medium | Open | [build] | no |
| FR-012 | Machine-readable report | As an automation author, I want `doctor workspaces --json` to include the per-worktree verdicts and any removals so that scripts can act on them. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No unproven deletion | 0 removals in the test matrix for each of: uncommitted change, untracked file, unpushed commit, running process, locked worktree, Mission worktree, missing `origin/<primary>`, unprovable process check. | Safety | High | Open |
| NFR-002 | Offline | 0 network contacts by `doctor workspaces` (with or without `--prune`); the remote-contact owner gate stays green with an empty allowlist. | Security | High | Open |
| NFR-003 | Report cost | The report over 50 worktrees completes in under 10 s on a developer machine (one ancestor check, at most one merge-tree run, one status probe per worktree). | Performance | Medium | Open |
| NFR-004 | Code quality | Touched code passes ruff, ruff format and mypy with zero new suppressions; every function stays at complexity ≤ 15; diff coverage ≥ 90 %. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No hosted surface | No GitHub lookup, no fetch and no hosted client in product code (CLAUDE.md, Team Kitty). | Technical | High | Open |
| C-002 | Never force | Removal never uses `git worktree remove --force`; a branch is deleted with `-D` only after the landed proof. | Technical | High | Open |
| C-003 | Reuse existing primitives | The landed proof reuses `lanes/lane_tip.is_absorbed`'s ancestor and merge-tree legs; Mission ownership reuses the branch-naming authority already used by `upgrade` (#5457). | Technical | High | Open |
| C-004 | Mission lifecycle untouched | Mission lane and coordination worktrees remain owned by `consolidate` and the lane-tip guards (`DESTROYED_LANE`, `LANE_WORK_TIP_UNKNOWN`); this Mission only reports them. | Technical | High | Open |
| C-005 | Packs edited upstream | The landing skill and procedure change is authored in `spec-kitty-open-packs` and reaches core only through a pin bump; core's `packs/` is never edited. | Process | High | Open |

### Key Entities

- **Worktree verdict**: one registered worktree's path, branch (or detached), tip SHA, verdict (landed / not landed / Mission-owned / unproven) and reason.
- **Worktree disposition (upgrade)**: one `.worktrees/` entry's path, branch and what upgrade does with it (skipped as Mission, skipped not opted in, upgraded and committed).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a fixture reproducing the issue (one rebase-merged, one open with an unpushed commit, one dirty, one with a running process, one Mission lane), one `--prune` run removes exactly the rebase-merged worktree and its branch and keeps the other four. — [build] · no-op passable: no
- **SC-002**: A plain `upgrade --yes` on that fixture produces 0 new commits on any non-Mission branch. — [build] · no-op passable: no
- **SC-003**: Every removal can be undone with the printed command, restoring the branch at the same SHA in 100 % of test cases. — [build] · no-op passable: no
- **SC-004**: The normal `upgrade --dry-run` output names 100 % of `.worktrees/` entries with a disposition. — [build] · no-op passable: no

## Assumptions

- `<primary>` is the repository's primary branch as resolved by the existing primary-branch helper; the remote is `origin`.
- With `--all-worktrees`, upgrade behaves as it does today for non-Mission worktrees (writes and commits), now with each one named.
- The post-consolidate report (option 3 in the issue) is deferred to a follow-up issue.
- The open-packs skill change ships as its own PR; the core pin bump follows once that PR merges.

## Related

- Follow-up: #3970 (machine-readable cleanup postcondition report), #4041 (archived Mission keeps its coordination worktree), #5747 and #5712 (upgrade worktree scope), #5457 (integrating worktrees skipped).

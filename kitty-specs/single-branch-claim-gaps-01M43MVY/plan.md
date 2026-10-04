# Implementation Plan: single_branch claim gaps: stale occupant and claim base

**Branch**: `issue-5680-single-branch-claim-gaps` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/single-branch-claim-gaps-01M43MVY/spec.md`

Reader: the implementer and reviewer of WP01.

## Summary

The single_branch occupancy scan (`lanes/checkout_occupancy.py::in_progress_wps_in_write_checkout`)
reads every single_branch mission's status from whatever branch the repository
root checkout has. It treats an `in_progress` WP found there as occupying the
checkout, even when the branch is not that mission's write branch, so the
snapshot is only a copy. This blocks every claim in this repository on
`reconcile-flake-family-01M34HR7` WP04 (#5680).

Approach:
- The scan counts an occupant only when the occupant mission's write branch is
  the branch the checkout is on.
- The occupied refusal gains the occupant's write branch and a runnable remedy.

#5663 is already fixed by #5659 (see [research/code-grounding.md](research/code-grounding.md) §1).
It needs no code, only a cited pin.

## Decision: the "no longer live" predicate (DM-01M43MY9BKY2BBJQN4D2GVM436)

**Chosen:** an occupant counts only if BOTH hold:
1. `not status.is_mission_completed(feature_dir)`. This is the existing filter
   and stays as is: a merge marker, or every WP terminal.
2. `single_branch_write_ref(stored_topology, meta["mission_branch"], meta["target_branch"]) == <current branch of the write checkout>`.

If the write branch cannot be determined (no `target_branch` in `meta.json`, or
the checkout is on a detached HEAD), the occupant counts. That fails closed and
keeps today's behaviour.

**Authority:**
- `mission_runtime.single_branch_write_ref` (`src/mission_runtime/resolution.py`)
  is the ONE write-branch rule (#5100 FR-007/012, IC-05). Its docstring names
  `meta.json` as the only authority. The scan already loaded that `meta.json`,
  through `read_topology`.
- The status-surface rule in CLAUDE.md ("Status source of truth: the resolved
  status surface ... not the open worktree") makes the write branch the
  authoritative status surface of a single_branch mission. A copy on any other
  branch is a snapshot.

**Rejected alternatives:**

| Predicate | Why rejected |
|---|---|
| `merged_at` / `is_mission_merged` only | Already covered by `is_mission_completed`. The real occupant has no marker: it was squash-merged by PR, not consolidated. |
| `mission_number` assigned | Display-only by canon ("never used for lookup"). It is also `null` here. |
| Accept commit / `acceptance-matrix.json` | Not a status authority. The real occupant's matrix is `pending`. |
| Lifecycle `stale`/`abandoned` (14/30 days) | Wall-clock heuristic. A claim refusal must not change with the date, and the real occupant is 12 days old. |
| Target branch ancestry / branch existence | Needs extra git probes per mission. It is wrong when the target branch was deleted after merge, and a live branched-off branch also contains the target. |
| Remedy-only (no predicate change) | Leaves every claim in this repository blocked until someone writes into a finished mission's status, which C-002 forbids for this mission. |

**Why branch-scoping does not weaken the guard for live missions (C-001):**
- Two live missions on the same write branch still refuse.
- Two missions on different write branches can never have commits interleaved
  in one branch: the claimant's wrong-branch refusal pins the checkout to the
  claimant's write branch, and the dirty refusal and git itself block switching
  away from uncommitted work.
- The scan was already one-directional. On branch X it can only see missions
  whose status exists on X. After this change it consistently counts only
  missions whose live surface IS X.

**Residual (accepted, documented):** a finished mission whose write branch is
the current branch, and which is neither consolidated nor all-terminal, still
refuses. The improved remedy (FR-005) covers it.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: typer, ruamel/json meta reads (existing), `mission_runtime`, `specify_cli.status`
**Storage**: files: `meta.json`, `status.events.jsonl`, `lanes.json`
**Testing**: pytest. Unit: `tests/lanes/test_checkout_occupancy.py`. CLI: `tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py`. E2E agent loop: `tests/integration/test_single_branch_write_checkout_e2e.py`.
**Target Platform**: CLI (Linux/macOS/Windows)
**Project Type**: single
**Performance Goals**: NFR-001. No new subprocess per mission; one `get_current_branch` per scan.
**Constraints**: C-001..C-005 (spec)
**Scale/Scope**: 2 source files, 3 test files, 3 docs

## Charter Check

- **Single canonical authority:** reuse `single_branch_write_ref`, `read_topology`, `is_mission_completed` and `get_current_branch`. No second rule.
- **Red-first (SO-4, ADR 2026-07-17-1):** issue-pinned `@pytest.mark.regression` repro, red through `spec-kitty implement` and `spec-kitty agent action implement` before the fix. Afterwards the repros move into their functional suites without the marker.
- **Tidy-first (SO-2):** the scan's per-mission filter grows by one condition. Extract the per-mission candidate check into a private helper first, as a behaviour-preserving enabler commit, to keep complexity at 15 or below.
- **No new gates (SO-5 / C-004):** none added.
- **NO_FULL_HEAVY_SUITES_IN_MISSION:** targeted suites and named gate files only.
- **Pack tiers:** no doctrine change.

## Project Structure

### Documentation (this mission)

```
kitty-specs/single-branch-claim-gaps-01M43MVY/
├── spec.md
├── plan.md
├── research/code-grounding.md
├── traces/{tooling-friction,approach,design-decisions}.md
├── tasks.md + tasks/WP01-*.md
└── decisions/
```

### Source Code (repository root)

```
src/specify_cli/lanes/checkout_occupancy.py     # predicate (write-branch scoping)
src/specify_cli/lanes/implement_support.py      # occupied refusal message + remedy
tests/lanes/test_checkout_occupancy.py           # unit: branch scoping, fail-closed, mint
tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py  # spec-kitty implement
tests/integration/test_single_branch_write_checkout_e2e.py              # agent action implement
docs/changelog/CHANGELOG.md, CLAUDE.md, docs/context/topology.md
```

**Structure Decision**: single project. All changes stay inside the existing
`lanes/` seam.

## Complexity Tracking

None.

## Implementation Concern Map

### IC-01 — Branch-scoped occupancy

- **Purpose**: stop a status copy on a non-write branch from occupying the write checkout.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, NFR-001, C-001, C-003
- **Affected surfaces**: `src/specify_cli/lanes/checkout_occupancy.py`, `tests/lanes/test_checkout_occupancy.py`, both claim-verb test suites
- **Sequencing/depends-on**: none
- **Risks**:
  - The repro fixture must make the occupant's write branch really differ from the claimant's.
  - The control must keep both missions on one branch.
  - Existing unit tests sit on `main` with target `main`, so they stay valid.

### IC-02 — Runnable remedy

- **Purpose**: a genuine refusal names the occupant's mission, WP and write branch, plus a `move-task … --to blocked` command.
- **Relevant requirements**: FR-005
- **Affected surfaces**: `src/specify_cli/lanes/implement_support.py` (message only), refusal tests
- **Sequencing/depends-on**: IC-01. After IC-01 every reported occupant writes to the checkout's current branch, which the wrong-branch refusal has already pinned to the claimant's expected branch. The message names that branch, and the scan's return type stays unchanged.
- **Risks**:
  - Keep the phrase `Move <WP> out of in_progress` (asserted by existing tests).
  - Verify that the suggested command actually clears the occupant.

### IC-03 — #5663 evidence, docs and changelog

- **Purpose**: close #5663 with a cited pin, and keep the docs in line with the new scope.
- **Relevant requirements**: FR-006, FR-007
- **Affected surfaces**: `docs/changelog/CHANGELOG.md`, `CLAUDE.md`, `docs/context/topology.md`
- **Sequencing/depends-on**: IC-01, IC-02
- **Risks**: changelog style gate (`scripts.docs.check_changelog_style`).

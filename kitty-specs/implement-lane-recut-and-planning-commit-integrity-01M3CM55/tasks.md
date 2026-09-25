# Tasks: Implement lane-allocation integrity

**Mission**: implement-lane-recut-and-planning-commit-integrity-01M3CM55
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)
**Issues**: #4889 (P0), #4905 (P1)

## Overview

Three work packages. WP01 (#4889) and WP02 (#4905) are write-scope-disjoint and run in parallel; WP03 is the cross-cutting integration regression and depends on both.

```
WP01 (#4889 fail-closed detector)  ─┐
                                     ├─→ WP03 (e2e integration regression)
WP02 (#4905 coord-staging partition)─┘
   WP01 ∥ WP02   →   WP03 depends on {WP01, WP02}
```

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first repro: destroyed lane (worktree+branch gone) via CLI `implement` re-cuts empty lane | WP01 | |
| T002 | Red-first repro: same via orchestrator `agent action implement` / `_resolve_start_workspace` | WP01 | [P] |
| T003 | Add fail-closed destroyed-lane pre-flight inside `allocate_lane_worktree` (before FRESH routes) | WP01 | |
| T004 | Key detector on WorkspaceContext + non-terminal status + refs-gone + tip-not-ancestor-of-target | WP01 | |
| T005 | Typed diagnostic (missing branch + recovery ref); leave WorkspaceContext untouched | WP01 | |
| T006 | FR-009 resilience assertion in `_merge_recorded_planning_commit` | WP01 | [P] |
| T007 | Preserve control arms (REUSE / CRASH_RECOVERY / fresh / reachable-tip) — regression pins | WP01 | |
| T010 | Red-first repro: coord `agent action implement WP01` stages `tasks/WP01-*.md` on coord branch | WP02 | |
| T011 | Red-first repro: WP02 claim fails with `PlanningCommitMergeConflictError` | WP02 | [P] |
| T012 | Partition staged paths by artifact kind at `_commit_via_coordination_transaction` sink | WP02 | |
| T013 | Route PRIMARY-kind (`WORK_PACKAGE_TASK`) paths to primary target via `commit_to_primary_target` | WP02 | |
| T014 | Cover all three staging sites (claim/resume-refresh/review-claim) by construction at the sink | WP02 | |
| T015 | Regression: coord tree has zero `tasks/WP*.md` after claim AND after review-claim; `lanes` control | WP02 | |
| T020 | e2e regression on a real coord mission: #4889 fail-closed across REUSE/CRASH_RECOVERY/FRESH + both callers | WP03 | |
| T021 | e2e regression: #4905 WP01→WP02 both start, no conflict, coord clean after review-claim | WP03 | |
| T022 | Interaction proof: #4905 fix + #4889 fresh path coexist (fixing one does not reopen the other) | WP03 | [P] |
| T023 | Confirm repros transition from RED (pre-fix) to GREEN (post-fix); demote transitional repros | WP03 | |

## Work Packages

### WP01 — #4889 fail-closed destroyed-lane detector

**Goal**: `allocate_lane_worktree` must distinguish a never-allocated lane from a destroyed one and fail closed rather than silently re-cut an empty lane. Prompt: [tasks/WP01-destroyed-lane-fail-closed.md](./tasks/WP01-destroyed-lane-fail-closed.md)
**Priority**: P0 (US1) · **Est.**: ~420 lines · 7 subtasks (T001–T007)
**Independent test**: destroyed-lane scenario refuses via both CLI and orchestrator; control arms resume.
**Dependencies**: none.

### WP02 — #4905 coord-staging partition

**Goal**: keep PRIMARY-partition `tasks/WP*.md` off the coordination branch at the shared commit sink, covering all three lifecycle staging sites. Prompt: [tasks/WP02-coord-staging-partition.md](./tasks/WP02-coord-staging-partition.md)
**Priority**: P1 (US2) · **Est.**: ~360 lines · 6 subtasks (T010–T015)
**Independent test**: coord tree carries no WP file after claim + review-claim; WP02 starts with no conflict.
**Dependencies**: none.

### WP03 — cross-cutting integration regression

**Goal**: prove both defects are dead together on a real coord mission across every route/caller. Prompt: [tasks/WP03-integration-regression.md](./tasks/WP03-integration-regression.md)
**Priority**: P1 · **Est.**: ~300 lines · 4 subtasks (T020–T023)
**Independent test**: the e2e suite is RED pre-fix and GREEN with WP01+WP02 present.
**Dependencies**: WP01, WP02.

## MVP scope

WP01 (#4889 P0) is the release-critical slice; WP02 is the P1 folded sibling; WP03 is the integration safety net.

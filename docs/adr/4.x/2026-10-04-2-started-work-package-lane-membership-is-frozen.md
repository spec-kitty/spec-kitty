---
title: 'ADR: a started work package keeps its recorded execution lane on re-finalize'
description: 'Lane computation keeps started work packages on their recorded lane by construction and refuses unsatisfiable amendments with LANE_MEMBERSHIP_FROZEN before any write.'
status: Accepted
date: '2026-10-04'
updated: '2026-10-04'
---

**Status:** Accepted

**Date:** 2026-10-04

**Deciders:** Stijn Dejongh (owner). Design decisions D1 to D8 of Mission `frozen-started-lanes-01M444FM`, taken from its code grounding (2026-10-04).

**Technical Story:** [#5573](https://github.com/spec-kitty/spec-kitty/issues/5573), Mission `frozen-started-lanes-01M444FM`. Earlier recurrences: [#3311](https://github.com/spec-kitty/spec-kitty/issues/3311), [#4945](https://github.com/spec-kitty/spec-kitty/issues/4945).

---

## Context and Problem Statement

Re-running `spec-kitty agent mission finalize-tasks` on a Mission that already has a lane manifest (`lanes.json`) is supported (ADR [3.x `2026-07-29-1`](../3.x/2026-07-29-1-lane-base-recorded-planning-commit.md)): operators amend work packages mid-execution and re-finalize. Each run recomputes execution lanes from ownership overlap and the surface heuristic.

#5573 is the third recurrence of one defect class: a re-finalize changes lane identity under work that has already begun.

- **#3311** — a re-finalize rewrote the recorded planning commit of active lanes.
- **#4945** — lane ids were re-minted positionally, so removing a work package could re-letter a surviving lane onto another work package's branch. terminus-merge-integrity FR-010 fixed this by binding a lane id to its git branch at creation and reading it back on re-finalize.
- **#5573** — the id ↔ branch binding held, but *which lane a started work package belongs to* was still a heuristic output. An amendment that made a planned WP01 overlap an in-progress WP02 merged both into one group, which read back `lane-a`. `finalize-tasks` exited 0 with WP02 moved off `lane-b`, the branch holding its commits; the next `implement WP02` failed with `LANE_WORK_TIP_UNKNOWN`.

A started work package owns commits on its lane branch and its lane work tip (`refs/spec-kitty/lane-tip/<branch>`). Its status transitions also carry a `lane_head` stamp that consolidation's per-work-package attribution (#5046) reads. Moving it to another lane strands that work, rebinds a lane-mate onto a branch carrying foreign commits, and poisons that attribution.

## Decision

The recorded lane membership of started work packages is a **constraint input** to lane computation, honoured by construction. It is not a check applied after the heuristic has decided.

- **"Started" is history-based.** A work package is started when its status history has ever recorded a move into `claimed`, `in_progress`, `for_review`, `in_review`, `approved` or `done` (`specify_cli.lanes.frozen_membership.started_wp_ids`). A later reset to `planned`, or a cancellation, does not unstart it. A move from `planned` straight to `blocked` or `canceled` does not start it.
- **Lane-work-tip fallback.** A prior code lane with no history-started member whose branch has a recorded lane work tip counts as wholly started. The planning lane (`lane-planning`) is never frozen by a tip.
- **Preserve by construction** (`specify_cli.lanes.compute`, which stays pure: no git, no `meta.json`). Started work packages that shared a recorded lane are kept in one group (collapse rule `frozen_lane_membership`). A group holding started work packages takes their recorded lane id before any overlap read-back. An unpinned group that shares at least one member with an unused prior lane reads back the one it shares the most members with; a tie goes to the lowest prior lane id. A group that shares no member with any unused prior lane mints the next free id, skipping every lane id that held started work.
- **Refuse only what cannot be satisfied**, with one code, `LANE_MEMBERSHIP_FROZEN` (`LaneMembershipFrozenError`), and one `reason` per case:
  - `started_lanes_collapsed`: one computed group holds started work packages recorded in two or more lanes;
  - `started_wp_removed`: a started work package is missing from the plan and the cancellation projection did not retire it;
  - `started_wp_kind_changed`: a started work package's `execution_mode` now puts it on the other side of `lane-planning`;
  - `status_unreadable`: a lane manifest exists, but the status surface cannot be resolved, its directory does not exist and is not an unmaterialized coordination worktree whose branch can be read locally, or its log cannot be read.
- **Refuse before any write.** finalize runs the check as a read-only preflight after its ownership gates and before its first status write. `--validate-only` runs it too. Nothing is written on refusal, and every remedy is non-destructive.
- **Fail closed on status.** A status directory that exists but holds no event log means nothing started. When the coordination worktree of a `lanes_with_coord` or `coord` Mission is not materialized, the preflight reads the status log committed on the local coordination branch, read-only, and never materializes the worktree. It refuses when that branch is not a local head (the remedy materializes the worktree, fetching the branch first when it exists only on a remote), when the branch carries no committed log, or when the log is malformed. Any other missing status directory, an unresolvable surface or an unreadable log refuses, with the cause appended to the remedy. Unknown never reads as "nothing started".
- **Cycles surface before any write.** Keeping started lane-mates together can close a lane dependency cycle that the unfrozen inputs would not have. The preflight raises that `LaneDependencyCycleError` (`LANE_DEPENDENCY_CYCLE`, unchanged text) before the first status write, so `--validate-only` and a real run refuse identically.
- **Defence in depth.** The lane writer (`compute_and_write_lanes`) re-checks the invariant before it writes `lanes.json`.
- `single_branch` Missions are exempt: their one repo-root lane has nothing to move.

## Considered Options

1. **A post-hoc diff in finalize** (compare the new and old membership of started work packages, refuse on any difference). Rejected. The heuristic would stay the deciding authority, and it would refuse #5573's own reproduction instead of keeping WP02 on `lane-b`.
2. **Freeze every lane once execution has begun.** Rejected. It forbids the supported amendment of unstarted work packages (#4141, ADR 3.x `2026-07-29-1`).
3. **Let lane computation read status and git itself.** Rejected. It breaks the documented purity of `compute_lanes`. The finalize shell gathers the evidence and passes it in, as it does for the planning commit.
4. **Constraint input to the pure computation, refusing only unsatisfiable cases (chosen).** It closes the class by construction and keeps "refuse, never rescue" for degraded input (ADR [3.x `2026-09-26-2`](../3.x/2026-09-26-2-lane-naming-keyed-on-creation-input.md)).

## Consequences

- A re-finalize that overlaps an unstarted work package with a started one succeeds; the unstarted work package joins the started one's lane.
- **Intentional behaviour change:** removing a started work package's task file now refuses with `started_wp_removed`. To retire it, cancel it with `spec-kitty agent tasks move-task <WP> --to canceled --mission <handle>` without clearing its owned files.
- The `--validate-only` lane preview now reads back the previous `lanes.json` and honours the frozen membership, so its lane ids match what a real run writes.
- The `collapse_report` gains the additive rule value `frozen_lane_membership`. It is not counted in `independent_wps_collapsed`: it restates lane-mates that already shared a lane.
- A corrupt line in the planning-side status log is still refused earlier, by finalize's existing work-package read, with its existing store error. `status_unreadable` is what the preflight reports when its own read fails, for example an unresolvable coordination status surface.
- The planning-pin probe ("has execution begun?") is not yet the history-based predicate; the two answer different questions.

## Related

- ADR [3.x `2026-07-29-1`](../3.x/2026-07-29-1-lane-base-recorded-planning-commit.md): finalize-tasks is the single writer of `lanes.json`, and re-running it is supported.
- ADR [3.x `2026-09-26-2`](../3.x/2026-09-26-2-lane-naming-keyed-on-creation-input.md): degraded input is migrated or refused, never rescued.
- [#5080](https://github.com/spec-kitty/spec-kitty/issues/5080): sibling lane-identity invariant.
- Follow-ups: [#5701](https://github.com/spec-kitty/spec-kitty/issues/5701) (the #3432 cancellation residual), [#5702](https://github.com/spec-kitty/spec-kitty/issues/5702) (move the planning-pin probe and its doctor twin onto the history-based predicate), [#5703](https://github.com/spec-kitty/spec-kitty/issues/5703) (`doctor mission-state --fix` still rebuilds the lane manifest with fresh lane ids).
- Operator docs: [Execution Lanes](../../architecture/execution-lanes.md#re-finalizing-an-active-mission), [finalize-tasks internals](../../api/finalize-tasks-internals.md#5-started-work-packages-keep-their-lane-lane_membership_frozen), [topology glossary](../../context/topology.md#started-work-package).

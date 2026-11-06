---
title: Execution Lanes Own Worktrees and Mission Branches
description: 'Moves git isolation off work packages and onto execution lanes: one branch and worktree per lane, one integration branch per mission, computed into lanes.json.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-04-03'
---

## Context and Problem Statement

Spec Kitty currently treats `WorkPackage` as both the planning/review unit and the
git/worktree execution unit. That coupling is wrong.

`WorkPackage` is a planning artifact. It is useful for decomposition, review
accounting, and acceptance scoping. A `worktree` is an execution-isolation
mechanism. It is useful for preventing overlapping edits from colliding, keeping
context warm for a coherent slice of work, and making integration predictable.

Feature `028-saas-active-projects-shell` exposed the failure mode clearly:

1. A correct landing-page implementation landed.
2. Later work in another parallel execution branch touched overlapping dashboard files.
3. A stale merge reintroduced old code.
4. The feature was declared complete before the integrated mission branch
   actually satisfied the spec.

The problem was not "too much parallelism". The problem was "parallel branches
were created on the wrong boundary". We need git isolation based on conflict and
integration surfaces, not on planning-document boundaries.

## Decision Drivers

* **Safe parallelism** — parallel work should be enabled only where write scopes
  are materially disjoint.
* **Deterministic integration** — the product should be validated on one
  integrated mission branch before merging to `main`.
* **Reduced stale-merge regressions** — branches that overlap on the same
  surfaces must not drift independently for long periods.
* **Warm execution context** — sequential work on the same surface should reuse
  the same branch/worktree.
* **Planner/runtime coherence** — planning artifacts should express both
  dependency order and merge-risk boundaries.

## Considered Options

* **Option 1:** Continue with one worktree per work package
* **Option 2:** One worktree per execution lane, with a mission integration branch
* **Option 3:** One worktree per mission, even when work is safely parallelisable

## Decision Outcome

**Chosen option: Option 2**, because it preserves useful parallelism while
moving git isolation to the correct unit: the execution lane.

### Core Decision

1. `WorkPackage` remains the planning, review, and accounting unit.
2. `ExecutionLane` becomes the git branch and worktree unit.
3. Every active lane gets one long-lived branch and one worktree.
4. Multiple sequential WPs may execute inside the same lane branch/worktree.
5. Every mission gets one integration branch.
6. Only the mission integration branch may merge to `main`.

### Lane Computation Contract

The planner MUST emit a machine-readable `lanes.json` artifact after tasks are
finalized.

Lane computation MUST consider both:

1. the WP dependency DAG, and
2. predicted write-scope / product-surface overlap.

Two WPs MUST be placed in the same lane when any of the following are true:

1. one depends on the other,
2. they share predicted file paths,
3. they share predicted product surfaces,
4. one is a cleanup/deprecation WP for a surface changed by the other,
5. one is an integration/QA WP validating the other in integrated form.

The lane manifest is mandatory runtime input. `implement`, `review`, `accept`,
and `merge` MUST fail closed when `lanes.json` is absent or malformed. There is
no runtime fallback to per-WP worktrees, per-WP branches, or structure
"detection" logic.

### Branch Model

1. Mission integration branch naming MUST follow:
   `kitty/mission-<feature-slug>`
2. Lane branch naming MUST follow:
   `kitty/mission-<feature-slug>-lane-<id>`
3. Lane branches merge into the mission integration branch continuously at
   stable checkpoints.
4. `main` is updated only from the mission integration branch, never directly
   from a lane branch.
5. When the planner computes exactly one lane, the feature gets exactly one
   worktree and one lane branch. Sequential DAGs are valid single-lane
   features, not a reason to recreate per-WP worktrees.

### Stale-Lane Merge Guard

A lane branch MUST NOT merge into the mission integration branch when:

1. the mission branch has advanced since the lane last synced, and
2. the changed-file intersection between lane and mission branch is non-empty.

In that case, the lane MUST first rebase or merge mission-branch changes, then
re-run review on the overlapping diff before merging.

## Consequences

### Positive

* Parallelism is preserved where it is actually safe.
* Sequential work on one surface stops paying the overhead of creating new
  branches/worktrees for every WP.
* Mission integration becomes explicit instead of being an accidental side
  effect of a final merge.
* Stale branch merges that reintroduce reverted code become blockable by policy,
  not just discoverable after damage.

### Negative

* Planner complexity increases because lane computation now needs conflict
  heuristics, not just dependency ordering.
* Lane branches are longer-lived than transient task branches and therefore
  need better merge discipline.
* Progress accounting becomes two-dimensional: WPs are still tracked, but lane
  state must also be visible.

### Neutral

* Existing WP review checkpoints remain valid; they now happen inside a lane
  rather than implying one branch per WP.
* Cleanup WPs are no longer presumed independent. They inherit the lane of the
  surface they clean unless proven otherwise.

### Confirmation

This decision is validated when all of the following are true:

1. Planner output includes `lanes.json` for each mission.
2. Missions with no safe parallelism produce exactly one lane and one worktree.
3. Missions with safe disjoint work produce multiple lanes without overlapping
   write scopes.
4. QA and final acceptance happen on the mission integration branch, not on a
   stale lane branch.
5. Regressions of the Feature 028 class are blocked by stale-lane merge guards
   before they reach `main`.
6. No shipped runtime command creates or merges `.worktrees/<feature>-WP##`
   worktrees or `<feature>-WP##` branches.

## Pros and Cons of the Options

### Option 1: One worktree per work package

Each WP gets its own branch and worktree regardless of write overlap.

**Pros:**

* Simple mental model on paper.
* Easy to explain if planning and execution boundaries are treated as identical.

**Cons:**

* Wrong isolation boundary — overlapping surfaces still diverge independently.
* Sequential WPs on the same surface pay repeated worktree and merge overhead.
* Encourages QA to review non-integrated branch states.
* Caused the stale-merge regression class seen in Feature 028.

### Option 2: One worktree per execution lane

Use conflict-aware lanes as the execution unit and keep WPs as planning units.

**Pros:**

* Aligns branch isolation with actual merge risk.
* Preserves context for sequential work on one surface.
* Makes integrated mission-branch QA the natural default.

**Cons:**

* Requires new planner output and new scheduling/orchestration logic.
* Lane boundaries must be explained and visualized clearly.

### Option 3: One worktree per mission

All work for a mission happens in one branch/worktree, even if disjoint.

**Pros:**

* Simplest branch topology.
* No cross-lane merge risk inside a mission.

**Cons:**

* Sacrifices legitimate parallelism.
* Creates needless serial bottlenecks on disjoint surfaces.
* Makes large missions slower and noisier than necessary.

## More Information

**Supersedes:**
* `architecture/1.x/adr/2026-01-26-9-worktree-cleanup-at-merge-not-eager.md`
* `2026-01-29-15-merge-first-suggestion-for-completed-dependencies.md`
* `2026-01-30-18-auto-detect-merged-single-parent-dependencies.md`

**Related ADRs:**
* `2026-02-17-1-canonical-next-command-runtime-loop.md`
* `2026-04-03-2-review-approval-and-integration-completion-are-distinct.md`
* `2026-04-03-3-feature-acceptance-runs-on-the-integrated-mission-branch.md`

**Related Product Document:**
* Companion planning artifact: `prd-lane-based-execution-and-feature-acceptance-gates-v1.md` in the planning repo

## Amendment 2026-11-06: lane branches are long-lived, lane checkouts belong to one workflow action

**Status of this amendment:** Proposed (2026-11-06). Operator ruling 5 of epic [#7276](https://github.com/spec-kitty/spec-kitty/issues/7276) (DM `01M6QY3BFCGCA7CXE4TZ9W70WH`, Mission `lane-worktree-model-hardening-01M6QY1M`): "Short-lived per-command lane checkouts: amend ADR 2026-04-03-1 now. Releasing a checkout commits or refuses." Slice S3, [#7279](https://github.com/spec-kitty/spec-kitty/issues/7279). The earlier text of this record is a snapshot and still says "feature" and "merge"; this amendment uses Mission and lane consolidation.

**Core Decision 3 is amended.** It read: "Every active lane gets one long-lived branch and one worktree." It now reads:

> 3. Every active lane gets one **long-lived lane branch**. A **lane checkout** (a worktree of that branch under `.worktrees/`) is held for **one workflow action** and released at its end.

Core Decision 4 follows: sequential work packages of one lane share its lane branch; each action gets its own checkout. The lane branch, not the checkout, carries the lane's work: every gate reads the lane branch ref and the `lane_head` stamps, never a checkout (the `for_review` gate on the lane branch, Mission WP08). Lane consolidation and the Branch Model are unchanged.

**What the amendment fixes, for the follow-up that builds it:**

- **Acquire and release points.** A checkout is acquired at the start of `spec-kitty agent action implement <WP>` and `spec-kitty agent action review <WP>`, and released at the end of that action: for implement, at the `in_progress -> for_review` hand-off; for review, at the verdict. No other command holds a lane checkout across its own exit.
- **Releasing commits or refuses.** A release never discards work. Work in the checkout is committed by the action before release, or the release refuses and keeps the checkout, naming the paths. A release is a destructive operation under [ADR 2026-11-06-1](https://github.com/spec-kitty/spec-kitty/pull/7275) (PR #7275, branch `issue-7211-safe-landed-prune`): O1, O2, O5, O7 and O8 apply as written. A release never deletes the lane branch, so O3, O4 and O6 do not arise.
- **The lane tip is recorded before a guarded removal.** The release writes `refs/spec-kitty/lane-tip/<branch>` (`lanes/lane_tip.py`) before the guard removes the checkout, so `DESTROYED_LANE` and `LANE_WORK_TIP_UNKNOWN` keep their evidence.
- **Attached checkouts.** A lane checkout is created on the lane branch, attached, never detached, so the `post-commit` / `post-rewrite` lane-tip recorder hook fires on every commit made in it.
- **Re-entry.** Work resumes with `spec-kitty agent action implement <WP>`, which acquires a fresh checkout of the existing lane branch (the route that finds the branch present and the worktree gone). A stale lane is refreshed by auto-rebase on re-entry (Mission assumption A-10). No manual `cd .worktrees/... && git merge` recipe is taught.
- **Harness working directories across turns.** A checkout path is valid only for the action that printed it. A harness that keeps a working directory across turns re-runs the action command to get a checkout again, and must not write into a released path. A harness isolation worktree (one the harness creates for itself) is not a lane checkout and never a status surface.
- **The review lock lives outside the checkout.** `.spec-kitty/review-lock.json` sits inside the lane worktree today (`review/lock.py`); a short-lived checkout would take the lock with it. The lock moves to a location that survives a release (for example under the git common dir), as part of the follow-up.
- **Auto-rebase without a held checkout.** Auto-rebase (`lanes/auto_rebase.py`) merges inside a lane worktree today. With short-lived checkouts it runs inside the checkout the re-entry action acquires. A merge with no checkout at all (`git merge-tree --write-tree`, then a compare-and-swap ref update, git 2.38 or later) is a possible later optimisation for clean merges only; a conflicted merge always needs the action's checkout.
- **Migration of existing checkouts.** Existing long-lived lane worktrees stay valid. The first action that runs in one adopts it as acquired and releases it at its end. Idle ones are removed by consolidation's final cleanup (ruling 6, slice S5) or by the `spec-kitty doctor workspaces --prune` backstop, under the same proofs; never with `--force`.

**The one lane-checkout helper is the future lease acquire.** Every lane checkout is created by one helper, `open_lane_checkout` (Mission WP09, `lanes/lane_checkout.py`), on every route: allocation, recovery, the lifecycle-sync recreate, the review checkout and the printed recreate command. It installs the lane-tip hook, the local excludes and the status exclusion. That helper is where the lease is acquired once leases exist.

**The lease implementation is a follow-up Mission** (Mission constraint C-007): lease state, the review-lock relocation and release-on-transition wiring are not built by Mission `lane-worktree-model-hardening-01M6QY1M`. Until that follow-up ships, lane checkouts keep today's lifetime; what ships now is the single helper and the `for_review` gate on the lane branch, which together make the release safe to add.

**Confirmation** (replaces Confirmation item 2's "exactly one lane and one worktree" with "exactly one lane branch, and a checkout only during an action"):

- the `for_review` gate needs no lane checkout: `tests/specify_cli/lanes/test_for_review_gate_parity.py` (Mission WP08);
- every lane checkout comes from the one helper, attached, with the hook and the exclusions: `tests/architectural/test_lane_checkout_single_seam.py` (with planted-violation self-tests) and `tests/lanes/test_lane_checkout_helper.py` (Mission WP09);
- the release itself (commit or refuse, tip recorded before removal, review lock outside the checkout) is confirmed by the lease follow-up Mission's own tests.

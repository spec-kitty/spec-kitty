---
title: 'Context: Topology'
description: 'Glossary context for mission topology: the four topologies, write checkout, repo-root and code lanes, protected target, mission branch, lane work tip, and absorbed lane.'
doc_status: active
updated: '2026-09-29'
related:
- docs/context/orchestration.md
- docs/context/execution.md
- docs/architecture/execution-lanes.md
---
## Context: Topology

Terms describing the shape a mission is given at creation and where its work runs. Introduced by mission `single-branch-topology-honesty-01M3M22V` (#5100). Related placement vocabulary — [PRIMARY partition](./orchestration.md#primary-partition), [COORD partition](./orchestration.md#coord-partition), [Topology Surface](./orchestration.md#topology-surface) — lives in [Context: Orchestration](./orchestration.md).

### Topology

| | |
|---|---|
| **Definition** | The shape a mission is given at creation, stored as `topology` in `meta.json`. Exactly four values, the 2x2 product of "has a coordination branch" and "has lanes": `single_branch` (no coordination, no lanes: every work package runs in the [write checkout](#write-checkout)), `lanes` (no coordination, computed code lanes), `coord` (coordination, no lanes), `lanes_with_coord` (coordination and code lanes). Realized by the `MissionTopology` enum in `src/mission_runtime/context.py`. On a non-primary branch the create-time default is `lanes`; `single_branch` comes only from an explicit `--topology single_branch` or from `--owned-checkout`. |
| **Context** | Topology |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Do NOT use when** | The concept is the artifact-kind routing rule — use [PRIMARY partition](./orchestration.md#primary-partition) or [COORD partition](./orchestration.md#coord-partition). The concept is the physical tree an artifact resolves to — use [Topology Surface](./orchestration.md#topology-surface). Never write "mode" or "layout" for a topology. |
| **Related terms** | [write checkout](#write-checkout), [code lane](#code-lane), [Topology Surface](./orchestration.md#topology-surface), [Lane](./orchestration.md#lane) |

---

### Write checkout

| | |
|---|---|
| **Definition** | The one checkout a `single_branch` mission writes code and status into: either the [repository root checkout](./execution.md#repository-root-checkout) or a validated owned checkout (ADR 2026-09-03-1). Work packages run in it one at a time, stamped `execution_mode: direct_repo`. `implement` refuses with `WRITE_CHECKOUT_WRONG_BRANCH`, `WRITE_CHECKOUT_OCCUPIED` or `WRITE_CHECKOUT_DIRTY` (a resume is exempt from the dirty check). |
| **Context** | Topology |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Do NOT use when** | The mission has code lanes — its work runs in a lane worktree, not a write checkout; use [code lane](#code-lane). The concept is only the operator's repository-root working copy as opposed to a lane worktree — use [repository root checkout](./execution.md#repository-root-checkout). Never write "main repo" or "main repository". |
| **Related terms** | [repo-root lane](#repo-root-lane), [repository root checkout](./execution.md#repository-root-checkout), [mission branch](#mission-branch), [Topology](#topology) |

---

### Repo-root lane

| | |
|---|---|
| **Definition** | The single bookkeeping lane of a `single_branch` mission, keeping the existing lane id `lane-planning`. It always resolves to the [write checkout](#write-checkout), never to a `.worktrees/` path, and has no lane branch. It generalises the planning lane that every topology already carries for `planning_artifact` work packages. |
| **Context** | Topology |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Do NOT use when** | The lane resolves to a `.worktrees/` lane worktree — use [code lane](#code-lane). Never call a `single_branch` lane "lane-a". |
| **Related terms** | [write checkout](#write-checkout), [code lane](#code-lane), [Lane](./orchestration.md#lane) |

---

### Code lane

| | |
|---|---|
| **Definition** | A lane that resolves to a `.worktrees/` lane worktree and a lane branch. Only `lanes` and `lanes_with_coord` missions have code lanes. A [repo-root lane](#repo-root-lane) is never a code lane. A `single_branch` mission whose `lanes.json` holds a code lane is unmigrated and fails closed with `SINGLE_BRANCH_CODE_LANES_UNMIGRATED`; the remedy is `spec-kitty migrate backfill-topology --restamp-single-branch` (always works), or `spec-kitty upgrade` (its re-stamp migration can be a no-op where it is already recorded). |
| **Context** | Topology |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Do NOT use when** | The lane is the `lane-planning` bookkeeping lane — use [repo-root lane](#repo-root-lane). The concept is lane consolidation into the mission branch — use [Lane Consolidation](./orchestration.md#lane-consolidation). |
| **Related terms** | [repo-root lane](#repo-root-lane), [lane work tip](#lane-work-tip), [Lane](./orchestration.md#lane), [Topology](#topology) |

---

### Protected target

| | |
|---|---|
| **Definition** | A target branch that is the repository's [primary branch](./orchestration.md#primary-branch), or one that `ProtectionPolicy` reports as protected. Both cases are answered by one query, `ProtectionPolicy.is_protected_target` (`src/specify_cli/git/protection_policy.py`); no forge API is consulted. A `single_branch` mission targeting a protected target gets a [mission branch](#mission-branch) at create time unless `--commit-to-target` is passed; that flag (persisted in `meta.json`, decided in `ProtectionPolicy`) un-protects only that mission's own target for its own writes. |
| **Context** | Topology |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Do NOT use when** | The concept is only the repository's default integration branch — use [primary branch](./orchestration.md#primary-branch). The concept is the branch a mission's code must land on regardless of protection — use [target branch](./orchestration.md#target-branch). Never use `main` as a generic name for a protected target. |
| **Related terms** | [mission branch](#mission-branch), [primary branch](./orchestration.md#primary-branch), [target branch](./orchestration.md#target-branch) |

---

### Mission branch

| | |
|---|---|
| **Definition** | `kitty/mission-<slug>-<mid8>`. For a `single_branch` mission it is minted and checked out in the [write checkout](#write-checkout), and recorded as `mission_branch` in `meta.json`, only when the mission targets a [protected target](#protected-target) without `--commit-to-target`. `spec-kitty consolidate` then lands the mission branch onto the target. Lane-based missions carry the same branch name as the consolidation base of their code lanes. |
| **Context** | Topology |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Do NOT use when** | The concept is the branch a mission's code must ultimately land on — use [target branch](./orchestration.md#target-branch). The concept is the coordination branch — say "coord branch". The concept is a single lane's branch — use [code lane](#code-lane). |
| **Related terms** | [protected target](#protected-target), [write checkout](#write-checkout), [Lane Consolidation](./orchestration.md#lane-consolidation), [target branch](./orchestration.md#target-branch) |

---

### Lane work tip

| | |
|---|---|
| **Definition** | The last commit made on a lane branch, recorded when the commit happens, independent of any spec-kitty command. It is stored in `refs/spec-kitty/lane-tip/<branch>`, written by a POSIX `post-commit` / `post-rewrite` hook when the recorder is installed (migration `4_0_0rc5_install_lane_tip_recorder`; a foreign hook is left untouched; the hooks are skipped with a warning when `core.hooksPath` is `/dev/null`, missing, or inside the working tree), plus spec-kitty's own record points (`implement`, `for_review` transitions, crash recovery, auto-rebase; `src/specify_cli/lanes/lane_tip.py`). It is distinct from the lane's creation base. A destroyed lane with unabsorbed work is refused with `DESTROYED_LANE`, which names the SHA and the restore command `git branch <b> refs/spec-kitty/lane-tip/<b>`. `LANE_WORK_TIP_UNKNOWN` (`LaneWorkTipUnknownError`) fires when a lane's branch was deleted before any work tip was recorded, or after its `refs/spec-kitty/lane-tip/<branch>` ref was deleted: nothing is left to classify the lane by, so the guard fails closed. Its message says to look for stranded commits (`git reflog <branch>` or `git fsck --lost-found`); if you find one, record it with `git update-ref refs/spec-kitty/lane-tip/<branch> <sha>` and re-run `implement`; if you are sure no work was ever committed, run `spec-kitty context cleanup` to clear the stale workspace record and retry. Abandoning a destroyed lane (`DESTROYED_LANE`) is two steps today: `git update-ref -d refs/spec-kitty/lane-tip/<branch>`, then `spec-kitty context cleanup`. Squash-absorption detection needs git >= 2.38 (`git merge-tree --write-tree`); on older git the guard fails closed and refuses even a genuinely squash-merged lane. |
| **Context** | Topology |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Do NOT use when** | The concept is the commit a lane was cut from — say "lane base". Never write a bare "head" or a bare "tip" for the work tip. |
| **Related terms** | [absorbed lane](#absorbed-lane), [code lane](#code-lane), [Lane](./orchestration.md#lane) |

---

### Absorbed lane

| | |
|---|---|
| **Definition** | A lane whose [work tip](#lane-work-tip) is an ancestor of the target, equals the lane's base (`tip == base`, nothing was ever committed), or whose integration into the target would change nothing (for example after a squash). The destroyed-lane guard treats an absorbed lane as safe to re-cut; an unabsorbed one is refused. Squash detection needs git >= 2.38; if git cannot evaluate absorption (including any older git) the check fails closed and the lane is not treated as absorbed. |
| **Context** | Topology |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Do NOT use when** | The concept is one of the three "merge" operations — use [Lane Consolidation](./orchestration.md#lane-consolidation), [Branch Integration / Git Merge](./orchestration.md#branch-integration--git-merge) or [Publish to origin/main](./orchestration.md#publish-to-originmain). Never write bare "merged" for an absorbed lane. |
| **Related terms** | [lane work tip](#lane-work-tip), [Lane Consolidation](./orchestration.md#lane-consolidation) |

---

### Execution-mode stamp

| | |
|---|---|
| **Definition** | The `execution_mode` recorded on status events: `worktree` or `direct_repo`. `direct_repo` is stamped for every work package that runs in a [write checkout](#write-checkout), and also for `planning_artifact` work packages of every topology, because they resolve to the repo-root lane. It is **not** the work-product kind (`code_change` / `planning_artifact`), which older code and work-package frontmatter also call `execution_mode`. |
| **Context** | Topology |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Do NOT use when** | The concept is whether a work package produces code or planning artifacts — say "work-product kind" (`code_change` / `planning_artifact`). Never write bare "execution_mode" when the kind is meant. |
| **Related terms** | [write checkout](#write-checkout), [work package](./orchestration.md#work-package) |

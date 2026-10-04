---
title: 'ADR: upgrade writes project-global state once, in the repository root checkout'
description: 'Upgrade writes project-global state once on the repository root checkout; integration merge sites resolve primary-owned bookkeeping by one declared rule.'
status: Accepted
date: '2026-10-04'
updated: '2026-10-04'
---

**Status:** Accepted

**Date:** 2026-10-04

**Deciders:** Stijn Dejongh (owner). Operator brief for #5457.

**Technical Story:** [#5457](https://github.com/spec-kitty/spec-kitty/issues/5457), Mission `upgrade-project-global-state-01M44538`. Related: #2385, #2392, #4972, #4892.

---

## Context and Problem Statement

`spec-kitty upgrade` run on a project with a Mission in flight wrote the project's generated bookkeeping once per checkout: in the repository root checkout and again in every live lane and coordination worktree. Each copy was committed on that worktree's own branch. `MigrationRunner._upgrade_worktrees` treated every directory under `.worktrees/` as a project of its own, kept a separate `ProjectMetadata` record per worktree, and stamped a fresh `applied_at` on every migration record in every copy. On 4.0.0rc5 and later the same run also committed an identical `.gitattributes` line on every branch.

The Mission's integration checks then refused a file the operator never touched (paths A, B and C of #5457):

- **Path A.** `consolidate` refused the second lane: `Lane lane-b is stale: overlapping files ['.gitattributes', '.kittify/metadata.yaml']`.
- **Path B.** `consolidate` refused the squash into a non-primary target: `TARGET_BRANCH_CONTENT_CONFLICT` with `conflicting_path: .kittify/metadata.yaml`.
- **Path C.** On a coordination Mission, review start and implement resume failed with `LANE_AUTO_REBASE_FAILED: no classifier rule matched .../.kittify/metadata.yaml`.

The printed `git merge` remedy was a no-op: `consolidate` rolls the Mission branch back to its pre-run tip after the refusal, so the lane already contains that tip.

The earlier per-worktree design could not converge. #2385 and #2392 ensured that every upgrade write ends in a commit, so no checkout is left dirty. #4972 aligned `last_upgraded_at` for a version-only bump. Neither could make two copies byte-identical, because the per-record `applied_at`, the set of recorded migrations and the notes still differ between checkouts.

## Decision

Upgrade writes project-global state once, in the repository root checkout. Integrating branches receive it by integration.

1. **Write placement.** `spec-kitty upgrade` skips integrating worktrees. `_is_integrating_worktree` (`src/specify_cli/upgrade/runner.py`) is true for a worktree whose checked-out branch the branch-naming authority recognises as a `kitty/mission-…` mission, lane or coordination branch, and for a worktree whose branch cannot be read (detached HEAD fails safe). `_worktrees_to_upgrade` leaves those worktrees out, so nothing is written, stamped or committed in them. A directory without a `.git` entry, and a worktree on any other branch, keep today's behaviour.
2. **A declared primary-owned set.** The state contract (`src/specify_cli/state/contract.py`) carries `StateSurface.primary_owned`, true only for a tracked, project-root surface that Spec Kitty fully generates and marks "do not edit". `primary_owned_paths()` derives the path set and `is_primary_owned_path` matches an exact, normalised path relative to the repository root, never a basename. Today exactly one surface is primary-owned: `.kittify/metadata.yaml`. `.gitattributes`, `.gitignore` and `.kittify/config.yaml` are operator-editable, so a work package may legitimately change them and they are not in the set (the #4933 and #4978 lesson: basename exemptions lost data).
3. **A fixed resolution side per integration merge site.** A conflict confined to a primary-owned path resolves as follows. No site uses `-X ours` or `-X theirs` (#4892).

   | Site | Code | Side for a primary-owned conflict |
   |------|------|-----------------------------------|
   | Stale-lane check | `check_lane_staleness` (`lanes/stale_check.py`) | not counted (no merge) |
   | Lane → mission merge | `_merge_branch_into` (`lanes/consolidation.py`), via `resolve_primary_owned_conflicts` and `_complete_merge_after_primary_owned_resolution` | stage 2: the mission branch |
   | Mission → target | `_run_squash_merge` and `_merge_branch_into` (`lanes/consolidation.py`) | stage 2: the target |
   | Lane sync (auto-rebase) | `_resolve_managed_artifact_conflicts` (`lanes/auto_rebase.py`), rule `RULE_ID_PRIMARY_OWNED` (`R-PRIMARY-OWNED-BOOKKEEPING`) | stage 3: the incoming coordination or mission branch |
   | Dependency-lane merge | `_merge_dependency_lane_tips` (`lanes/worktree_allocator.py`), via `_complete_merge_after_primary_owned_resolution` | stage 2: the dependent lane |

   Every resolved side is either closer to the primary branch, or a lane copy that is never authored and is resolved again at the next integration.
4. **The stale check ignores content-identical overlaps.** `_filter_benign_overlaps` drops primary-owned paths and any overlapping path whose tree entry (mode and object id, or absence) is identical at the lane tip and the Mission tip. Equal end states merge trivially. A failed probe cannot prove identity, so every candidate stays stale.

A Mission already caught in the broken state heals on its next `consolidate`, review or implement, with no manual edit, history rewrite or destructive command. The operator runbook is [`docs/operations/upgrade-with-live-lanes-recovery.md`](../../operations/upgrade-with-live-lanes-recovery.md).

## Considered Options

1. **Align the per-worktree copies.** Rejected. This is the #2385, #2392 and #4972 design. The per-record `applied_at`, the migration record set and the notes cannot be made byte-identical across checkouts.
2. **Refuse upgrade while lanes are live.** Rejected. It blocks the main 3.2.x to 4.0 route for every team that upgrades mid-Mission.
3. **A git merge driver for `.kittify/metadata.yaml`.** Rejected. The refusals are raised by Spec Kitty's own checks (stale check, squash gate, classifier), which a driver does not reach, and a driver needs per-clone configuration.
4. **Per-hunk classifier rules.** Rejected. The file is wholly generated, so a whole-file resolution side is correct and a hunk-level rule adds no safety.
5. **Skip integrating worktrees, declare primary-owned bookkeeping, fix the resolution side per site (chosen).** It removes the defect class at its source and recovers Missions already affected.

## Consequences

- Upgrade leaves no integrating worktree dirty and adds no upgrade commit to a lane, mission or coordination branch (the #2385 and #2392 invariant holds trivially).
- Commands run inside a worktree resolve `.kittify` from the repository root checkout, so a lane that keeps its pre-upgrade copy is harmless at runtime.
- **Residuals:**
  - Lanes keep their pre-upgrade `.gitignore` and `.gitattributes` until they integrate. See the amendment to [ADR 2026-07-07-1](../3.x/2026-07-07-1-ignored-surface-backfill-migration-pattern.md).
  - Ignored per-checkout surfaces are no longer refreshed in integrating worktrees.
  - A pre-`kitty/` legacy branch (`NNN-slug[-WP##]`) is not recognised as integrating, so its worktree keeps today's behaviour.
  - `--strategy rebase` is not covered by the merge-site resolution above.
  - For a genuine overlap between two lanes on an operator-editable file, the printed stale remedy is still a no-op after the in-run rollback. This Mission removes the upgrade-induced trigger only. The general stale-remedy wording is a defect. Follow-up: [#5711](https://github.com/spec-kitty/spec-kitty/issues/5711).
  - Migrations with `runs_on_worktrees=True` that rewrite tracked Mission state no longer reach coordination or lane branches. For example, `m_3_1_1_normalize_status_json` rewrites `kitty-specs/*/status.json`, and now does so only in the repository root checkout and in worktrees that upgrade still visits. `status.json` is a derived snapshot that is re-materialized from the event log, so the impact is low today. A future migration of tracked Mission state must not rely on the worktree pass to reach in-flight branches. Follow-up: [#5712](https://github.com/spec-kitty/spec-kitty/issues/5712).
- `.kittify/metadata.yaml` keeps one writer, `ProjectMetadata.save()`. This decision adds no second one (see #5229).

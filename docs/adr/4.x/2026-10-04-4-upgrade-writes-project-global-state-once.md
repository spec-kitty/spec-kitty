---
title: 'ADR: upgrade writes project-global state once, in the repository root checkout'
description: 'Upgrade writes project-global state once on the repository root checkout; integration merge sites resolve target-owned bookkeeping by one declared rule.'
status: Accepted
date: '2026-10-04'
updated: '2026-10-05'
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

Upgrade writes project-global state in the repository root checkout and no longer in any integrating worktree. A lane's own copy is not brought forward while the Mission is in flight: no step merges the merge target branch into the Mission branch, so a lane keeps its pre-upgrade copy until consolidation, where the merge target branch's copy survives.

1. **Write placement.** `spec-kitty upgrade` skips integrating worktrees. `_is_integrating_worktree` (`src/specify_cli/upgrade/runner.py`) is true for a worktree whose checked-out branch the branch-naming authority recognises as a `kitty/mission-…` mission, lane or coordination branch, and for a worktree whose branch cannot be read (detached HEAD fails safe). `_worktrees_to_upgrade` leaves those worktrees out, so nothing is written, stamped or committed in them. A directory without a `.git` entry, and a worktree on any other branch, keep today's behaviour: upgrade still writes, stamps and commits there (see Residuals).
2. **A declared set of target-owned bookkeeping.** ("Target-owned" is defined in the [glossary](../../context/orchestration.md#target-owned-bookkeeping): the copy on the merge target branch is the authoritative one. The identifiers were first named `primary_owned`; they were renamed before release because that read as the PRIMARY partition or the primary branch, and it meant neither.) The state contract (`src/specify_cli/state/contract.py`) carries `StateSurface.target_owned`, true only for a tracked, project-root surface that Spec Kitty fully generates and marks "do not edit". `target_owned_paths()` derives the path set and `is_target_owned_path` matches an exact, normalised path relative to the repository root, never a basename. Today exactly one surface is target-owned: `.kittify/metadata.yaml`. `.gitattributes`, `.gitignore` and `.kittify/config.yaml` are operator-editable, so a work package may legitimately change them and they are not in the set (the #4933 and #4978 lesson: basename exemptions lost data).
3. **A fixed resolution side per integration merge site.** A conflict confined to a target-owned path resolves as follows. No site uses `-X ours` or `-X theirs` (#4892).

   | Site | Code | Side for a target-owned conflict |
   |------|------|-----------------------------------|
   | Stale-lane check | `check_lane_staleness` (`lanes/stale_check.py`) | not counted (no merge) |
   | Lane → mission merge | `_merge_branch_into` (`lanes/consolidation.py`), via `resolve_target_owned_conflicts` and `_complete_merge_after_target_owned_resolution` | stage 2: the mission branch |
   | Mission → target | `_run_squash_merge` and `_merge_branch_into` (`lanes/consolidation.py`) | stage 2: the target |
   | Lane sync (auto-rebase) | `_resolve_managed_artifact_conflicts` (`lanes/auto_rebase.py`), rule `RULE_ID_TARGET_OWNED` (`R-TARGET-OWNED-BOOKKEEPING`) | stage 3: the incoming coordination or mission branch |
   | Dependency-lane merge | `_merge_dependency_lane_tips` (`lanes/worktree_allocator.py`), via `_complete_merge_after_target_owned_resolution` | stage 2: the dependent lane |
   | Recorded planning-commit merge on implement resume | `_merge_recorded_planning_commit` (`lanes/worktree_allocator.py`) | stage 2: the lane |

   Every resolved side is either the copy closer to the merge target branch, or a lane copy that is never authored and is resolved again at the next integration. The Mission → target `--strategy merge` leg reconciles the derived `status.json` only when it also resolved a target-owned path; a conflict on `status.json` alone still refuses there.

   The resolver breaks ties; it is not an ownership invariant. A lane's upgraded copy still merges cleanly onto a Mission branch or target that did not change the file.
4. **The stale check ignores content-identical overlaps.** `_filter_benign_overlaps` drops target-owned paths and any overlapping path whose tree entry (mode and object id, or absence) is identical at the lane tip and the Mission tip. Equal end states merge trivially. A failed probe cannot prove identity, so every candidate stays stale.

A Mission already caught in the broken state heals on its next `consolidate`, review or implement, with no manual edit, history rewrite or destructive command. The operator runbook is [`docs/operations/upgrade-with-live-lanes-recovery.md`](../../operations/upgrade-with-live-lanes-recovery.md).

## Considered Options

1. **Align the per-worktree copies.** Rejected. This is the #2385, #2392 and #4972 design. The per-record `applied_at`, the migration record set and the notes cannot be made byte-identical across checkouts.
2. **Refuse upgrade while lanes are live.** Rejected. It blocks the main 3.2.x to 4.0 route for every team that upgrades mid-Mission.
3. **A git merge driver for `.kittify/metadata.yaml`.** Rejected. The refusals are raised by Spec Kitty's own checks (stale check, squash gate, classifier), which a driver does not reach, and a driver needs per-clone configuration.
4. **Per-hunk classifier rules.** Rejected. The file is wholly generated, so a whole-file resolution side is correct and a hunk-level rule adds no safety.
5. **Skip every linked worktree.** Not chosen here. Commands in any linked worktree read `.kittify` from the repository root checkout, so the argument for skipping applies to all of them, but it changes behaviour for worktrees on ordinary branches (#2385, #4972). Follow-up: [#5747](https://github.com/spec-kitty/spec-kitty/issues/5747).
6. **Declare the fact in the dirty-churn classifier (`coherence`) instead of the state contract.** Rejected. That classifier answers "may this dirty file be ignored", a different question, and a dirty copy must still block.
7. **Skip integrating worktrees, declare target-owned bookkeeping, fix the resolution side per site (chosen).** It removes the defect at its source for Mission worktrees and recovers Missions already affected.

## Consequences

- Upgrade leaves no integrating worktree dirty and adds no upgrade commit to a lane, mission or coordination branch (the #2385 and #2392 invariant holds trivially).
- Commands run inside a worktree resolve `.kittify` from the repository root checkout, so a lane that keeps its pre-upgrade copy is harmless at runtime.
- **Residuals:**
  - Lanes keep their pre-upgrade `.gitignore` and `.gitattributes` until they integrate. See the amendment to [ADR 2026-07-07-1](../3.x/2026-07-07-1-ignored-surface-backfill-migration-pattern.md).
  - Ignored per-checkout surfaces are no longer refreshed in integrating worktrees.
  - A pre-`kitty/` legacy branch (`NNN-slug[-WP##]`) is not recognised as integrating, so its worktree keeps today's behaviour.
  - `--strategy rebase` is not covered by the merge-site resolution above.
  - **Worktrees on other branches are still upgraded.** A linked worktree whose branch is not a `kitty/mission-…` branch (a feature or landing branch) still gets its own `.kittify/metadata.yaml` commit and every worktree-running migration. When that branch reaches the merge target branch through a pull request, no Spec Kitty resolver is on the path. Follow-up: [#5747](https://github.com/spec-kitty/spec-kitty/issues/5747).
  - **Upgrade run from inside a lane worktree.** The skip covers the sibling worktrees of the checkout upgrade runs in. Run with a lane worktree as the current directory, upgrade still treats it as the project and commits `.kittify/metadata.yaml`, `.gitattributes` and `.kittify/config.yaml` on the lane branch. Follow-up: [#5747](https://github.com/spec-kitty/spec-kitty/issues/5747).
  - **Skipped worktrees are not listed.** Upgrade does not name the integrating worktrees it left alone.
  - **`.gitattributes` on an already-affected Mission.** When the merge target branch's `.gitattributes` differs from the lanes' (any edit on the target after the Mission was cut, plus the line the earlier upgrade appended on each branch), `consolidate` still refuses with `TARGET_BRANCH_CONTENT_CONFLICT` on `.gitattributes`. The file is operator-editable, so it is deliberately not target-owned.
  - **Tracked generated tool files in lanes.** Generated command and skill copies in a lane worktree are no longer refreshed by upgrade until the lane integrates.
  - A project nested below the repository root (`sub/.kittify/metadata.yaml`) is not matched and gets no recovery.
  - For a genuine overlap between two lanes on an operator-editable file, the printed stale remedy is still a no-op after the in-run rollback. This Mission removes the upgrade-induced trigger only. The general stale-remedy wording is a defect. Follow-up: [#5711](https://github.com/spec-kitty/spec-kitty/issues/5711).
  - Migrations with `runs_on_worktrees=True` that rewrite tracked Mission state no longer reach coordination or lane branches. For example, `m_3_1_1_normalize_status_json` rewrites `kitty-specs/*/status.json`, and now does so only in the repository root checkout and in worktrees that upgrade still visits. `status.json` is a derived snapshot that is re-materialized from the event log, so the impact is low today. A future migration of tracked Mission state must not rely on the worktree pass to reach in-flight branches. Follow-up: [#5712](https://github.com/spec-kitty/spec-kitty/issues/5712).
- This decision adds no writer of `.kittify/metadata.yaml`. The file already has several (`ProjectMetadata.save()`, the schema stamp in `upgrade/runner.py`, `migration/runner.py`, `migration/backfill_identity.py` and `init`; see #5229), and nothing ties the state contract's path to them: if the file moved, the target-owned declaration would go inert without a failing test.

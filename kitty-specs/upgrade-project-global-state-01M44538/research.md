# Research — upgrade-project-global-state-01M44538

The evidence base is [`research/code-grounding.md`](research/code-grounding.md) (a five-lens pre-spec squad) and [`research/squad-dispositions.md`](research/squad-dispositions.md) (the post-specify squad). This file records the plan-time decisions in Decision / Rationale / Alternatives form.

## D1 — Skip integrating worktrees in upgrade
- **Decision**: `_upgrade_worktrees` skips worktrees whose branch is `kitty/mission-…` (via `parse_mission_slug_from_branch`), or whose branch is unreadable.
- **Rationale**: An alignment approach can never make the copies identical: the per-record `applied_at`, the record set and the notes all differ (grounding §2). Commands run inside a worktree read `.kittify` from the repository root checkout (`core/paths.py:197`), so a stale lane copy is inert. `--no-worktrees` already proves that skipping is a supported state.
- **Alternatives**:
  - (a) Align worktree metadata to main's content. Rejected: it still commits on lane branches, and `.gitattributes` still overlaps.
  - (b) Refuse upgrade while lanes are live. Rejected: it burdens the operator, and missions already broken stay stuck.
  - (c) Make `runs_on_worktrees` opt-in across 102 migrations. Rejected: a large blast radius for the same effect.

## D2 — State contract owns "primary-owned"
- **Decision**: add `StateSurface.primary_owned`, set to true only for `project_metadata`.
- **Rationale**: The state contract already registers `.kittify/metadata.yaml` with owner `init/upgrade`, and already drives derived consumers (the gitignore entries). `coordination/coherence.py` answers a different question: which dirty churn a gate may ignore.
- **Alternatives**: a predicate in `coherence.py` (wrong fact); a module-level list in `lanes/` (forbidden by `test_exemption_registry_ratchet.py`).

## D3 — One shared resolver at the git-merge sites
- **Decision**: `resolve_primary_owned_conflicts(worktree, env)` keeps stage 2, or removes the path when stage 2 is absent. Three sites call it: the squash, the MERGE branch of `_merge_branch_into`, and the dependency-lane merge.
- **Rationale**: In each of those merges, "ours" is already the right side: the target, the mission branch, or the dependent lane respectively. The resolver handles modify/delete conflicts.
- **Alternatives**: a `_MERGE_DRIVERS` entry with `driver=true`. Rejected: git never invokes a driver on modify/delete, and `test_merge_reconciliation_class_guard` scopes the registry to `kitty-specs/**`.

## D4 — Auto-rebase uses the managed-artifact arm
- **Decision**: add a `R-PRIMARY-OWNED-BOOKKEEPING` branch to `_resolve_managed_artifact_conflicts` that takes stage 3 (the coordination or mission side, which is incoming in a lane-worktree `git merge <mission>`).
- **Rationale**: The arm is whole-file, already handles deletions (`_remove_sparse`), and writes the audited rule id into the commit message. The per-hunk `RULES` list cannot represent a modify/delete conflict.
- **Alternatives**: a new entry in `conflict_classifier.RULES`. Rejected (disposition #5).

## D5 — Content-identical overlap is not staleness
- **Decision**: in `check_lane_staleness`, drop overlap paths whose `git ls-tree` entry (mode and object id, or absent on both sides) is equal at the lane tip and the mission tip.
- **Rationale**: Equal end states make a trivial 3-way merge, with no conflict and no semantic difference. The rule is path-agnostic, so it does not require declaring operator-editable files.
- **Alternatives**: declaring `.gitattributes` primary-owned. Rejected (C-008; the #4933 data-loss precedent).

## D6 — General stale remedy deferred
- **Decision**: the remedy text is unchanged. A follow-up issue covers the rollback-induced no-op remedy for genuine sibling overlaps.
- **Rationale**: The correct remedy merges a sibling lane, which interacts with per-WP attribution (the closed-world check). That is out of this mission's blast radius. The upgrade-induced trigger is removed.

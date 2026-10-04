# Adversarial squad dispositions — upgrade-project-global-state-01M44538

Per `adversarial-squad-deployment`: every finding gets exactly one disposition.

## Post-specify (2026-10-04) — reviewer-renata, architect-alphonso

| # | Sev | Finding (lens) | Disposition | Evidence |
|---|-----|----------------|-------------|----------|
| 1 | BLOCKER | Lane → mission merge (`_merge_branch_into` MERGE strategy) is a fifth merge site; FR-005 alone turns the stale refusal into an uncoded merge failure (both) | accepted | spec FR-012, Story 4 AS-1, Domain Language "Integration merge sites" |
| 2 | HIGH | Dependency-lane merge (`worktree_allocator._merge_dependency_lane_tips`) does not use the classifier; "incoming" is a peer lane (both) | accepted | spec FR-013, Story 4 AS-5; grounding §2 item 4 corrected here |
| 3 | HIGH | Story 4 AS-1 cannot prove FR-005/006 when auto-rebase heals first (half-fix trap) (reviewer) | accepted | spec Story 4 AS-2 (lane worktrees absent) |
| 4 | HIGH | FR-007 vs "deleted on one side": clean merges never reach a resolver; strategy scope unclear (reviewer) | accepted | spec edge cases ("deleted on one side", "--strategy rebase"), FR-007 wording |
| 5 | HIGH | Auto-rebase per-hunk `RULES` cannot express whole-file / modify-delete; use the managed-artifact arm (`_resolve_take_theirs`) (architect) | changed | spec FR-008, C-002, Key Entities |
| 6 | HIGH | Squash ordering: restore before `reconcile_derived_status_snapshot_conflicts`, else a mixed set still refuses (architect) | accepted | spec FR-007 ("whatever other derived paths conflict"), Story 4 AS-3 |
| 7 | MED | Root checkout may itself be on a `kitty/mission-…` branch (single_branch protected target) (reviewer) | accepted | spec edge case "single_branch mission on a protected target" |
| 8 | MED | Legacy `NNN-slug` claim overstated; parser is `kitty/mission-` prefixed (both) | accepted | spec Domain Language, edge case "Legacy-form branches" |
| 9 | MED | FR-010 remedy half ill-defined / contradicts Out of Scope (reviewer) | deferred_with_rationale | spec FR-010 (docs only), C-004, Out of Scope; follow-up issue to be filed at closeout |
| 10 | MED | Merge-driver alternative for the merge sites (architect) | changed | rejected for this mission: git never invokes a driver on modify/delete, and auto-rebase deliberately does not seed attributes; one shared resolve helper is used at the merge sites instead (plan) |
| 11 | MED | Residual: pre-upgrade lanes miss new `.gitattributes` driver mappings (architect) | accepted | spec Assumptions (residual window) |
| 12 | LOW | FR-001 also stops ignored-surface refreshes in lanes (reviewer) | accepted | spec Assumptions (residual window) |
| 13 | LOW | `_is_bookkeeping` in reconciliation.py is a separate broader predicate (reviewer) | accepted | spec C-002 |
| 14 | LOW | NFR-001 no-op passable (reviewer) | accepted | spec NFR-001 reworded to a measurable count |
| 15 | LOW | FR-006 applies to every path, not only bookkeeping; say so (reviewer) | accepted | spec FR-006 ("overlapping path of any kind") |
| 16 | LOW | State-contract owner, ratchet and layer compliance confirmed; exact root-anchored matching (architect) | accepted | spec FR-004 ("matched exactly and anchored at the repository root") |

## Post-tasks (2026-10-04) — reviewer-renata (test/fakeability), planner-priti (slicing)

| # | Sev | Finding (lens) | Disposition | Evidence |
|---|-----|----------------|-------------|----------|
| 17 | HIGH | Raw `git ls-tree`/`ls-files` in `lanes/` trips `test_git_path_listing_owner.py` (empty allowlist) (renata) | accepted | WP03/WP04/WP05 folds: use `kernel.git.listing.tree_entries` / `_unmerged_paths` / `_git_show_stage`; gate added |
| 18 | HIGH | `test_worktree_stamp_guard.py` (on `kitty/mission-lane-*`) and `test_symlinked_ignore_guard.py` (no git) go red under the skip (renata) | accepted | WP02 owns and re-pins both; integrating rule refined (no `.git` → not integrating; detached → integrating); spec edge case updated |
| 19 | HIGH | `lanes` fixture on protected `main` hits `PROTECTED_BRANCH_REFUSED` before the defect (renata) | accepted | WP01 fold: fixtures default to target `work`; red tests assert exact defect text |
| 20 | HIGH | Moving `merge --abort`/`reset --hard` literals trips `test_destructive_op_routing.py` (renata) | accepted | WP04 fold: extract only resolve-and-commit; WP04 owns the gate file for a justified re-pin only |
| 21 | MED | Closest ready-made builders not named; fixture knobs later WPs need (renata) | accepted | WP01 fold: `build_coord_mission`, `_build_mission_repo`, knob list |
| 22 | MED | Older-version fixture must make the divergence observable, not a version-only bump (renata) | accepted | WP01 fold: `observe_upgrade_divergence()` positive control |
| 23 | MED | Path C fallback policy inconsistent between WP02 and WP05 (renata) | accepted | WP02 fold aligns to WP05 (real `upgrade`, CLI review attempted, production-function fallback recorded) |
| 24 | MED | Half-by-half proof missing WP03 production-path legs; Story 5 AS-1 CLI control unowned (renata) | accepted | WP04 fold: AS-2 via CLI with T010/T011 revert legs + Story 5 AS-1 control |
| 25 | MED | Lane runtime after skip unpinned (renata) | accepted | WP02 fold: `agent tasks status` from a lane worktree exits 0 |
| 26 | LOW | NFR-001 / `--no-worktrees` / `--dry-run` / no-migrations stamp untested (renata) | accepted | WP02 fold: spy migration + edge cases |
| 27 | LOW | FR-007 `--strategy merge` mission→target untested (renata) | accepted | WP04 fold |
| 28 | LOW | Dependency conflict shape needs a hand-written `lanes.json` (renata) | accepted | WP04 fold + WP01 knob |
| 29 | LOW | WP06 runbook needs `docs/operations/toc.yml` / `index.md` (renata) | accepted | WP06 owned_files |
| 30 | LOW/MED | Dead-symbol / `__init__.py` exposure in WP01 (both) | accepted | WP01: no `state/__init__.py` edit, no `__all__`; owned_files trimmed |
| 31 | MED | WP02 MVP gated on WP01 predicate work (priti) | changed | WP01 fold: T004 fixtures committed first; dependency kept (WP02 needs the fixtures) |
| 32 | MED | WP04→WP03 dependency is test-reachability coupling (priti) | deferred_with_rationale | kept: AS-1/AS-2 must exercise the real stale check; pre-seeding would test a fake path |
| 33 | MED | Gate allowlist edit rights unspecified (priti) | accepted | "Gate-file rights" clause in every WP fold |
| 34 | MED | Issue-matrix rows for bare cites (priti) | accepted | WP06 fold; orchestrator records `issue-verdict` at accept |
| 35 | LOW | Stale prompt line counts in tasks.md (priti) | accepted | tasks.md |
| 36 | LOW | CHANGELOG conflicts with open PRs (priti) | accepted | WP06 fold; rebase at closeout |

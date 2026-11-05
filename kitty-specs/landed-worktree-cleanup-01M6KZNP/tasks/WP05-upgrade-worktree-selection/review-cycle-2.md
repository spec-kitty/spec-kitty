---
affected_files: []
cycle_number: 2
mission_slug: landed-worktree-cleanup-01M6KZNP
reproduction_command:
reviewed_at: '2026-11-05T07:22:54Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP05
---

# WP05 review (cycle 2): changes requested

The core behaviour is right and well tested. The default `upgrade` writes no non-Mission worktree (FR-007). The opt-ins and refusals work and happen before any write (FR-008). The plan-json keys are correct and the schema change is additive (FR-010). The red-first test fails on the base for the right reason. Two defects in the FR-009 output need fixing before approval.

## Blocking

**Issue 1: the post-run `Worktrees:` block says "upgraded and committed" for worktrees upgrade did not write or commit (FR-009).**

`_report_worktree_dispositions` prints `outcome.result.worktree_dispositions`. These are the *selection* dispositions computed at the top of `_upgrade_worktrees`, not what the pass did. Every selected worktree is rendered "upgraded and committed", even when:

- it is a plain directory with no `.git`, or has no upgradeable state. The loop `continue`s at `if not has_upgradeable_state`.
- the early return `if not selected or (migrations and not worktree_migrations)` fires. Migrations are pending but none `runs_on_worktrees`, so the selected worktree is not touched.
- auto-commit is off (`should_auto_commit_for_worktree` is False). Files may be written but nothing is committed.
- a worktree migration failed or errored. Nothing is committed, and `worktree_failures` reports the failure in the same output.

Reproduced on the lanes fixture with `.worktrees/plain` (an empty directory) and `upgrade --yes --include-worktree .worktrees/plain`. The output says `.worktrees/plain (detached): upgraded and committed`, but the directory is still empty and nothing was committed. `--all-worktrees` does the same for a symlinked entry with no `.git`. FR-009 exists "so that I know where upgrade writes", so the normal output must not claim a write or commit that did not happen.

Fix: report the worktrees the run actually wrote and committed. For example, have `_upgrade_worktrees` record a per-worktree result (upgraded and committed / upgraded, not committed / nothing to upgrade / failed), and render the post-run line from that result. The JSON `action` enum can stay as it is, since it is the plan. The preview keeps the selection wording. Add a CLI test for at least the "selected but nothing written" case and the "failed" case.

**Issue 2: a directory that is not a git worktree is labelled `(detached)`, and the hint for a symlinked entry is one that refuses.**

- `_worktree_disposition_line` renders `branch is None` as `detached`. `_branch_of` returns None for a plain directory with no `.git`. The rule says a detached worktree is a Mission skip, so `.worktrees/plain (detached): skipped, not selected` contradicts it. Render a non-git directory distinctly, for example `(not a git worktree)`.
- A symlinked entry `.worktrees/esc -> /elsewhere` is listed with an absolute path and the hint `use --include-worktree /…/.worktrees/esc or --all-worktrees`. Following that hint exits 2 with `UPGRADE_WORKTREE_NOT_FOUND`, because `validate_named` resolves the path outside `.worktrees/`. Meanwhile `--all-worktrees` *does* select it, and writes through the symlink when it has a `.kittify`. Make the two rules agree. The simplest fix is for `worktree_dispositions` to skip, or never select, an entry that does not resolve to a direct child of `.worktrees/`, which matches `validate_named`. Add tests for the symlink-escape case and the plain-directory case. Neither is covered today.

## Non-blocking notes

- Outside a project, `--no-worktrees --all-worktrees` is not refused, because `_guard_project_or_fallback_to_cli` falls back to CLI guidance first. `--cli` silently ignores both opt-in flags. Both are acceptable, but worth a line in WP06 docs.
- `tests/integration/target_owned_fixtures.py::observe_upgrade_divergence` now has no callers. `test_upgrade_integrating_worktrees.py` copies it as `_observe_upgrade_all_worktrees`. Consider giving the fixture an `*args` parameter instead of keeping a copy and a dead helper.
- `tests/upgrade/test_upgrade_worktree_commit.py::test_upgrade_invariant_every_touched_checkout_ends_clean`: the docstring picked up `worktree_selection=WorktreeSelection.all()` from the mechanical replace. Revert that docstring line.
- `src/specify_cli/.contextive/execution.yml` still cites `_is_integrating_worktree` in `runner.py`. The alias keeps the citation valid, and one test imports it, so the alias is justified. Consider pointing the glossary at `worktree_selection.is_integrating_worktree`.
- The dry-run preview prints "upgraded and committed" for a selected worktree. The contract says so, but "will be upgraded and committed" would read correctly in a preview.

## Verified (no action)

- Both CLI call sites pass the selection: the no-migrations stamp pass and `MigrationRunner.upgrade`. Preview, run and plan-json all use `worktree_dispositions`.
- `_worktrees_to_upgrade` is gone with no callers. There is no ledger or `order_manifest` change. Edits stay local to worktree handling in `upgrade.py`. There are no new suppressions. Ruff, format, C901 and mypy are clean.
- The schema change matches 288f354f, is additive (optional keys only), and leaves `schema_version` unchanged.
- The 7 out-of-map test edits only opt in (`WorktreeSelection.all()` / `--all-worktrees`) or let fakes accept the new kwarg. No assertion was loosened, and two were tightened.

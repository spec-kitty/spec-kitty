# Tracer: design-decisions

Mission git-paths-are-data-01M3SSXR. Append-only during implementation.

- 2026-09-30 plan: queries live in kernel because ref_advance must import zero specify_cli (NFR-004); no speculative core/vcs wrapper module (R4).
- 2026-09-30 post-spec squad folded: C-007 command-agnostic runner, C-008 2.25 floor, C-009 P0 landable, FR-013 fail-open classification, FR-014 literal pathspecs, concrete gate rule, T019 porcelain scan folded.

## 2026-09-30 — census rule (WP01 T006b)

- The census counts every path-listing argv outside `src/kernel/git/`, `-z` or not: a `-z` listing parsed by hand outside the owner is the same defect one step removed (FR-009 "any path-listing git invocation"). `worktree list` is out of scope (#5475).
- Positional-constant argv (`_git(root, "status", …)`) and the git-only flags `--name-only`/`--name-status`/`--numstat` on their own (a helper may add the subcommand) are classified, closing the squad's blind-spot finding.
- `[3:]` slicing counts only inside a function that mentions "porcelain", to avoid false positives on unrelated slicing.
- Base count on the branch point: 119 hits in 51 files (the first prototype saw 85 in 47).

## 2026-09-30 — #5392 red-first proof (WP02 T007)

- `tests/terminus/test_repro_5392.py` run on the branch point b99f6f41: **1 failed** — `spec-kitty consolidate` exited 0, merged the lane and ran the resync over the ignored `src/local data/notes.txt` (status printed `!! "src/local data/"`, which never matched the `ls-tree` path). The setup needs a tracked sibling under `src/`, otherwise git collapses the whole `src/` into one ignored entry.

## 2026-09-30 — WP01 review folds

- The census is stricter than the WP text: `status --porcelain … -z` and every other `-z` listing outside `kernel.git` count, because the WP03–WP08 goal is "no caller builds path-listing argv" (FR-006/FR-009), not "no caller forgets -z". WP03–WP07 migrate those sites too.
- Listings ask git for repository-relative paths whatever the cwd: `ls-files --full-name`, `ls-tree --full-tree`, and `-c diff.relative=false` for diff/show/log (`--no-relative` is newer than the git 2.25 floor; older git ignores the unknown `-c` key).
- `--` always ends the revisions, so a file named like a branch is never read as one.
- The `parse_*_z` helpers are module-private API (not in `__all__`): the dead-symbol gate requires a `src/` caller for every export, and only tests call them.

## 2026-09-30 — WP02 half-by-half proof

- b99f6f41 (branch point): `test_repro_5392` red (consolidate exits 0 and resyncs over the ignored file).
- 251f4e82 (PR #5437 cherry-picked, `path.startswith(target + "/")` only): `test_repro_5400` passes, `test_repro_5392` still **fails** — the ancestor fix alone does not see a quoted path.
- 2551859c (listing on `kernel.git`, obstruction = `GitPath.overlaps`): both pass, in a 374-test blast-radius run (ref_advance, destructive_guard, doctrine git source, coordination teardown, terminus repros, T018/T019, layer rules, dead symbols).
- `_dirty_entries` asks `status_entries(untracked="normal", ignored=True)` explicitly instead of inheriting `status.showUntrackedFiles`: a guard should not go blind because a user set that config to `no`.

## 2026-09-30 — WP02 review folds

- The dirty verdict is typed: `_dirty_reason` returns `(_DirtyReason, line)` (`TRACKED`, `OBSTRUCTION`, `REMOVAL`); `_dirty_verdicts` carries the pairs, `_dirty_entries` renders the unchanged display lines, and `reset_would_obstruct_untracked` decides on `reason is OBSTRUCTION`. The text marker constant is gone (kept only as display note `_RESET_OBSTRUCTION_NOTE`).
- `StatusEntry.display()` is safe to print: undecodable bytes show as `\xNN`, control characters (newline, ESC, tab) are escaped, ordinary non-ASCII such as `é` is kept.
- `untracked="all"` for the dirty check, refining the WP02 half-by-half choice of `normal`: a residue classifier must see `newdir/status.json`, not the collapsed `newdir/`, whatever `status.showUntrackedFiles` says. Ignored entries come from a second `--ignored` call kept at `normal` so a `.venv` is not expanded into every file.
- Reviewer's ancestor-half proof: swapping `GitPath.overlaps` for `contains` turned 7 of the #5400 tests red while #5392 stayed green, so each half of `overlaps` (inside, and ancestor) is load-bearing.

## WP04 review folds (git/, lanes/, watcher)

- `for_review_gate._has_qualifying_commit_since_claim_base` reads paths through `kernel.git.log_paths` (`--no-renames`). A move such as `src/x.py -> .kittify/x.py` now lists the deleted origin too, so the commit qualifies as implementation work; before, only the excluded destination was seen. Deliberate, pinned by a real-git test.
- `sparse_checkout_remediation._is_dirty` fails closed: a failed probe on an existing path counts as dirty and blocks `git checkout HEAD -- .`. Only a missing path is clean. This reverses the old "treat as clean" behaviour (FR-013 guard, not advisory).
- The watcher keeps (0, 0) deltas for renames and its background status probe no longer takes `index.lock` (`optional_locks=False`). `commit_helpers` follow-up unstage commands use literal pathspecs, like the probe.
- `worktree_allocator._git_status_entries` re-raises kernel failures with the old "git status failed in <path>" message so the fail-closed contract test keeps its pin.

## WP06 review folds (CLI command sites)

- The dead-code scan no longer reads paths out of `+++ b/<path>` diff headers (git appends a TAB for spaced paths and C-quotes others, so those files silently reported "no new symbols"). It diffs each changed Python path, with its rename source, under `--literal-pathspecs` and attributes added lines to the path it asked about. Cost: one `git diff` per changed Python file. A failed per-path diff is "undeterminable", never "clean".
- Acceptance readiness fails closed: when `git status` cannot be read, `_resolve_git_context` raises `AcceptanceError` instead of reporting an empty dirty set that passed the clean-tree gate. Branch and root probes around it keep their non-git fallbacks; only the clean-tree claim needs proof.
- `detect_conflicting_wp_status` had no production caller and is deleted rather than migrated.

## WP05 review folds (agent command sites)

- Gate byproduct enrolment is fail-closed. A dirty-path snapshot has three states: known-clean `()`, known-dirty `(...)`, unknown `None`. Enrolment needs both before and after snapshots known, because the abort compensator unlinks anything enrolled as absent-before; a failed before-probe used to make every pre-existing user file look like a byproduct. Advisory callers that only widen test scope may degrade unknown to empty.
- A rename or copy entry names two paths, so every consumer judges both sides (dossier snapshot filter) or stages both sides (`_lane_deliverable_paths`), never just the destination.
- Finalize tests patch the named probe `_finalize_candidates_dirty`, not the generic `kernel.git.status_entries`, which leaked into every real-git caller sharing `_common_patches`.

## WP07 review folds (policy, post-merge, migration, upgrade)

- `commit_guard_hook` now fails closed when it cannot list staged files (it used to exit 0 on any git error, and `--name-only` quoted `kitty-specs/café…` so the prefix check never matched). The policy is loaded first, so a disabled guard never blocks on a failed probe.
- `mission_state._assert_git_safe` skips registered worktrees whose directory is gone (nothing to protect there) and wraps other git failures as `MissionStateRepairError`, so `doctor mission-state --fix` refuses cleanly instead of tracing back.
- `--full-name` paths are repository-relative, so any follow-up command runs from the top level: the `m_3_2_5` untrack step (`git --literal-pathspecs rm --cached` from `rev-parse --show-toplevel`) and `stale_assertions` path resolution. Pinned with subdirectory-project tests.
- Base-red, not ours: `tests/upgrade/test_mission_corpus_recovery.py` (11 failed on both e10f947e~1 and lane-g in the same environment).

## WP03 review folds (merge and coordination seams)

- A staged rename is exempt from the post-merge porcelain invariant only when both sides are exempt; an expected destination can no longer hide a deleted source (the old text form never matched, so renames always offended).
- A git read failure in the squash projection proof or the post-merge porcelain invariant now takes the existing refusal path (restore, `typer.Exit(1)`, `_report_rollback`) instead of a traceback or a yellow "skipped" warning. Rollback stays single-authority (`rollback_to_snapshot`).
- The coord-window probes (`_post_checkpoint_commit_shas`, `_post_checkpoint_mission_paths`) raise `GitCommandError`: an empty result always means "nothing happened", never "could not read".
- `planning_recency` refuses with `GitProbeError` on an unreadable diff (it used to read as "nothing newer on target", which let the squash overwrite target-newer planning artifacts). `stale_check` stays fail-open as advisory, documented at the call.

## Aggregate-review folds

- Intended behaviour change: because `_lane_deliverable_paths` stages both sides of a rename, an owned-checkout auto-commit refuses with `OWNED_DELIVERABLE_SCOPE_REFUSED` when a file outside `owned_files` is renamed onto an owned path (the source's deletion is outside scope). Before, only the destination was judged, so the out-of-scope deletion was hidden. Pinned by `test_owned_review_refuses_a_rename_from_outside_owned_files`.

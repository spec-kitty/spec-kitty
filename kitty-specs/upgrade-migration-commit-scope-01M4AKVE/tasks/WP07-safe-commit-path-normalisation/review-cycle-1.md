---
affected_files: []
cycle_number: 1
mission_slug: upgrade-migration-commit-scope-01M4AKVE
reproduction_command:
reviewed_at: '2026-10-07T16:23:26Z'
reviewer_agent: reviewer-renata
wp_id: WP07
---

# WP07 review, cycle 1: changes requested (reviewer-renata)

Lane: `kitty/mission-upgrade-migration-commit-scope-01M4AKVE-lane-g`, 9a148e333..69254b1d5.

The product code holds up. I re-ran the red-first pairs, probed it against real git in scratch repos, re-ran 9 mutants and ran the gates (details at the end). There is one required change. It is about where a test lives, not what the code does.

## Required change (blocking)

### R1. Move the FR-022 upgrade e2e under `tests/upgrade/`, so it runs on every PR

The orchestrator does not accept the file as placed. FR-022 is part of the #5443 P0 guarantee, so its end-to-end test must run on every PR. Today it runs only nightly.

- `tests/integration/upgrade/test_upgrade_carries_migration_untracks.py` sits in a new `tests/integration/upgrade/` directory.
- `.github/ci-module-registry.yml:691` (commit 69254b1d5) adds `tests/integration/upgrade` to `out_of_matrix_test_dirs`. That makes it nightly-only.

Do this:

1. Move the module to `tests/upgrade/`, next to WP01's #5443 modules (`test_upgrade_commit_scope_5443.py`, `test_upgrade_commit_outcomes_5443.py`). Those run per PR through the `upgrade` module row (`shard_count: 4`). A suggested name is `tests/upgrade/test_upgrade_carries_migration_untracks_5443.py`. Its imports already come from `tests.upgrade._legacy_upgrade_fixture`, so they stay as they are.
2. Delete `tests/integration/upgrade/__init__.py` and the `tests/integration/upgrade/` directory.
3. Revert the `.github/ci-module-registry.yml` edit (the `- tests/integration/upgrade` line). The file then matches 9a148e333 byte for byte.
4. Keep the markers. Module level is `pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.regression]`. The `tests/upgrade` 5443 e2e files use module-level `git_repo` + `non_sandbox`, with `regression` on each test; module-level `regression` is equivalent. Do not add `p0_repro`.
5. Update the T040 targeted command list and the Activity Log to the new path. Record it as a new file in `tests/upgrade/`, and record that the registry edit was reverted. That clears the out-of-map entry for the registry.

I simulated these steps in a scratch tree: moved the module, deleted the package and restored the registry file from 9a148e333. Then `tests/architectural/test_module_shard_registry.py` plus the moved module gave 30 passed, so the move needs nothing else. Run that pair again after the move, along with `tests/upgrade/test_upgrade_auto_commit_unit.py` (WP01's protected file).

## Minor findings (not blocking; fix them in this cycle if they are cheap)

### m1. With an inherited `GIT_INDEX_FILE`, the temporary index can land in the work tree

`src/specify_cli/git/commit_helpers.py:959-967`, `_temp_index_path`: `git rev-parse --git-path index` honours `GIT_INDEX_FILE`. When the caller's env carries `GIT_INDEX_FILE=<somewhere>`, the temporary index is created beside that file instead of under `$GIT_DIR`. I reproduced both cases:

- `GIT_INDEX_FILE=<outside>/alt.idx` puts the temp file at `<outside>/spec-kitty-index-deletions.*.tmp`;
- `GIT_INDEX_FILE=<repo>/alt.idx` puts it at `<repo>/spec-kitty-index-deletions.*.tmp`, inside the work tree, for the whole commit. The pre-commit hook can see it as an untracked file.

The M7 mechanism requires the file to be "under `$GIT_DIR` ... never in the work tree". The commit is still correct, and the file is cleaned up. Suggested fix: derive the directory from `git rev-parse --absolute-git-dir`, or run the probe with `GIT_INDEX_FILE` removed from its env. Add one case to `test_an_inherited_git_index_file_is_the_operators_index_and_never_leaks` that places `alt.idx` inside the repo and asserts that the hook's `$GIT_INDEX_FILE` lies under `.git/`. Today that test checks `_no_temp_index` only under `.git`, so it cannot see this.

### m2. Mutant E survives: the symlinked-directory guard in `_expand_arguments` is never tested on its own

`src/specify_cli/cli/commands/safe_commit_cmd.py:198` is `if path.is_dir() and not path.is_symlink():`. Mutating it back to `if path.is_dir():` leaves all 12 tests in `test_safe_commit_paths_5401_5671_4722.py` green. The guard is currently redundant: the expansion now filters a whole-repo status by `GitPath` containment and no longer calls `.resolve()`, so `linkdir` expands to itself. Either assert that the JSON payload has no `expansion` entry for `safe-commit linkdir`, so the guard is pinned, or record E as equivalent in the Activity Log.

### m3. A batch with one unknown path names our reason, not git's

For `safe-commit ok.md typo.md`, the new `_refuse_unknown_paths` refuses before staging: `Unknown path (not on disk and not known to git): typo.md`. git's `did not match any files` is reached only on the in-process `safe_commit` route. FR-018 reads "names that path and git's reason". `test_batch_with_one_bad_path_names_it_and_commits_nothing` accepts either text (`or "Unknown path" in err`), so it cannot tell the two apart. The path is named and nothing is committed, which is acceptable to me. State the deviation in the Activity Log, or narrow the assertion to the route you intend.

### m4. Router helpers now raise `OSError` on a symlink loop instead of `RuntimeError`

`src/specify_cli/coordination/commit_router.py:1319` (`_is_directly_in_worktree`) and `:1950` (`_relpath`): with a looping path, on 3.11 the base raised `RuntimeError` (from `Path.resolve`) and the tip raises `OSError(ELOOP)`; on 3.13 the base returned silently. `_relpath` is called from the except-arm renderers `_safe_commit_error_result` and `_safe_commit_unchanged_result`, where a cosmetic helper should not raise. Low reach, since router paths come from internal writers. Consider `except (ValueError, OSError)` in `_relpath`; `test_loop_aware_resolution` allows catching `OSError` generically. Otherwise note it in the Activity Log.

### m5. Directory expansion now reads the status of the whole repo

`safe_commit_cmd.py:156` now calls `status_entries(repo_root, untracked="all")` with no pathspec, on every directory argument. The reason is sound: git pairs a rename only when both sides are in scope. But in a repo with a large untracked tree the cost moves from the size of the directory to the size of the repo. Not blocking. One sentence in the docstring or the Activity Log is enough.

## What I verified (no action needed)

**A. Red first.**
- T037 at 21fd0fee9: 10 failed, 2 passed. Every failure is a behavioural assertion: `docs/old.md` still in HEAD, link mode not 120000, `['link.md','other.md']`, crossing renames exiting 0, `typo.md` exiting 0. At b60f25a71: 12 passed.
- T044 at 959e7ccba: 3 failed (`('D', SKILL)` missing from the upgrade commit); the rejecting-hook control passed. At 973b77f62: 4 passed.

**B. Real git, independent probes.**
- #5401: an in-directory rename is committed as `R100` and leaves nothing staged. A crossing rename in either direction exits 1, names the outside path, and leaves HEAD and the index unchanged. `docs2/` is not treated as under `docs/`.
- #5671: relative, absolute, re-pointed tracked and via-directory links are all committed as 120000. The target's WIP stays uncommitted and the operator's work is unchanged. A symlinked directory is committed as one 120000 entry, never expanded. A loop in the leaf or in a parent exits 1 with nothing changed.
- #4722: a lone unknown path exits 1 and names it. In a batch, nothing is committed or left staged. A deleted tracked file, unstaged or staged, is still accepted.
- T044:
  - The upgrade commit equals `D a.md` plus the requested add.
  - The operator's staged add, staged deletion and partial stage are byte-identical in `ls-files -s` and `diff --cached`, apart from the committed paths. The work-tree diff is unchanged.
  - The hook sees only the commit's diff.
  - A rejecting hook leaves HEAD, the real index bytes, the file and the temp index all as before.
  - The temp index is removed after success, after `SafeCommitStagedTreeUnchanged` and after a staging failure.
  - An inherited `GIT_INDEX_FILE` does not leak into the commit or back into `os.environ` (see m1 for the placement problem).
  - A deletions-only commit to protected `main` with STANDARD is refused (`ProtectedBranchRefused`) and allowed with UPGRADE_BOOKKEEPING. A `.worktrees/` deletion is refused (`SafeCommitPathPolicyError`). An empty call is refused (`SafeCommitEmptyChangeset`).

**C. Gate safety.** The temp-index `["git","-c","commit.gpgsign=false","commit","-m",message]` (commit_helpers.py:1039) is inside `_commit_with_index_deletions`, a private top-level helper that `safe_commit` calls directly by name. Under WP05's `CANONICAL_OWNERS` rule it is therefore exempt, and it gives WP05's positive control its hit.

**D. Mutants.** 8 of 9 killed, E survived (see m2):
- killed: B (preflight follows the leaf), D (rename source dropped), N (commit from the real index);
- killed, my own: no temp cleanup, no real-index sync, `--no-verify`, leaf loop probe removed, collector ignores the baseline.

**E. Gates.**
- WP list + `tests/kernel` + `tests/git_ops` + `tests/coordination`: 1829 passed, 5 skipped.
- 11 architectural suites: 350 passed.
- ruff, format and C901 (≤15) clean.
- mypy: one error, `commit_router.py:936` no-any-return, also present at 9a148e333 (pre-existing).
- tests/upgrade: 1112 passed, 46 failed, 2 skipped. The 46 are preview/CLI-contract failures (`test_preview_oracle`, `test_upgrade_preview_acceptance`, `preview_support/test_public_witnesses`, `test_upgrade_cli_contract`). The same 46 node ids also fail at 9a148e333, so they are pre-existing and not caused by this WP.

---
affected_files: []
cycle_number: 1
mission_slug: upgrade-migration-commit-scope-01M4AKVE
reproduction_command:
reviewed_at: '2026-10-07T13:45:34Z'
reviewer_agent: reviewer-renata
wp_id: WP04
---

# WP04 review feedback (reviewer-renata), cycle 1: changes requested

Overall the fix is close. Red→green is clean (7/7 red at f649c95fd for content, branch or bytes reasons; green at 828dece16). The seam (`commit_merge_bookkeeping(destination_ref_override=target_branch)`), the restore-on-refusal, the `--only … --` temp-worktree argv, the ratchets, ruff, mypy and complexity are all fine. 7 of 8 mutants are killed. One spec gap blocks approval, and it is also a regression against the pre-fix code.

## MAJOR-1: an untracked or gitignored `meta.json` on the primary checkout is still committed (FR-010, US5 scenario 2)

`src/specify_cli/consolidation/mission_number/bake.py:300`, in `_primary_checkout_refusal`:

    if status_entries(main_repo, pathspecs=(rel_meta.as_posix(),), untracked="no"):

With `untracked="no"`, a `meta.json` that is **not tracked in HEAD** looks clean. The bake then read-modify-writes the operator's file, and `safe_commit` stages it with `git add --force` and commits it onto `main`. I reproduced both cases on real git through `_bake_mission_number_into_mission_branch`:

1. **Untracked `meta.json`** (operator content `"secret_note": "operator-only"`, never committed). Result: `chore(...): assign mission_number=1 (primary tree)` lands on `main` and adds the whole file, operator bytes included. No unbaked warning. The pre-fix code did the same. It still violates US5 scenario 2 ("`meta.json` differs from HEAD → nothing is committed") and FR-010 ("with my own `meta.json` edit pending it commits nothing"), because an untracked file differs from HEAD.
2. **Gitignored and untracked `meta.json`** (`.gitignore: kitty-specs/`). This is a **regression**. Pre-fix (f649c95fd): `git add` refused the ignored path, so the number was reported unbaked and nothing was committed. Post-fix (828dece16): `safe_commit`'s `add --force` commits the ignored file onto `main`, with no warning.

Requested fix (product): refuse unless `meta.json` is tracked in HEAD and clean. Either of these works:
- `status_entries(main_repo, pathspecs=(rel,), untracked="all", ignored=True)` non-empty → refuse; or
- keep the current status check and also refuse when `kernel.git.tree_entry(main_repo, "HEAD", rel)` is `None`, with a reason like `f"{rel_meta} is not tracked on {target_branch!r}"`.

Refusing is safe: per #4900 the number is still returned and the executor writes and verifies it on the target tree.

Requested tests (`tests/consolidation/test_bake_commit_scope_meta_only.py`): add two red-first cases next to `test_primary_bake_refuses_when_meta_has_operator_edit`:
- untracked `meta.json` (the mission branch is cut from root and `meta.json` was never committed);
- gitignored and untracked `meta.json`.

For each, assert the following: `main`/HEAD do not move, the on-disk bytes are unchanged, the file is still untracked, and the unbaked warning is printed. The WP prompt prescribed `untracked="no"`, so this is a planning-level hole that you inherited, not a deviation on your part. It still has to close here because FR-010 and US5 say "differs from HEAD".

## MINOR-1: no T022 evidence recorded

The WP Activity Log has no RED/GREEN output, no `git grep -nE '"commit"'` gate-readiness output for WP05, and no WP08 changelog draft bullet (T022 steps 3–5). The for_review event carries no note. Add them when you resubmit.

## NOTE-1: equivalent mutant on the branch/detached precheck (no action required)

`bake.py:296-299`: dropping the detached/other-branch checks leaves every test green. `safe_commit`'s HEAD assertion raises `SafeCommitHeadMismatch`, and the `except` then restores the bytes. Behaviour is protected by two layers, so this is acceptable. If you want the precheck itself pinned, assert the refusal reason (`"detached HEAD"` / `"not the merge target"`) in the two refusal tests.

## NOTE-2: a `status_entries` failure now propagates

`bake.py:300`: if `status_entries` fails (a git failure in `kernel.git`), the exception propagates out of the bake. The old `git add` failure path surfaced the number as unbaked instead. This is low risk. Consider catching it and surfacing it as unbaked.

## Verified OK
- (A) RED: 7 failures at f649c95fd, all on assertions: scenario 3 lists `src/staged.py`; on operator-topic and detached HEAD, `head` moves and `meta.json` gets `mission_number: 1`; the operator-edit cases commit `"note": "mine"`; the temp-worktree argv lacks `--only`. GREEN: 7/7 at 828dece16.
- (B) `commit_merge_bookkeeping` → `CommitTarget(ref=target_branch)` → `safe_commit` preflight asserts HEAD == target (detached shows as `<detached>`), `MERGE_BOOKKEEPING` authorises the protected `main`, and `commit --only -- paths` is used. A hook rejection raises `RuntimeError`; `safe_commit` restores the index and the bake restores the exact bytes (pinned by the hook test). A staged rename into `meta.json` and an intent-to-add `meta.json` are both refused correctly.
- (C) `commit --only -m … -- <rel_meta>` in the fresh detached temp worktree commits exactly `meta.json`. The C-005 exception comment is present.
- (D) No `MERGE_BOOKKEEPING` in `consolidation/`. `git grep -nE '"commit"|"add"'` shows only the `--only … --` argv plus two `worktree add`. Results: 303 passed, 1 skipped across the guard-capability, destructive-op, layer-rules, path-listing-owner, inline-meta, exemption-ratchet and terminology suites; 5 passed for `-k load_meta`.
- (E) Mutants killed: bare commit, no dirty check, index-only dirty check, commit on the current branch, no restore, temp-worktree bare commit, directory pathspec. The seven `test_ordering_bake_seam.py` edits only add `target_branch="main"`.
- (F) ruff, format, C901 ≤ 15 and mypy are clean. The 7 consolidation suites pass (74 passed).

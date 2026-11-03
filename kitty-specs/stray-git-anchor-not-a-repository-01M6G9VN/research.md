# Research: a stray `.git` that is not a repository is not an anchor

Mission: `stray-git-anchor-not-a-repository-01M6G9VN` · Issue: #7093 · Recorded after
grounding, implementation and review, so the record matches what was actually decided.

## Decisions

1. **The assertion is right; the shared anchor test is wrong.** The reported red,
   `tests/upgrade/migrations/test_m_2_0_6_consistency_sweep.py::test_apply_repairs_feature_state_and_legacy_prompt_refs`,
   asserts the frozen sweep's documented repair: a Mission folder with no `meta.json`, outside
   any git checkout, gets a baseline `meta.json` with the inferred `target_branch` and
   `mission_type`. That is what the sweep does on a host with no `.git` above its temp root —
   verified by running the same test with `--basetemp` outside `/tmp` (2 passed).
   `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py::test_nothing_tracked_is_not_a_refusal`
   asserts the same contract at the seam, and is red for the same reason. Two independent
   tests, one contract, so the assertion is not the thing to change.

2. **The frozen migration is not the fix site.** `2.0.6_consistency_sweep` is byte-frozen
   (`DIRECTIVE_044`; `SUPERSEDED_MIGRATIONS` maps it to `2.0.6_residue_safe_consistency_sweep`),
   so its bytes are its `content_hash`. The behaviour it exhibits is produced by
   `specify_cli.upgrade.feature_meta.build_baseline_feature_meta`, which asks
   `specify_cli.mission_metadata.read_tracked_meta` "what does git hold" — and that answer was
   wrong.

3. **An anchor is a repository, not a name.** `_has_no_git_anchor` counted any `.git` entry at
   or above the folder. This host has `/tmp/.git`: a directory with `hooks/` and no `HEAD`,
   the shape the literal-`.git/hooks` writer of #5756 leaves behind. git answers
   `fatal: not a git repository` for every path below it, which is correct. The anchor test
   converted that into `TrackedMeta(None, unavailable=True)` — the refusal that means *git
   tracks this path but cannot give it back* — so `build_baseline_feature_meta` returned
   `None`, the sweep reported `wrote baseline meta.json` and wrote nothing, `detect()` stayed
   true forever, and the successor seam told the operator to `git checkout --` a path git does
   not track.

4. **The narrowed predicate keeps every refusal.** A `.git` *file* (worktree/submodule/
   separate-git-dir pointer) is an anchor even though the caller may not read it; a `.git`
   *directory* is an anchor only when it holds `HEAD`; any `OSError` other than "not found"
   reads as an anchor (fail closed). The walk continues past a non-repository `.git`, so a
   stray entry never shields a real repository above it.

5. **The probe is one seam.** The anchor walk calls `Path.lstat()` (not `os.lstat`) and
   `Path.stat()` on `HEAD`, so the repository's own EACCES helper
   (`tests/_support/eacces.py::deny_path_method`) can deny each seam without `chmod`, whose
   verdict differs between a regular uid and root (#5622, #5691).

## Evidence

- Red before, green after, same assertions: the reported test and
  `test_nothing_tracked_is_not_a_refusal` on `d18c4f1d58` with `/tmp/.git` present.
- Both pass at `d18c4f1d58` when pytest's basetemp is outside `/tmp`, which is why CI was green
  while this host was red: the defect needs an ancestor `.git` that is not a repository.
- `git rev-parse --is-inside-work-tree --show-prefix` in `/tmp` exits 128 with
  `fatal: not a git repository (or any of the parent directories): .git`, while
  `_has_no_git_anchor` still answered "anchor" for `/tmp/.git`.
- `spec-kitty migrate ledger` drift is untouched: no file under
  `src/specify_cli/upgrade/migrations/` changed (`git diff origin/main -- src/specify_cli/upgrade/migrations/`
  is empty).

## Open questions

- The frozen sweep still claims a write for a *genuine* refusal (a tracked copy git cannot
  produce). That path lives in the frozen module and cannot be corrected there; its successor
  `2.0.6_residue_safe_consistency_sweep` already reports the refusal honestly and skips the
  Mission, so no follow-up is filed for it. Recorded as C-004 in the spec.
- #5756 (the literal-`.git/hooks` writer that leaves a stray `/tmp/.git` behind) is a separate
  defect and stays with its own issue; this fix only stops a stray `.git` from breaking a
  repair.

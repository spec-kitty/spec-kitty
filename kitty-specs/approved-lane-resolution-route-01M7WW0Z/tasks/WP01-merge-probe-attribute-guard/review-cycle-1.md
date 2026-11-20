---
affected_files: []
cycle_number: 1
mission_slug: approved-lane-resolution-route-01M7WW0Z
reproduction_command:
reviewed_at: '2026-11-20T19:41:33Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP01
---

# WP01 review feedback (cycle 1) — reviewer claude::reviewer-renata (session_019C2Tk5ehA3TXonKhbxbaMR), verdict REJECT, commits 5354775e + 1f29e11d

## Holds
These checks hold: union, unknown drivers, merge.default, user merge.text/binary.*, registered name on the wrong pattern, wrong command, .recursive; committed `[attr]` macros; check-attr input hardening; attribute sources match the probe's; the committed-union rule (a); the per-run version cache; deletions, mode changes and renames in the changed paths; config read through `--get`.

Test results: guard 88 passed; tests/consolidation 3581 passed; tests/lanes 1196 passed; arch gates 212 passed; static checks clean.

## Must fix
1. (HIGH, laundering reproduced) A clone-local `merge.renormalize=true` plus a clean `filter` passes the guard and makes both probes accept hand content.
   - Where: `merge_attribute_guard.py:282-304`, `git_probes.py:772` (`merge_own_changed_paths`) and `:989` (`n_way_merge_blob`).
   - Repro (git 2.43): hand-edit line 3 of `f` to EVIL in merge M. Put `* filter=evil` in `.git/info/attributes`, set `filter.evil.clean "sed s/l3/EVIL/"`, `filter.evil.smudge cat` and `merge.renormalize true`.
   - Result: `merge_own_changed_paths(repo, M)` returns `[]` and `n_way_merge_blob([M^1, M^2], 'f')` returns the hand blob. The env form (`GIT_CONFIG_COUNT` / `KEY_0=merge.renormalize` / `VALUE_0=true`) works too.
   - Fix, fail closed:
     - refuse when the effective `merge.renormalize` is true (`git config --get --type=bool`, all scopes plus env);
     - refuse when any probed path has an effective `filter`, `ident` or `working-tree-encoding` attribute, checked in the same batched call: `check-attr --stdin merge filter ident working-tree-encoding`.
   - Tests: real git, both probes, with the setting in a config file and via `GIT_CONFIG_COUNT`.
2. (MED) Other clone-local merge config is unguarded.
   - `merge.directoryRenames=true` turns a default file-location conflict into a clean merge: `merge-tree` exits 1 by default and 0 with the setting, so `n_way_merge_blob` reads a should-be-conflicted path as clean.
   - `merge.renames` and `diff.algorithm` also change what the automatic merge is.
   - Fix: pin the probe-relevant config on both probe invocations: `-c merge.directoryRenames=conflict -c merge.renames=true -c diff.algorithm=myers -c merge.conflictStyle=merge`. Refusing when any is set is also acceptable. Add one test per key.
   - Expose ONE shared helper (attribute and config pinning or refusal) so that WP08's incorporate merge (delivered via WP07) and the WP10 printed review command cannot drift. Keep it out of `__all__` until a src consumer exists, per the dead-symbol rule 2: referenced inside its own module.
3. (LOW) Correct the red-first record. The 1f29e11d tests against the 5354775e^ sources give 85 failed and 3 passed. Label the 3 passing tests as controls: `test_an_attribute_on_another_path_does_not_refuse`, `test_n_way_merge_blob_single_commit_is_not_guarded` and `test_merge_set_passes`.

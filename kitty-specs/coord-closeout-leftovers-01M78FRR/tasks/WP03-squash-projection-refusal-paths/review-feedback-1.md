Most of WP03 holds. Red is real at 28d6f048: collection fails with `AttributeError: ProjectedPathReason`. Green is real on the lane: 273 passed across the five target files and the gates `test_no_dead_symbols`, `test_merge_reconciliation_class_guard`, `test_layer_rules` and `test_single_rollback_authority`. ruff, C901, `format --force-exclude` and mypy are clean on the changed files. The phrase is kept, the cap is 20 with "and N more", remedies are deduplicated, the code line is `Error code: SQUASH_PROJECTION_NOT_LANDED.`, exit 1 is unchanged and the constant is pinned. The return-shape refactor gives the same verdicts: each `return False` maps to one reason, `all()` becomes a full loop, and no new exception can escape, because `_read_git_blob_bytes` never raises. `MergeDriverNotRegisteredError(GitProbeError)` keeps every existing `except GitProbeError` working, and no code matches on message text or checks the exact type. Three findings block approval.

**Issue 1 (blocking): the allowlist grows, and the debt has no owner or drain date.**
`projected_content_matches_target` now has no `src/` caller. The fix adds a `dead_symbol_allowlist.yaml` entry (225 → 226 entries) with `issue: '#5867'`. #5867 is the issue this WP closes, so the entry is debt with no open tracker, owner or drain date. That breaks charter SO 5 and Burn-down Policy (a). The gate passes only because the baseline (231) has headroom. The `_baselines.yaml` history shows the precedent: "deleted the dead X instead of allowlisting them" (#6614, the #6164 landing fold).
The wrapper is a one-line `not unlanded_projected_paths(...)`. Its callers are tests only:
- `tests/terminus/test_repro_5038.py`
- `tests/coordination/test_projection_teardown.py`
- `tests/consolidation/test_projection_excludes_plan_outputs.py`
- `tests/consolidation/test_bookkeeping_projection_seam.py`
- the new test file

Under SO 4 these callers are stale tests, so re-pin them.
Fix:
- Delete `projected_content_matches_target` and its `__all__` entry.
- Re-pin each `assert projected_content_matches_target(...)` to `assert unlanded_projected_paths(...) == []`.
- Re-pin each `assert not projected_content_matches_target(...)` to an assertion on the expected `(path, reason)`. This makes the #5038 reproductions stronger: P2 then pins `MERGE_DRIVER_MISMATCH`, not just "some failure".
- Drop the allowlist entry.
- Update the docstrings that cite the old name: `test_repro_5038.py:36,160`, `test_projection_teardown.py:22`, `test_projection_excludes_plan_outputs.py:11`, and the `CHANGELOG` fixture is historical, so leave it.

This is leeway outside `owned_files`. Record it in the WP history as you did for `git_probes.py`.

**Issue 2 (blocking): the NO_MERGE_DRIVER remedy (`run spec-kitty upgrade`) is untrue.**
`driver_replay_expected_bytes` resolves the driver inside `_ephemeral_merge_driver_activation`. That call seeds every `_MERGE_DRIVERS` attribute line into `$GIT_COMMON_DIR/info/attributes` and defines the git config for the duration of the check. So the verdict does not depend on whether this clone ran `spec-kitty upgrade`. Your own test `test_a_diverged_path_whose_landing_is_the_driver_output_is_landed` resolves the traces driver in a repo with no `.gitattributes` and no upgrade.
NO_MERGE_DRIVER therefore means the path kind has no driver in the registry. The projected kinds that have no driver by design are notes, verdicts and other kitty-specs files. The registry covers `status.events`, `decisions.events`, `meta`, `traces/*.md`, `acceptance-matrix`, `issue-matrix`, `review-cycle-*` and `decisions/index.json`. Your `_NOTE` cell is exactly that case, and `spec-kitty upgrade` cannot change it. The WP asked you to verify this remedy against how drivers are installed.
Fix: make the remedy name what the operator can do. Both sides changed a path that has no merge driver, so make the target's copy match the coordination branch (or reconcile the two by hand on the target), then re-run `spec-kitty consolidate`. Drop the `spec-kitty upgrade` clause. Update `test_each_reason_has_its_own_remedy` to match.

**Issue 3 (blocking): "The landing was rolled back" is false on one reachable path, and the FR-014 comment overclaims the same way.**
`_phase_reconcile_before_teardown` calls `_assert_squash_projected_content_landed` in two places. One of them is the `_resume_reconciliation_already_passed(run)` branch: a `--resume` whose target tip carries a persisted PASS anchor. If the proof refuses there, the rollback authority deliberately keeps the landing (`rollback.py:703-708`, `refused_verified_landing`, which prints "Kept the landing verified by an earlier reconciliation; nothing was rolled back"). The refusal printed just before it says "The landing was rolled back", so the operator gets two contradictory lines.
The refusal can fire on that branch in two ways:
- a transient PROBE_FAILED on the re-run;
- the coordination branch moved after the earlier PASS, which brings in new projected paths.

The new comment says the door "restores the target to its pre-run snapshot like any other post-mutation failure", which is likewise not true for that branch.
Fix (either option):
- (a) Drop the rollback claim from the refusal text and let the rollback door's own report state the outcome. For example: "Nothing was torn down; the rollback outcome follows."
- (b) Pass the call site in and word the text conditionally.

Correct the comment to name the verified-landing exception, and add a gate-level test for the already-passed branch.

**Non-blocking observations (fix them if cheap, otherwise record them as residuals in the WP history):**
- `_resolve_merge_driver_config_key` also returns `None` on a non-zero `git check-attr` exit, so a transient probe failure surfaces as NO_MERGE_DRIVER, a deterministic cause. The new class's docstring says it separates the two. Narrow the claim, or raise a plain `GitProbeError` on the non-zero exit.
- Some deterministic driver-side failures surface as PROBE_FAILED, "re-running may succeed": a driver raising on malformed content (`RowMatrixMergeError`), "no merge-driver registry entry for config key" (a stale committed `merge=` key), and an unrecognized command shape. Those clash with the ruling that deterministic causes say what to change. At a minimum, word PROBE_FAILED as "may succeed if the failure was transient; if it repeats, …".

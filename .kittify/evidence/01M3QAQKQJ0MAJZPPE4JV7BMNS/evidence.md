# Red proofs, slice A (tests/consolidation)

Implementer: python-pedro. Op `01M3QAQKQJ0MAJZPPE4JV7BMNS`. Tracker: #5353.
Worktree: `.claude/worktrees/agent-ae6ed991457e928fe`, branch `worktree-agent-ae6ed991457e928fe`, base `5c8d24d02b` (`issue-5353-consolidation-test-quality`).
Input: `verdicts-A.md`.

Every break below was planted in `src/` with an exact single-occurrence replace, run, and reverted with `git checkout -- src/`. Each break was planted on its own, except the two `_render_stale_findings` message deletions (L860/L864). They were planted together because each test reaches only one of the two lines. `git diff --stat src/` was checked before every commit. The only `src/` changes committed are the grade-label escape and the docstring fix.

Command form: `PYTHONPATH=<worktree>/src .venv/bin/python -m pytest <nodeid> -q -p no:cacheprovider`.

## FIX

| Test (verdict line) | Planted break | Current test on break | Fixed test on break | Fixed test on real code | Verdict change |
|---|---|---|---|---|---|
| executor_coverage L872 `test_render_stale_findings_all_grades` | none needed: live product defect (Rich swallowed `[high]`/`[medium]`/`[low]`/`[info]`). Regression breaks: (a) the unescaped original code, (b) `actionable = [...]` → `actionable = []` | green (no oracle) | RED on the unescaped code (output `   test_x.py:10 — ...`, no label); RED on (b) | green after `rich.markup.escape` fix (`_stale_finding_line`) | none. Note: order inside the actionable group follows input order (there is no severity sort), so the test asserts group order only: actionable < info block < low |
| executor_coverage L860 `test_render_stale_findings_none_report` | `executor.py::_render_stale_findings`: delete the `could not run` `console.print` | green | RED | green | none. Folded with L864 into `test_render_stale_findings_short_circuit_states_are_named[check-could-not-run]` |
| executor_coverage L864 `test_render_stale_findings_no_findings` | `executor.py::_render_stale_findings`: delete the `No likely-stale assertions detected.` `console.print` | green | RED | green | none. Folded as `[no-findings]` |
| executor_coverage L179 `test_phase_merge_lanes_resume_tolerates_already_merged` | `executor.py::_phase_merge_lanes`: `if run.is_resume and already_merged:` → `if already_merged:` | green | RED (`[fresh-run-fails]`) | green | none. Renamed `test_phase_merge_lanes_already_merged_tolerated_only_on_resume`, parametrized |
| executor_coverage L338 `test_handle_result_resume_tolerates_already_merged` | `executor.py::_handle_mission_merge_result`: drop `run.is_resume and` from the tolerance condition | green | RED (`[fresh-run-fails]`) | green | none. Renamed `test_handle_result_already_merged_tolerated_only_on_resume`; the fresh case asserts Exit(1) and a restore |
| executor_coverage L706 `test_phase_push_success` | `executor.py::_phase_push`: push argv `target_branch` → `mission_branch` | green | RED (origin held `refs/heads/kitty/mission-m`) | green | none. Renamed `test_phase_push_publishes_the_target_branch_to_origin`; real bare remote with both branches present at different shas |
| terminus_integrity L294 `test_enforce_resume_anchor_fresh_is_noop` | `executor.py::_enforce_resume_anchor_integrity`: delete `if not run.is_resume: return` | green | RED (H4 refusal Exit 1) | green | none |
| terminus_integrity L302 `test_enforce_resume_anchor_non_coord_is_noop` | `executor.py::_enforce_resume_anchor_integrity`: drop `coord_topology and` from H4 | green | RED (H4 refusal Exit 1, message confirmed) | green | none |
| bootstrap_history_gate L131 `test_gate_skips_when_no_wp_ids` | `preflight.py::_enforce_canonical_status_history`: delete `if not wp_ids: return` | green | RED (Exit 1) | green | none. Landed before the L507 retirement |
| preflight_seam L573 `test_warn_or_confirm_noop_without_warnings` | `preflight.py::_warn_or_confirm_hollow_reviews`: delete `if not warnings: return` | green | RED (Exit 1 from the declining forced-interactive prompt) | green | none. Now uses a real empty feature dir, no collector mock |
| done_bookkeeping L450 `test_mark_wp_merged_done_warns_when_wp_file_missing` | `done_bookkeeping.py::_mark_wp_merged_done`: `if wp_path is None:` → `if False:` | green (the verdict's UNSURE is resolved: it did not go red by accident) | RED (the missing-file warning is absent) | green | none |
| done_bookkeeping L463 `test_mark_wp_merged_done_noop_when_already_done` | `done_bookkeeping.py::_mark_wp_merged_done`: delete `if lane == _Lane.DONE: return` | green | RED | green | none. The spurious warning under the break is `WP01 has no recorded approval metadata`, not `is in lane 'done', not approved` as the verdict predicted. The oracle is "no `Warning`", so the test catches both |
| done_bookkeeping L546 `test_mark_wp_merged_done_warns_when_lane_not_approved` | `done_bookkeeping.py::_mark_wp_merged_done`: `if lane != _Lane.APPROVED:` → `if False:` | green (the verdict's UNSURE is resolved: no crash on real I/O) | RED (warning absent) | green | none. The emit is now patched (it ran live before) |
| done_bookkeeping L576 `test_mark_wp_merged_done_aborts_when_replay_returns_none` | `done_bookkeeping.py::_mark_wp_merged_done`: `if replay_result is None: return` → `replay_result = (lane, _force_done)` | green | RED (done emit called once) | green | none. The resolved lane is now APPROVED |
| merge_unit L101 `test_missing_source_dir_no_error` | `runtime/merge.py::merge_package_assets`: `shutil.rmtree(dst, ignore_errors=True)` as the first line of the managed-dir loop | green | RED (dest tree changed) | green | none. Renamed `test_empty_source_leaves_dest_managed_assets_intact`. The file still sits in the wrong directory (it belongs under `tests/specify_cli/runtime/`); I did not move it (out of scope) |

## Sibling blind spots named by the verdicts

| Test | Planted break | Current test on break | Fixed test on break | Fixed test on real code | Outcome |
|---|---|---|---|---|---|
| `tests/specify_cli/cli/commands/test_merge.py::test_mark_wp_merged_done_skips_when_already_done` | same DONE-dedup deletion as L463 | green (vacuous, as the verdict said) | RED (spurious `Warning` printed) | green | FIXED (added the capsys "no Warning" oracle) |
| `tests/consolidation/test_hollow_review_warnings.py::test_warn_or_confirm_hollow_reviews_assume_yes_does_not_prompt` | `preflight.py::_warn_or_confirm_hollow_reviews`: `if assume_yes or not is_interactive():` → `if not is_interactive():` | green (vacuous) | RED (Exit 1) | green | FIXED (forced interactive, declining prompt, asserts no prompt). This is the survivor of the "fix one, retire the other" pair |

## RETIRE

| Test | Covering guard | Break | Covering guard on break | Retiree on break | Verdict change |
|---|---|---|---|---|---|
| preflight_seam L507 `test_canonical_status_history_noop_without_wps` | `test_merge_bootstrap_history_gate.py::test_gate_skips_when_no_wp_ids` (as fixed) | `preflight.py::_enforce_canonical_status_history`: delete `if not wp_ids: return` | RED | green (vacuous) | none |
| preflight_seam L533 `test_canonical_status_history_passes_with_real_history` | `test_merge_bootstrap_history_gate.py::test_gate_allows_real_lane_transition` | `preflight.py::_enforce_canonical_status_history`: `if has_non_bootstrap_status_history(...)` → `if not ...` | RED | RED as well | none. The retiree is not vacuous; it is a duplicate that mocks the gate's own predicate. Retired as redundant |
| preflight_seam L580 `test_warn_or_confirm_proceeds_with_assume_yes` | `test_hollow_review_warnings.py::test_warn_or_confirm_hollow_reviews_assume_yes_does_not_prompt` (as fixed) | `preflight.py::_warn_or_confirm_hollow_reviews`: drop `assume_yes or` | RED | green (vacuous) | **FIX → RETIRE.** The verdict said "fix one and retire the other". The sibling uses real `status.json` data rather than a mocked collector, so it is the better survivor under the test-desiderata styleguide |
| merge_recovery L488 `test_cleanup_tolerates_already_removed_worktree` | `test_merge_workspace_unit.py::TestCleanupMergeWorkspace::test_cleanup_is_idempotent` | `workspace.py::cleanup_merge_workspace`: `if runtime_dir.exists():` → `if True:` | RED (FileNotFoundError) | RED as well | none (a line-for-line duplicate) |
| resume_strategy_authority L165 `test_equal_explicit_does_not_refuse` | `::TestResumeStrategyPrecedence::test_explicit_wins_over_everything_on_resume` and `::test_equal_explicit_and_persisted_is_not_a_flip` | `consolidate.py::_resolve_effective_merge_strategy`: drop `and explicit != persisted` | both RED (MergeStrategyFlipError) | RED as well | none (a subset duplicate) |

## Totals landed

- FIX: 15 of the 16 verdict FIXes, plus 2 sibling FIXes (`test_merge.py` already-done and `test_hollow_review_warnings.py` assume_yes).
- RETIRE: the 4 verdict RETIREs plus L580, which changed from FIX to RETIRE. That makes 5.
- Changed to KEEP: 0.
- Campsite: removed the stale `done_bookkeeping.py:261` and "lines N-M" prose pins in `test_done_bookkeeping_seam.py`, including the KEEP L509 docstring. Replaced the `executor.py` rollback-helper docstring pin `test_merge_state_authority.py:500` with test-class and test-file names.

## Verification (final)

- All touched test files in one run (10 files): **269 passed, 0 failed**. The files: `test_executor_coverage.py`, `test_executor_terminus_integrity.py`, `test_merge_bootstrap_history_gate.py`, `test_preflight_seam.py`, `test_hollow_review_warnings.py`, `test_done_bookkeeping_seam.py`, `tests/specify_cli/cli/commands/test_merge.py`, `test_merge_unit.py`, `test_merge_recovery.py`, `test_resume_strategy_authority.py`.
- `ruff check` on the touched files: all checks passed.
- `ruff format --check --force-exclude` on the touched files: 4 files formatted. The other 7 are on the shrink-only format-exclude ratchet in `pyproject.toml`: `executor.py`, `test_executor_coverage.py`, `test_preflight_seam.py`, `test_hollow_review_warnings.py`, `test_done_bookkeeping_seam.py`, `test_merge.py` and `test_merge_recovery.py`.
- `mypy src/specify_cli/consolidation/executor.py`: 6 `no-any-return` errors, all pre-existing (lines 240, 1508, 1511, 1843, 2018 and 2786). None is on a changed line. The new `_stale_finding_line` is clean.

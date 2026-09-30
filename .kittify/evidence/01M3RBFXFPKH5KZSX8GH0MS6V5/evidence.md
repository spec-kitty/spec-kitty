# red-proofs-S (untracked)

Commands: `uv run --frozen pytest <file> -q -n auto --dist loadfile -p no:cacheprovider`
All breaks planted in src/, reverted with `git checkout -- src/`; `git diff --stat src/` empty before every commit.

## Group 1: test_auth_logout.py

### RETIRE test_logout_impl_is_importable (A)
- Break: `_auth_logout.py` rename `async def logout_impl(` -> `logout_impl_renamed(` and `__all__`.
- Guard: the 9 `TestAuthLogoutCommand` CliRunner tests (each asserts exit code/stdout/delete; not vacuous, all invoke `["logout"...]`).
- Result on break: 10 failed (9 guard tests + the retired test). Guard RED -> retire.

### RETIRE test_logout_local_cleanup_failure_exits_1 (B-G2)
- Break: `_auth_logout.py:87` `raise typer.Exit(code=1)` -> `return`.
- Guard: `test_logout_storage_delete_failure_propagates` (same file, real TokenManager.clear_session, asserts exit_code == 1).
- Result on break: 2 failed, 8 passed: the retired test AND the guard both RED. Guard non-vacuous -> retire.

### Isolation
- Autouse `_isolate` fixture now requests `canonical_home` (SPEC_KITTY_HOME -> tmp_path/home).

## Group 3: charter retirements (B-G3)
Five breaks planted at once (distinct sites), then flagged + guard files run:
`pytest test_charter_bundle_coverage.py test_charter_orchestration.py test_charter_rendering.py tests/charter/test_bundle_validate_cli.py tests/agent/cli/commands/test_charter_cli.py tests/charter/test_context_org_chain.py -n auto` -> 16 failed, 73 passed.
Breaks (line numbers at this base):
1. charter_bundle.py:388 `not tracked_missing` -> `True`
2. charter/interview.py:414 `write_interview_answers(...)` -> `pass`
3. charter/_status_collectors.py:152 `"stale" if stale else "synced"` -> `"stale"`
4. charter/context.py:168 `result.mode` -> `"compact"`
5. charter/context.py:210 `console.print(result.text, markup=False)` -> `pass`
Result per retired test / guard:
- test_validate_exits_zero_when_all_checks_pass, test_validate_json_output_contains_result_key: stayed GREEN (not in failed list). Guard `tests/charter/test_bundle_validate_cli.py::test_validate_fails_on_missing_tracked_file` RED (also `..._when_charter_md_is_untracked`). Non-vacuous (asserts exit code / errors on a real bundle).
- test_interview_defaults_exits_zero_and_writes_answers, test_interview_defaults_json_output: GREEN. Guard `test_charter_cli.py::test_interview_defaults_writes_answers` RED.
- test_status_exits_zero_with_human_output: GREEN. Guard `test_charter_cli.py::test_status_command_synced` RED.
- test_context_json_output_has_success_key: GREEN. Guard `test_charter_cli.py::test_context_bootstrap_then_compact` RED. Attribution check: with break 5 reverted (breaks 1-4 still planted), guard RED, flagged test GREEN (1 failed, 1 passed) -> RED is caused by break 4.
- test_context_exits_zero_for_known_action, test_context_renders_action_name_in_output: these two also went RED on break 5 (they assert the printed text), so they are not blind to that break, but they mock build_charter_context and assert a disjunctive `or "review" in output.lower()`. Guard `tests/charter/test_context_org_chain.py::TestContextCliTwoPackChain::test_pack_two_directive_present_in_cli_text_output` RED on break 5 with a real run. Guard covers the same break -> retire per verdict (guard red is the criterion).
- Unused `import json` in test_charter_bundle_coverage.py removed (ruff F401 --fix). ruff format touched the three files (pre-existing unformatted spans reflowed).
Kept: test_validate_exits_nonzero_when_resolver_raises_not_inside_repo, test_context_json_uses_same_depth..., etc. (test_context_json_uses_same_depth also went RED on the planted breaks; KEEP unchanged).

## Group 6: test_doctor_mission_state.py FIX (B-G6)
- Break: migration/mission_state.py:402 `"quarantine_root_path": self.quarantine_root_path,` -> `None`.
- OLD test (copied from HEAD into an untracked temp file): GREEN (1 passed).
- FIXED test (real RepairReport + MissionRepairResult, product `to_json`): RED (1 failed).
- After `git checkout -- src/`: FIXED test GREEN (72 passed across the 6 files run together).

## Group 9: test_events_tail.py FIX (B-G9)
- Break: events.py after `log_path = mission_event_log_path(...)` insert `open(log_path, "a").write("\n")` (a builtin-open append WRITE).
  Deviation from verdict: the verdict's `open(log_path, "a").close()` writes nothing, so no filesystem-state oracle can see it (size/mtime/bytes unchanged); the write variant is a real mutation and equally invisible to the old `Path.open` spy.
- OLD test `test_no_write_syscall_reachable_on_any_code_path` (temp copy of HEAD file): GREEN.
- FIXED `test_events_tail_leaves_mission_tree_byte_identical_on_every_code_path` (snapshot of paths/sizes/mtime/bytes across happy/usage/not-found/resume-refused): RED. (The append also corrupts the log, so 3 behaviour tests went red in both old and new files; irrelevant to the oracle comparison.)
- After checkout: GREEN.

## Group 4: test_implement_base_flag.py
### FIX test_implement_base_flag_invalid_ref_fails_clearly
- Break: implement.py:1623 `_raise_base_ref_unresolved(base)` -> `return None, lanes_manifest`.
- OLD test (temp copy of HEAD file): GREEN. FIXED test (message via `console.capture()`, no branch, no worktree, real ULID, dead fixture + no-op patches + require_lanes_json patch dropped): RED. After checkout: GREEN.
- ruff.toml: per-file-ignore for this file shrunk `["F401","F841","SIM105","SIM117"]` -> `["F401","SIM117"]` (F841 and SIM105 verified stale by running ruff without the ignore; F401/SIM117 still fire in the untouched sibling test).

## Group 4 (retirements) - guard proofs
NOTE: the implement-base retirement commit (8c9bc5bdb) was committed BEFORE this guard run (order slip in my process); the run below was done afterwards, guard was RED, so the retirement stands. No commit contains a planted break.
Three breaks planted at once (distinct sites); run: old implement-base file (temp copy of a091fc489 version), tests/specify_cli/lanes/test_lane_base_honoring.py::TestAC1SeamLevelRedFirst, tests/cli/commands/test_merge_status_commit.py, tests/cli/test_doctrine_org_commands.py -n auto -> 11 failed, 19 passed.
1. implement.py:2171 `base=effective_base,` -> `base=None,`
   - Retired test_implement_base_flag_creates_workspace_from_ref (old file copy): GREEN (not in failed list; vacuous oracle confirmed).
   - Guard `test_lane_base_honoring.py::TestAC1SeamLevelRedFirst::test_explicit_base_replaces_coord_parent_on_no_dep_lane`: RED. Non-vacuous (divergent base).
2. consolidation/done_bookkeeping.py `_mark_wp_merged_done`: insert `return` before body.
   - Guard `TestRealMergeCommitsBookkeeping::test_status_pair_with_done_event_is_committed_on_target`: RED (also test_real_merge_exits_zero etc.: "merged WPs did not reach done"). Real `consolidate` run, non-vacuous.
   - Retired test_mark_wp_merged_done_uses_lightweight_emit_path and test_modern_coord_done_events_land_on_target_history: also RED on this break; the guard covers it. test_done_events_committed_to_git stays (D2 deferred), also RED.
   - The retired lightweight test's sole assertion (`ensure_sync_daemon is False`) pins a dead sync-residue kwarg (verdict; not re-derived).
3. doctrine.py:1118 `check_drg_root=True` -> `False`.
   - Guard `test_doctrine_org_validate_catches_drg_only_fragment_after_init`: RED (real CliRunner run, asserts drg_root_graph_missing diagnostic). Retired test_doctrine_org_validate_calls_validate_pack_with_check_drg_root_true also RED (it pinned the arg only).
After `git checkout -- src/` all reverted. Unused `_mark_wp_merged_done` import removed; ruff format applied.

## A-G3 nits
- test_init_templates_preservation.py: dropped the dead `survived_in_place or survived_in_backup` disjunct (and unused backup_dirs) in the source-absent test; message folded into the strict `survived_in_place` assert. Oracle strictly unchanged (the strict assert already implied the disjunction). 20 passed with test_mission_agnostic_flag.py.
- test_mission_agnostic_flag.py `_resolve`: asserts on an unresolved name. Verified loud: `_resolve(['agent','profile','lst'])` -> AssertionError "unresolved command path ['lst'] ...". No src break needed (test-helper hardening).

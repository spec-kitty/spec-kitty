# WP01 red-then-green proofs (#5344)

Env: `export PATH=/tmp/claude/venv/bin:$PATH; PYTHONPATH=<worktree>/src python -m pytest <file> -q -p no:cacheprovider`

## T001 test_post_consolidation.py forbidden-import set (commit `55162a72`)

Fix: forbidden parts now include `consolidation`; scan extracted to `_forbidden_imports()` plus a parametrized planted-source test.
Plant: added `from specify_cli.consolidation import state as _planted` to `src/specify_cli/acceptance/post_consolidation.py`.
- Red: `pytest tests/acceptance/test_post_consolidation.py` -> `FAILED ...::test_module_has_zero_merge_or_rollback_coupling` / `1 failed, 13 passed`
- Revert (`git checkout` of the production file) -> Green: `14 passed`

## T002 test_context_bootstrap_markers.py no-leak assertion (commit `2fec3559`)

Fix: assert `mode == "compact"` and that the `Directive IDs:` rail is exactly `["(none)"]` (was `"Directive IDs:" in text or mode == "compact"`, i.e. header presence).
Plant: `src/charter/activation/compact.py` `[] if suppress_project_resolver else resolver_directives` -> `resolver_directives if True else []` (suppression disabled).
- Red: `pytest tests/charter/test_context_bootstrap_markers.py` -> `FAILED ...::TestEmptyCharterProvenance::test_empty_charter_fallback_does_not_leak_directive_canon` / `1 failed, 9 passed` (`Left contains 37 more items, first extra item: 'DIRECTIVE_001'`)
- Revert -> Green: `10 passed`

## T003 test_execution_context_parity.py injection proofs (:479, :768, :1167) (commit `00179e44`)

Fix: the three ratchet comparisons are extracted into `_assert_cwd_parity`, `_assert_persisted_write_target`, `_assert_sequence_parity` (used by the live ratchets unchanged). Each injection proof now runs that REAL function twice: a control that must pass, and a simulated CWD-routing regression (CWD-derived reader / write into the worktree copy / divergent worktree lane) wrapped in `pytest.raises(AssertionError, match=...)`.
Plant: neutered the ratchet comparisons (`assert main_lanes[wp_id] == lane_lanes[wp_id]`, the write-target `claimed` assertions, and the final-lane equality) with `assert True`. (No product-code break is possible for these proofs: the product is correct today; the proofs assert the ratchet's own sensitivity.)
- Red: `pytest tests/architectural/test_execution_context_parity.py -k "test_ratchet_catches_divergence or test_write_ratchet_catches_divergence or test_full_sequence_ratchet_catches_divergence"` -> 3x `Failed: DID NOT RAISE AssertionError`, `3 failed, 18 deselected`
- Revert (file restored byte-identical) -> Green: `pytest ... -k "cwd_parity or catches_divergence or full_sequence"` -> `8 passed, 13 deselected` (includes the live ratchets test_cwd_parity, test_cwd_parity_write, test_full_sequence_*).

## T004 test_drain_capability.py resolve_focus_lease drain gate (commit `1435bed0`)

Fix: the drain-off test now stores a complete, in-scope, unexpired credential + focus lease first, and a new drain-ON baseline test asserts the same state yields the `FocusLease`; so `None` under drain-off can only come from the gate.
Plant: `src/specify_cli/zeitgeist_client/resolution.py` `resolve_focus_capability` drain gate condition replaced with `if False:`.
- Red: `pytest tests/zeitgeist_client/test_drain_capability.py -k TestResolveFocusLeaseDrainGate` -> `FAILED ...::test_returns_none_when_drain_is_off` (`assert FocusLease(...) is None`) / `1 failed, 1 passed`
- Revert (`git checkout`) -> Green: `2 passed` (whole file: `13 passed`)

## T005 test_drain_live_work.py retrospective fan-out + hook drain gates (:184, :232) (commit `175d51ee`)

Fix: new `moment_handlers_enabled` fixture deletes `SPEC_KITTY_NO_MOMENT_HANDLERS`, `SPEC_KITTY_SYNC_DISABLE`, `SPEC_KITTY_SYNC_MINIMAL_IMPORT`; used by `test_skips_publish_observations_under_drain_off` and `test_hook_exits_cleanly_without_resolving_an_adapter`, so the earlier `moment_handlers_disabled_reason()` return can no longer mask the drain gate.
Plant: `if not hosted_posture.drain_posture(...).enabled:` -> `if False:` in both `src/specify_cli/cli/commands/live_work.py::_run_hook` and `src/specify_cli/retrospective/lifecycle_events.py::_fanout_live_work_retrospective`.
- Red (run with `SPEC_KITTY_NO_MOMENT_HANDLERS=1` exported, the ambient dispatch env): `pytest tests/specify_cli/live_work/test_drain_live_work.py -k "skips_publish_observations or hook_exits"` -> `2 failed, 7 deselected`
- Revert (`git checkout src`) -> Green (same env): `2 passed, 7 deselected`

## T006 test_upgrade_command.py::test_project_mode_no_cli_nag_in_output (:870) (commit `099ac87c`)

Fix: the test now drives the real CLI. With `_default_latest_provider` patched to report 999.0.0 it asserts (positive control) `--cli` output contains `999.0.0`, then that `--project --dry-run` output is non-empty and contains neither `999.0.0` nor "update/upgrade available". The old body only ran `_validate_json_contract` on a planner payload.
Plant: `src/specify_cli/cli/commands/upgrade.py` `if cli:` -> `if cli or project:` (project mode renders the CLI nag).
- Red: `pytest tests/specify_cli/cli/commands/test_upgrade_command.py -k test_project_mode_no_cli_nag` -> `AssertionError: assert '999.0.0' not in 'Spec Kitty 999.0.0 is available; you have ...'` / `1 failed, 57 deselected`
- Revert (`git checkout src`) -> Green: `1 passed, 57 deselected`

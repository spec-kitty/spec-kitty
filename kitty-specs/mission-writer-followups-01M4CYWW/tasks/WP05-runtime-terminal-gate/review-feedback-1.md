# WP05 review feedback (cycle 1): changes requested

Reviewed: stream/runtime at 24cba0fe8 (diff 68857d82d..24cba0fe8).

## Blocking

1. **A test regression the change caused and did not fix.**
   `tests/specify_cli/next/test_runtime_bridge_composition.py::test_advancement_helper_raises_policy_error_for_strict_retrospective`
   fails at 24cba0fe8. It still expects
   `pytest.raises(RuntimeError, match="bad retrospective policy")` from
   `advance_run_state_after_composition`. The policy error now comes out wrapped as
   `RetrospectiveGateRefused`, a plain `Exception` subclass. This is the same B6
   change you already applied to `tests/runtime/test_bridge_engine.py` in 24cba0fe8.
   Fix: expect `RetrospectiveGateRefused`, assert `excinfo.value.__cause__ is policy_error`
   or check its type and message, and keep the `fake_plan_next.called` assertion. Record it as
   another out-of-owned-files test edit, like the one in test_bridge_engine.py.
   Repro: `.venv/bin/python -m pytest tests/specify_cli/next/test_runtime_bridge_composition.py -k strict_retrospective`.
   Before you hand back, grep for every test that patches `_resolve_retrospective_policy_for_runtime`
   or `_run_retrospective_learning_capture` and run it. I ran tests/integration/retrospective/,
   tests/specify_cli/post_merge/test_retrospective_triggering.py, tests/next/test_engine_commit_primitives.py,
   tests/next/test_mission_run_back_reference.py and tests/runtime/test_runtime_bridge_query_seam_layout.py.
   They are green; only this one is red.

## Verified (no change needed)

- `_commit_advance` is the only writer of `MissionRunCompleted`. Its two bridge callers
  (`commit_advance` and the `runtime_next_step` fallback in `_dn_advance_engine`) and the composition
  adapter all pass `before_run_completed`. Query mode does not advance, and nothing in
  `src/specify_cli` calls the engine directly.
- The guard runs before any append, emission or `state.json` write, and only on the transition
  into terminal. A re-poll runs neither the gate nor the non-blocking capture
  (the `_reached_terminal` flag works).
- The refusal Decision is `blocked`, with the reason "Retrospective gate refused completion: ...",
  and `guard_failures` comes from `reason.code/detail`. On both paths it is caught before the
  generic handlers.
- Lazy policy resolution: the resolver and the mission-id lookup never raise. A policy error
  still blocks only under a blocking policy, so behaviour is unchanged for steps that do not
  reach terminal.
- Reviewer mutation: moving the guard after `_record_step_completed` makes 8 tests in
  test_terminal_gate_before_completion.py fail.
- The layer rules pass. ruff, C901 and `ruff format --check --force-exclude` are clean.
  mypy reports 12 errors in engine.py, the same payload call-arg errors as before, so none are new.
  The only `noqa` is the moved BLE001, which keeps its rationale.

## Non-blocking

- The foreign-append-during-gate proof covers the three legacy paths. The composition path
  is checked only for byte-identity without a concurrent append. It shares
  `commit_advance`, so the risk is low; a parametrized case would close the gap.

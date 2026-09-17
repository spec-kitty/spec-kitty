# WP05 review feedback — cycle 1

**Issue 1 — FR-006 / T022 is not tested at the owned data-builder boundary.**

`test_4643_tasks_status_empty_mission_is_success_json` invokes the `agent tasks status` command, whose implementation uses `tasks_status_cmd._StatusState` and `_st_emit_json`; it never calls `agent_utils.status.show_kanban_status`. Consequently, deleting the WP05 change in `src/specify_cli/agent_utils/status.py` still leaves the new #4643 regression green. Add a direct production-path test for an empty mission through `show_kanban_status`, patch/spy its console, and assert the complete empty success object, absence of every `error` key, and no console call. Retain reproducible red-on-base / green-on-head evidence for that test and the public command test.

**Issue 2 — T021/T024/T025's required caller and boundary matrix is incomplete.**

The new parametrized not-in-project test covers archive, materialize, dashboard, and glossary, but only dashboard is one of the five otherwise-unowned callers assigned to WP05. It does not exercise `verify.py`, `validate_encoding.py`, `research.py`, or `validate_tasks.py`, so their helper arguments can regress without failing this WP's tests. Add table-driven production-command or boundary-spy coverage for all five assigned callers, including the fixed non-JSON mode for commands that do not expose `--json`. Also add the prompt-required paired assertions for JSON versus human exit fidelity and unchanged happy-path parsed payloads.

The folded #4533 tests also stop at the not-in-project branch. Exercise archive create's mission-not-found/refused JSON branches and materialize's mission-not-found/per-mission failure branches, asserting canonical envelope shape, raw-stdout parseability, no traceback, and the historical exit codes. This is required to prove “canonical error object at each adopted JSON failure,” not merely the shared root failure.

## WP anti-pattern checklist

1. Dead code — PASS (new local helpers have live production callers).
2. Synthetic-fixture test — **FAIL** (the #4643 test does not execute the changed `agent_utils/status.py` production path).
3. Silent empty return — PASS (no undocumented silent failure return introduced).
4. FR coverage — **FAIL** (FR-006's builder boundary and FR-008's full five-caller inventory are not asserted).
5. Frozen surface — PASS (no frozen helper/architecture surface changed by WP05 code).
6. Locked decision — PASS (no prohibited new `feature` flag/interface found in changed code).
7. Shared-file ownership — PASS (the seam-test ownership amendment is committed in the WP prompt).
8. Production fragility — PASS (no new production `raise` without the command-boundary rationale).

## Evidence observed

- New WP05 regression file: 6 passed.
- Task-status seam tests: 12 passed.
- Ruff check over every requested changed file: passed.
- Mypy over the ten changed production modules: passed.
- Whole-repository `ruff format --check .`: passed.
- The broad focused suite ran without a failure through roughly 20% before review stopped it once the blocking acceptance gaps above were established; rerun it to completion before resubmission.

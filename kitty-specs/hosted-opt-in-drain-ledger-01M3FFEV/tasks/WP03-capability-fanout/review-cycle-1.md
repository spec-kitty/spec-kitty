---
affected_files: []
cycle_number: 1
mission_slug: hosted-opt-in-drain-ledger-01M3FFEV
reproduction_command:
reviewed_at: '2026-09-27T01:18:03Z'
reviewer_agent: claude
wp_id: WP03
---

# WP03 review — cycle 1 (reviewer-renata) — CHANGES REQUESTED (one small blocking fix)

The production diff is correct and well-tested: 12/12 spot mutations were killed, diff coverage on the touched src is 100% (50/50 lines), ruff and format are clean, the touched files add no new mypy errors, and C-004/layer rules pass. One test is not hermetic, and that is the only thing blocking approval.

## Issue 1 (BLOCKING): the new drain-on baseline test goes red under `SPEC_KITTY_NO_MOMENT_HANDLERS=1`

`tests/specify_cli/live_work/test_drain_live_work.py::TestRetrospectiveLiveWorkFanoutDrainGate::test_unaffected_under_drain_on_still_publishes`
fails whenever the environment sets `SPEC_KITTY_NO_MOMENT_HANDLERS=1`. That is the documented dispatch environment for this mission's agents. `_fanout_live_work_retrospective` returns at the
`moment_handlers_disabled_reason()` narrower before it reaches the drain gate, so `publish_observations` is never called.

Reproduce:
```
SPEC_KITTY_NO_MOMENT_HANDLERS=1 PYTHONPATH=$PWD/src python -m pytest \
  tests/specify_cli/live_work/test_drain_live_work.py -q -n0
# 1 failed (the test above), 8 passed
```

Fix: in that test (or in a small fixture shared by the drain-on baseline tests in the file), add
`monkeypatch.delenv("SPEC_KITTY_NO_MOMENT_HANDLERS", raising=False)` and `monkeypatch.delenv("SPEC_KITTY_SYNC_DISABLE", raising=False)`, or patch
`specify_cli.core.env.moment_handlers_disabled_reason` to return `None`. After the change, re-run the WP's five new or changed test files with and without the env var set, and record both counts.

(For information only: the pre-existing `tests/specify_cli/live_work/test_retrospective_fanout.py` has the same leak in 3 tests. That file is outside WP03's owned files and the tests were already red under this env on the base, so they are not yours to fix here. You may mention them in the PR.)

## Non-blocking observations (no change required for approval)

- **`routes --json` under drain-off prints the plain guidance line, not JSON.** This matches the existing `_fail` branches, which also emit non-JSON. A JSON caller could still get a machine-readable answer if you emitted something like `{"drain": false, "reason": ...}` when `as_json` is set. Your call; if you change it, add a test.
- **`_RETRYABLE_OUTCOMES`**: the prompt asked for a module-level frozenset. You used a local tuple and gave a rationale (a stand-in outcome does not need to be hashable). The retryable set is exactly the same as before (THROTTLED, DROPPED_BUDGET, DROPPED_UNREACHABLE equals every OfferOutcome member minus SENT, REJECTED and REFUSED_LOCAL), so drain-on behaviour is unchanged. Accepted.
- **Bridge test** checks for "any DEBUG record". Asserting that the message contains `drain off` would pin the branch more tightly. Optional.
- **Mission-level gap (not WP03's files; flagged to the orchestrator):** the interview callers (`cli/commands/charter/interview.py`, `missions/plan/{specify,plan}_interview.py`) call `SaasClient.from_env()` and `load_auth_context()` before `check_prereqs`. Those calls read the credential store and may refresh an expired OAuth session over the network. So under drain-off the widen path still accesses credentials before reaching the gate, which does not meet FR-004's "before any network or credential access". Behaviour is otherwise sensible: `[w]` is silently suppressed and there is no misleading "not authenticated" message.
- The `DrainDisabled`/`DrainPosture`/`ledger_posture`/`set_*_drain` entries in `test_no_dead_symbols` are WP01 symbols that WP02, WP05 and WP08 will consume. WP03 wires `drain_posture`, `require_drain` and `DRAIN_GUIDANCE_LINE`.

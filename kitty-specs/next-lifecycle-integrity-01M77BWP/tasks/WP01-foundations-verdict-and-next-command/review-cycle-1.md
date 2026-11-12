---
affected_files: []
cycle_number: 1
mission_slug: next-lifecycle-integrity-01M77BWP
reproduction_command:
reviewed_at: '2026-11-12T09:48:13Z'
reviewer_agent: claude
wp_id: WP01
---

# WP01 review feedback (reviewer-renata), cycle 1

**Verdict: changes requested.** The production code is correct and matches the contract. The rejection is for one blocker: the FR-010 invariant turns 6 tests red in `tests/runtime/`. That directory is in the per-PR CI matrix (`.github/ci-module-registry.yml:299`) and is the owning subsystem test directory for `src/runtime/next/`. The WP's Test Strategy only listed `tests/runtime/next` and `tests/specify_cli/next`, so these were missed.

## BLOCKER: the new invariant breaks existing test fixtures (red on lane, green on base)

Reproduce from the lane (root venv, `PYTHONPATH=<lane>/src`):
`python -m pytest tests/runtime/test_bridge_decision_builder.py tests/runtime/test_bridge_decision_log_flush.py -q`

Each failure raises `InvalidDecisionPrompt: ... question is None but decision_id is set`. In every case a fixture builds a `query` or `decision_required` Decision or envelope with a `decision_id` and no `question`:

1. `tests/runtime/test_bridge_decision_builder.py:355-369`: `test_never_stamps_timestamp_run_id_decision_id_when_present[decision_required]` and `[query]`. The envelope sets `decision_id` but has no `question`/`options`. Fix: for the prompt-bearing kinds, give it a valid prompt (`question=` plus `options=` or `input_key=`; `with_prompt(PendingDecisionPrompt(...))` also works). Keep the NFR-003 assertion; do not drop those two kinds from the parametrization.
2. `tests/runtime/test_bridge_decision_log_flush.py:275`: `test_composition_dispatch_decision_required_reaches_decision_log`. The `expected = Decision(kind=decision_required, decision_id=DECISION_ID)` has no question. Fix: add `question=` and `options=`/`input_key=` that match the fixture's request payload.
3. `tests/runtime/test_bridge_decision_log_flush.py:411-420`: `test_real_composition_advances_and_logs_despite_optional_seed_failure[missing|raises|lookup_raises]`. The `_map_runtime_decision` stub builds `Decision(kind=decision.kind, decision_id=DECISION_ID)` with no question. Production then catches the raise and degrades to `blocked`, which hides it. Fix: thread `question=decision.question`, `options=decision.options` and `input_key=decision.input_key` from the planned decision (the `_plan_next` stub already sets `question="Proceed?"`).

These files are not in `owned_files`. Record the out-of-map edits in the hand-off, as was done for `tests/specify_cli/next/test_runtime_bridge_composition.py`, or ask the orchestrator to widen ownership. Do **not** weaken the invariant.

Then re-run `tests/runtime` in full (`-n 8 --dist loadfile`). The only other red I saw there is `tests/runtime/test_reassess_under_lock.py::...test_live_upgrade_dry_run_preview_is_deterministic_across_repeats`. Its cause is a `Source mismatch` from running the root venv with `PYTHONPATH` set (environmental, not yours).

## Verified OK (no change needed)

- `finished_board_verdict` matches the freshness ruling exactly: strictly later, a missing latest transition counts as fresh, and an unparsable `accepted_at` gives AWAITING. Failing closed on an unparsable `latest_transition_at` is consistent with "fail toward blocked", and I accept it.
- `next_command` is additive, `suppress_step_pairing` is never serialized, and both are threaded through all three `step_or_blocked` builders, with tests for each branch and for `_with_remediation`.
- Production producer audit: no latent raise. Planner pending decisions (`input:` ids get `input_key`; `audit:` ids carry options, and so does the medium-band rewrite), `_request_decision_input` (pydantic `question` min_length=1), `_map_runtime_decision`, `_build_decision_required_query`, `answer_decision_via_runtime` and orchestrator-api (none construct a Decision).
- The cores stay stdlib-only (`datetime`, `enum`), the canonical `load_meta_or_empty` is used, ruff, format and C901 are clean, and mypy is clean on the touched files.
- The commit trailer is present and the diff contains no model identifiers.

## Nits (optional)

- `PendingDecisionPrompt` accepts `options=[]` or `input_key=""` as "answerable". Consider requiring a non-empty `options` list or a non-empty `input_key`.

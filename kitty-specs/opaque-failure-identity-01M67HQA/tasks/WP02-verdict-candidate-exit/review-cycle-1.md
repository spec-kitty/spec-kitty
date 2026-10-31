---
affected_files:
- src/specify_cli/review/pre_review_gate.py
- src/specify_cli/cli/commands/agent/tasks_move_task_gates.py
- tests/review/test_verdict_candidate_exit.py
cycle_number: 1
mission_slug: opaque-failure-identity-01M67HQA
reproduction_command: ../../.venv/bin/python -m pytest tests/review/test_verdict_candidate_exit.py tests/review/test_transition_gate_parity.py -q
reviewed_at: '2026-10-31T00:40:00Z'
reviewer_agent: reviewer-renata
verdict: approved
wp_id: WP02
---

## Review Verdict: APPROVED (with one should-fix and one nit folded in cycle 1)

**Reviewer:** `reviewer-renata` (independent reviewer model, `tokenfactory/glm-5.3`).
**Diff reviewed:** `99fde90ac5..0c0a62b2eb` plus the fold commit (docstring + caveat scoping).
Red-first commit: `1cffb5d6cc` (5 failing assertions on the pre-fix engine).

### Verified

- The digest printed in the reason is the MATCHED failure's: `diff_baseline`
  returns candidate-side objects, and an opaque match requires equal exit status
  and equal output digest, so "matches the baseline exactly" is literally true.
- `candidate_exit_code` is recorded on both the `NEW_FAILURES` and
  `NO_NEW_FAILURES` scope-source verdicts, including `UNVERIFIED_BASELINE`; the
  legacy JUnit caller passes no keyword, so its `NO_NEW_FAILURES` keeps
  `reason is None` and renders byte-identically to base.
- Parity: no metadata key is added (`_mt_pre_review_gate_metadata` untouched);
  the `if verdict.reason:` guard keeps the fixture console string exact; all
  parity fixtures and the engine tests pass.
- Non-vacuity: each WP02 assertion fails when its product line is reverted
  (exit-status plumbing, reason construction, console append, metadata key set),
  and the stub's exit status is genuinely the subprocess's (`sys.exit(N)` driven
  through the real `_run_raw_command` launch).
- `ruff check` / `ruff format --check` clean; `mypy` clean on the two product
  modules; no unrelated churn.

### Finding 1 (should-fix, folded): `candidate_exit_code` docstring was wrong

It claimed the field is `None` for an uncomputable baseline, but the scope-source
path records the observed status on `UNVERIFIED_BASELINE` as well. The docstring
now names the only two `None` cases (verdicts reached before a completed run; the
legacy JUnit branch) and states that the status is recorded even when the
baseline is uncomputable.

### Finding 2 (nit, folded): the clean-exit caveat read as a contradiction

`no_new_failures` with exit 0 and zero failures appended "this verdict does not
assert a clean candidate exit". The boundary sentence is now appended only for a
NONZERO run, where it carries meaning; `test_clean_candidate_records_exit_zero`
pins both the "exited 0" statement and the absence of the caveat.

### Validation run in this cycle

- `tests/review/test_verdict_candidate_exit.py` — 8 passed.
- `tests/review/test_transition_gate_parity.py`,
  `test_pre_review_gate_engine.py`, `test_pre_review_gate_source_mismatch.py`,
  `test_pre_review_gate_integration.py`, `test_configured_test_timeout.py` — 159
  passed.
- `tests/specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_gate_observability.py`
  and `..._escape_hatch.py` — 50 passed, 2 skipped.
- `mypy` clean on `pre_review_gate.py` and `tasks_move_task_gates.py`.

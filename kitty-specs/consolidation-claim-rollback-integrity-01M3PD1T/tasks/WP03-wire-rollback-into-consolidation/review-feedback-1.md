# WP03 review feedback, cycle 1 (reviewer-renata)

Verified: red at 66d43a63 (#5318 coord branch left advanced; #5332 target left advanced by a real no-driver projection refusal), and green at the tip.
The only driver edit is the gate-call wrapper. C-001 functions are untouched.
ruff, format, and C901 are clean. The mypy count is 6 at both base and tip, and none of the errors are on new lines.
All targeted suites and named gates pass. Two blocking issues remain, both in the same decorator.

**Issue 1 (BLOCKING, FR-007 / #4996): `_records_post_mutation_tips` turns a detected foreign move into "our" post tip.**
- Location: `src/specify_cli/consolidation/executor.py:520-524` (the `finally:` branch).
- How it happens:
  - `advance_branch_ref` raises `RefAdvanceError` when a compare-and-swap fails, meaning another actor moved the ref. Its message says "Refusing to clobber the concurrent update". One path is `ordering.py:675`, the mission-branch bake inside `_phase_bake_and_pre_target_done`, which re-raises at `executor.py:~859`.
  - The decorator's `finally` then records that foreign tip into `post_mutation_refs`.
- Consequences:
  - On `--resume`, `begin_attempt` sees `live == previous_post` and sets `restore_target = snapshot`. A later gate FAIL CAS-restores over the other actor's commit.
  - WP04's `--abort` does the same, because the CAS expected value is the foreign tip.
  - This is exactly the case FR-007 forbids ("rollback never destroys another actor's work"), and the one case where the executor *knows* the move was foreign.
- Fix:
  - On the exception path, do not record when the propagating exception is `RefAdvanceError` or `RefRestoreError`. Keep recording on normal exit, on `typer.Exit`, and on other errors.
  - Without the record, the branch reports `NOT_RESTORED` (moved by other) or `UNCHANGED_BY_RUN`. That is fail-safe.
- Test: add a unit test next to `test_phase_decorator_records_when_the_phase_raises`. A phase that moves a ref externally and then raises `RefAdvanceError` must leave that branch's `post_mutation_refs` entry unrecorded.

**Issue 2 (BLOCKING, masking): recording inside `finally` can replace the real error.**
- If `record_post_mutation_tips` raises while the phase's exception is propagating, the new exception replaces the original. `save_state` I/O errors are one way; a missing git binary is another. The original becomes `__context__` only, so the operator sees the recorder's traceback instead of the phase's `Error:`/`typer.Exit`. The recorder is also decorated onto the in-phase rollback helpers, which run while an error is already in flight.
- Fix: split the decorator into a normal path and an exception path:

```python
try:
    phase(...)
except BaseException as exc:
    if not isinstance(exc, (RefAdvanceError, RefRestoreError)):
        with contextlib.suppress(Exception):
            record(...)
    raise
else:
    record(...)
```

- Test: the recorder raises while the phase raises `typer.Exit(1)`, and the test asserts `typer.Exit(1)` still surfaces.

**Issue 3 (non-blocking, recommended): `_report_rollback` can raise over the gate's `typer.Exit`.**
- Location: `executor.py:3489-3501`.
- An unexpected exception from `rollback_to_snapshot`, for example a failing `save_state`, replaces `typer.Exit(1)` with a traceback. The exit is still non-zero, but the rollback outcome goes unreported.
- Suggestion: catch `Exception`, print `Rollback could not complete: <exc>; branches may still carry this run's commits`, and let the original `typer.Exit` re-raise.

**Issue 4 (non-blocking): the FR-011 control does not assert the report text.**
- `tests/terminus/test_repro_5332.py::test_5332_earlier_verified_landing_is_kept_on_resume_projection_refusal` does not check for "Kept the landing verified by an earlier reconciliation", which the WP prompt names. Use `capsys` or a console capture.
- The #5318 test also does not assert the idempotence line the prompt asks for: target `unchanged ... (already at <pre>)`.

**Issue 5 (note, item 7 shared-file ownership):**
- d03184ad edits WP02-owned `rollback.py` and `tests/consolidation/test_rollback_authority.py` (the WP02 review folds). The folds are sound, but record a coordination note in the Activity Log.
- `__all__` trimming is legitimate: the report and outcome types are return types of the exported entry points, not separate API.
- The `test_executor_phase_boundary.py` stub is a genuine stub for a new git-touching call, not a softened test.

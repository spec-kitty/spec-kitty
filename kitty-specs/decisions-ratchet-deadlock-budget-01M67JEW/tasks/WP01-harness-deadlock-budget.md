---
work_package_id: WP01
title: The harness verdict owns the only deadline
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- NFR-003
- C-002
- C-003
planning_base_branch: issue-6773-decisions-ratchet-deadlock-budget
merge_target_branch: issue-6773-decisions-ratchet-deadlock-budget
branch_strategy: Planning artifacts for this mission were generated on issue-6773-decisions-ratchet-deadlock-budget. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6773-decisions-ratchet-deadlock-budget unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - The verdict
history:
- at: '2026-10-30T23:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/decisions/test_service_terminal_concurrency.py
create_intent:
- tests/specify_cli/decisions/test_service_terminal_concurrency.py
execution_mode: code_change
model: ''
owned_files:
- tests/specify_cli/decisions/test_service_terminal_concurrency.py
role: implementer
tags: []
---

# WP01 — The harness verdict owns the only deadline

## Context

`tests/specify_cli/decisions/test_service_terminal_concurrency.py` is the NFR-002 ratchet
that a terminal call, an `open`, the `doctor decisions --repair` reconciler and a
status-lock writer coexist on the decisions lock. #6773 reports it flaky under xdist.

`research.md` (D-1..D-5) establishes the cause from evidence: the four participants only
ever take the decisions lock *before* the status lock, so the scenario cannot deadlock by
ordering; it does not reproduce on demand (7 broad runs, 14 file runs under `-n 4`, 40
in-process iterations, one serial run pinned to a single core — all green); and the one
remaining way it reds without a deadlock is a wall clock it does not own — the product's
fixed `_LOCK_ACQUIRE_TIMEOUT_S = 10.0` (`decisions/service.py`, mirrored in
`cli/commands/_decisions_doctor.py`). A holder that is merely slow surfaces as
`DecisionError(LOCK_TIMEOUT)` (a retryable refusal, by design — `#4848` operator ruling,
`test_decisions_lock_waiter_times_out_and_writes_nothing`) and `_Worker.finish()` reports
it as a failed worker.

Read before you start: `spec.md` (FR-001..FR-005, NFR-001..NFR-003, C-002, C-003),
`plan.md` §D1..§D5, `research/deadlock-budget-probe.md` (the reproducible pre-fix red),
`docs/development/testing/testing-flakiness.md` (Tier-2 policy: fix the root cause, never
retry, never skip/xfail/quarantine), `CLAUDE.md` (Python conventions).

## Owned files

- `tests/specify_cli/decisions/test_service_terminal_concurrency.py` — the only product
  file this WP may edit. No `src/` change is permitted (C-001): the product's 10 s bound
  is the documented refusal contract and stays where it is.

## T001 — Deterministic red proof, before touching the harness

Reproduce the pre-fix red deterministically, through the pre-existing entry points
(DIRECTIVE_034). Copy the recipe in `research/deadlock-budget-probe.md` into
`tests/specify_cli/decisions/test_zz_probe_slow_holder.py` (so the `tests/` conftest chain
applies), run `uv run --frozen pytest tests/specify_cli/decisions/test_zz_probe_slow_holder.py -q -n0`,
and confirm it reds with

```
AssertionError: DecisionError("Timed out after 0.2s waiting for the decisions lock …")
```

while all four workers finish — i.e. a slow-but-finite holder, no deadlock. Record the
observed output in the WP activity log and **delete the probe file** (it must never be
committed under `tests/`).

Acceptance: the red is observed and recorded; the probe file is gone from the tree.

## T002 — One scenario, one helper

Extract the four-participant interleaving out of
`test_terminal_calls_do_not_deadlock_with_other_decision_lock_holders` into a module-level
helper:

```python
def _run_coexistence(tmp_path: Path, *, slow_hold_s: float = 0.0) -> None
```

It builds the mission and the two decisions, starts the four barrier-gated participants
(two terminal calls, an `open`, `doctor._repair`, the status-lock writer), finishes them
with the backstop budget, then asserts the doctor report is clean — exactly the assertions
the ratchet has today. The ratchet becomes a one-line call with no injection, so the
existing test keeps asserting precisely what it asserted (FR-005). Do **not** remove,
weaken or reorder any existing assertion; keep `_Pause`, `_Worker`, `_open`, `_resolves`
and the other tests in the module untouched apart from what T003 requires.

`slow_hold_s` wraps `specify_cli.decisions.store.save_index` so a holder's critical section
takes `slow_hold_s` longer than it otherwise would (a finite hold, used only by the T004
proof).

Acceptance: `uv run --frozen pytest tests/specify_cli/decisions/test_service_terminal_concurrency.py -q -n0`
is green, and `git diff` shows no assertion removed.

## T003 — The scenario owns its bounds; one backstop decides "stuck"

1. Inside `_run_coexistence`, pin — through a `pytest.MonkeyPatch.context()` so the pin is
   undone even when a worker raises:
   - `specify_cli.decisions.service._LOCK_ACQUIRE_TIMEOUT_S = None`
   - `specify_cli.cli.commands._decisions_doctor._LOCK_ACQUIRE_TIMEOUT_S = None`

   `None` is the documented "wait without a bound" mode of `machine_file_lock`
   (`kernel/locks.py::_sync_acquire`), already used by `open_decision`
   (`_OPEN_LOCK_WAIT_S = None`). Comment *why* (a slow machine must not become a refusal),
   and that the refusal contract keeps its own coverage in
   `test_decisions_lock_waiter_times_out_and_writes_nothing`.

2. Add one named backstop next to `_WAIT_S`:

   ```python
   _WAIT_S = 20.0            # a rendezvous participant must reach/leave its event
   _DEADLOCK_BUDGET_S = 45.0  # a participant that has not finished by now is stuck
   ```

   with a comment stating the relationship: more than 2x the largest legitimate wait
   inside the scenario (`_WAIT_S = 20.0`) and below **every** `@pytest.mark.timeout`
   marker in the file (60 s on the pause-driven tests, 90 s on the ratchet), so a hang yields
   the harness verdict, not a bare `Failed: Timeout` (NFR-002).

3. `_Worker.finish(self, timeout: float = _DEADLOCK_BUDGET_S)`: keep both assertions, and on
   a timed-out join fail with a report that keeps the phrase `worker did not finish` and
   appends `_deadlock_report(repo_root)`:
   - `faulthandler.dump_traceback(file=…, all_threads=True)`, so the blocked frame
     (`_sync_acquire` → `time.sleep`, or something else) is visible;
   - every sidecar `*.lock` file under the mission's `decisions/` directory with its
     recorded holder payload — `kernel.locks` truncates on release, so a non-empty record
     names the holder and an empty one names a released lock.

   Keep it a small, dependency-free helper (stdlib only); `finish()` needs the mission root,
   so pass it in (or give `_Worker` the repo root). Do not print to stdout — the report goes
   into the failure message only, so a green run stays silent (NFR-001).

Acceptance: `uv run --frozen pytest <file> -q -n0` is green and unchanged in runtime
(~5 s); grepping the source shows exactly one deadlock budget constant and no remaining
`30.0` join default.

## T004 — The non-vacuity proof pair

Add two tests, ~1 s each, that run the *production* entry points the ratchet uses (not a
mock of the locking layer):

1. `test_coexistence_ratchet_is_indifferent_to_the_ambient_acquire_bound` — pin an ambient
   bound of 0.1 s (`service._LOCK_ACQUIRE_TIMEOUT_S`) and call
   `_run_coexistence(tmp_path, slow_hold_s=0.3)`. Assert green. This is the fast encoding
   of the T001 red: on a harness that honours the ambient bound it reds, so the assertion is
   non-vacuous (tactic `acceptance-criteria-non-vacuity`, same-fixture positive control).
2. `test_deadlock_backstop_reports_a_participant_that_never_finishes` — park a `_Worker` on
   an `threading.Event()` that is never set, call `finish(timeout=0.2)` inside
   `pytest.raises(AssertionError)` and assert the message carries `worker did not finish`
   plus the report (a frame from the parked thread and the decisions lock path). Then set the
   event so the test leaves no live thread (NFR-003).

Keep both `@pytest.mark.timeout(60)` and `pytest.mark.unit` (module-level marker already
applies).

Acceptance: both tests pass; temporarily reverting T003's pin makes test 1 red (prove it and
record the output, then restore) — that is the half-by-half proof the tactic asks for.

## T005 — Repetition evidence

Run and record in the WP activity log:

```bash
uv run --frozen pytest tests/specify_cli/decisions/test_service_terminal_concurrency.py -q -p no:cacheprovider -n0
for i in $(seq 1 30); do uv run --frozen pytest tests/specify_cli/decisions/test_service_terminal_concurrency.py -q -p no:cacheprovider -n 4 --dist loadfile; done
uv run --frozen pytest tests/specify_cli/cli/commands/test_decision*.py tests/specify_cli/decisions -q -n 4 --dist loadfile
```

All must be green (SC-001). Also run `uv run --frozen ruff check` on the file and
`uv run --frozen mypy` if the file is in the mypy surface. Do **not** run a full heavy
suite (`NO_FULL_HEAVY_SUITES_IN_MISSION`).

## Definition of done

- T001 red observed and recorded; probe file absent from the tree.
- One scenario helper, no assertion removed, no `src/` change, no skip/xfail/quarantine/retry.
- Exactly one wall clock decides "deadlock", and a timed-out join names the stuck threads
  and the decisions lock.
- 30 consecutive `-n 4` runs green plus the serial run; the broad decisions slice green.
- Ruff clean; the file's green-path runtime unchanged.

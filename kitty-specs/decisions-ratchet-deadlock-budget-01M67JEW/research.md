# Discovery — decisions ratchet deadlock budget (#6773)

## Context

`tests/specify_cli/decisions/test_service_terminal_concurrency.py::test_terminal_calls_do_not_deadlock_with_other_decision_lock_holders`
is the NFR-002 ratchet that four decision-surface participants can coexist: two terminal
calls, an `open`, the `doctor decisions --repair` reconciler and a status-lock writer. It
was reported flaky under xdist (#6773) after one red in two runs of

```bash
uv run --frozen pytest tests/specify_cli/cli/commands/test_decision*.py tests/specify_cli/decisions -q -n 4 --dist loadfile
```

The reporter's proposed cause was the short fixed joins (`thread.join(0.3)` /
`thread.join(0.5)`). This step re-derived the cause from evidence rather than accepting it.

## Decisions

### D-1 — This is a Tier-2 harness defect, not a lock bug (no lock-order cycle exists)

Every participant that takes two locks takes the decisions lock **before** the status lock:

| Participant | Lock order |
|---|---|
| `resolve_decision` / `defer` / `cancel` | `_decisions_lock` (`decisions/service.py`) → `feature_status_lock` inside `emit.emit_decision_resolved` |
| `open_decision` | `_decisions_lock` → `feature_status_lock` inside `emit.emit_decision_opened` |
| `doctor._repair` | `machine_file_lock(decisions/index.json.lock)` only |
| status-lock writer | `feature_status_lock` only |

No path in the four takes the status lock first and then waits for the decisions lock, so
the scenario cannot deadlock by ordering. The decisions lock is also keyed to a path under
the test's `tmp_path` (`_ledger_dir` → `decisions/index.json.lock`) and the status lock to
`tmp_path` as its lock root (`resolve_status_lock_root` falls back to the mission's parent
because `tmp_path` is not a git checkout), so nothing is shared with another xdist worker
or another process on the host.

### D-2 — It does not reproduce on demand here, so the cause must be argued from mechanism

Reproductions attempted on `main` @ `512567eee7` (this host, itself loaded by 20 parallel
agents, load average ~11 on 20 cores):

| Probe | Runs | Result |
|---|---|---|
| the issue's full command, `-n 4 --dist loadfile` | 7 (2,107 test executions) | all green |
| this file alone, `-n 4 --dist loadfile` | 14 (6 of them with 6 extra CPU burners) | all green |
| this file, `-n0` serial, and pinned to one core with `taskset -c 0` | 2 | all green |
| this single test, 40 iterations in one process (`pytest.main` loop) | 40 | all green |

A rare, load-shaped flake: absence of a local reproduction is not evidence of absence, and
the fix therefore has to remove the *mechanism* that can turn a slow machine into a red.

### D-3 — The remaining wall clock that can red the ratchet belongs to the product, not the test

`_Worker.finish()` reports `assert self.error is None` for any worker exception. A
participant that holds the decisions lock longer than the product's fixed
`_LOCK_ACQUIRE_TIMEOUT_S` (10 s, `decisions/service.py`, mirrored by
`_decisions_doctor.py`) makes its peers raise `DecisionError(LOCK_TIMEOUT)` or an
uncaught `LockAcquireTimeout` — a **retryable refusal by design** (`#4848` operator ruling,
pinned by `test_decisions_lock_waiter_times_out_and_writes_nothing`), *not* a deadlock.
The ratchet cannot distinguish that from a deadlock, so on a box where an `fsync` or a
`git` probe stalls past 10 s it reds with a "failed worker" that is not a deadlock at all.

Evidence (deterministic, fast): pin the ambient bound to 0.2 s and slow every holder by
0.4 s — every holder still releases — and the ratchet reds with

```
AssertionError: DecisionError("Timed out after 0.2s waiting for the decisions lock
'/…/kitty-specs/concurrency-mission/decisions/index.json.lock'; another decision command is
holding it. Nothing was written; retry the command.")
```

while all four workers finish. The probe recipe is preserved in
`research/deadlock-budget-probe.md`; the same shape at the production 10 s bound is a
stalling filesystem.

### D-4 — The joins the issue title blames are in the safe direction

`b.thread.join(0.5)` / `b.thread.join(0.3)` in the two preceding tests are followed by
`assert b.thread.is_alive()`. Load can only make a still-blocked waiter *more* likely to
still be alive, so those cannot false-red; they would only false-*green* if a worker had
not yet been scheduled, which does not weaken the ratchet they defend (the fixes at issue
there are guarded by the event-driven `_Pause`). The unsafe wait is the opposite one:
`_Worker.finish()`'s hard-coded 30 s join, which converts any unbounded-by-the-test wait
into a bare `worker did not finish` with no diagnosis.

### D-5 — Sanctioned remedy: one wall clock, owned by the harness

`docs/development/testing/testing-flakiness.md` (Tier 2, "correctness test") prescribes
fixing the root cause and forbids retries, skips and quarantine. Two mechanics follow:

1. **The scenario pins the acquire bound it runs under** (both `decisions.service` and
   `_decisions_doctor`) so the scenario's verdict cannot depend on an ambient product
   bound. A slow machine is then simply slow.
2. **One named backstop budget decides "stuck"**, chosen above every legitimate wait
   inside the scenario, with the join failure carrying a thread dump and the decisions-lock
   holder record. This keeps the deadlock guard while making its verdict self-explaining.

Negative-control requirement (acceptance-criteria non-vacuity): a participant that never
finishes must still red the ratchet inside that budget, otherwise the "no false red" fix
would have bought silence.

## Open questions (resolved or carried into the plan)

- **Q1 — Should the product's 10 s bound move?** No. It is a documented retryable refusal
  (NFR-002, #4848) and is pinned by its own test. Changing it would be a product change
  outside this issue's scope (C-001).
- **Q2 — Should the ratchet keep the product bound to prove "no refusal under
  contention"?** No: that is a latency budget, i.e. Tier-1 content, and it is already
  covered explicitly by the timeout test with a 0.3 s bound on the same fixture.
- **Q3 — Does the docs flakiness audit table need a row?** Yes — the table is the
  disposition register for known surfaces, and this one now has a root cause and a fix.

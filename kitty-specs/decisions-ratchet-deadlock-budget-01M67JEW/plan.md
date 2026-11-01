# Implementation Plan: Decisions Ratchet Deadlock Budget

**Branch**: `issue-6773-decisions-ratchet-deadlock-budget` | **Date**: 2026-10-30 | **Spec**: `kitty-specs/decisions-ratchet-deadlock-budget-01M67JEW/spec.md`
**Input**: Mission specification from `kitty-specs/decisions-ratchet-deadlock-budget-01M67JEW/spec.md`, discovery evidence in `research.md`

## Summary

The coexistence ratchet
(`tests/specify_cli/decisions/test_service_terminal_concurrency.py::test_terminal_calls_do_not_deadlock_with_other_decision_lock_holders`)
currently inherits **two** wall clocks it does not own: the product's fixed 10 s
decisions-lock acquire bound (`decisions/service.py`, `_decisions_doctor.py`) and a
hard-coded 30 s join in `_Worker.finish()`. Either one can red the test on a loaded
machine with no deadlock present (#6773), and neither failure says anything about
*why* a participant did not finish.

The change moves the verdict to the harness: the scenario pins the acquire bound it runs
under (so "slow" can never be mistaken for "stuck"), one named backstop budget decides
"stuck" and is derived from the longest legitimate wait inside the scenario, and a
timed-out join fails with a thread dump plus the decisions-lock holder record. That is a
test-only change (C-001): no product constant, lock primitive or behaviour moves.

## Technical Context

**Language/Version**: Python 3.11 (repo `pyproject.toml`)
**Primary Dependencies**: pytest, pytest-xdist, pytest-timeout, `kernel.locks`
(`machine_file_lock`), `specify_cli.decisions` service/emit/doctor
**Storage**: `kitty-specs/<mission>/decisions/index.json` + `status.events.jsonl` under a
per-test `tmp_path`; locks are sidecar flock files under the same tree
**Testing**: `uv run --frozen pytest`; target file is `@pytest.mark.unit`; the issue's
parallel invocation is `-n 4 --dist loadfile`
**Target Platform**: POSIX (flock) and Windows (`msvcrt.locking`) — the test must not
assume flock, and it does not: it drives the public service/doctor entry points
**Project Type**: single library + CLI (`src/`)
**Performance Goals**: the fixed file's green path stays under 15 s under
`-n 4 --dist loadfile` (today ~6-9 s); no new sleep on the green path (NFR-001)
**Constraints**: no skip/xfail/quarantine/retry, no weakened assertion (C-002); the fix
must hold at `-n0` and `-n4` alike and must not depend on xdist internals (C-003)
**Scale/Scope**: one test module (`tests/specify_cli/decisions/test_service_terminal_concurrency.py`,
~280 lines) plus one docs table row (`docs/development/testing/testing-flakiness.md`)

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Verdict | Note |
|---|---|---|
| Single canonical authority | PASS | The product's acquire bound stays the single owner of refusal semantics; the test pins it, it does not fork a second policy. `docs/development/testing/testing-flakiness.md` stays the single flake policy. |
| ATDD-first / DIRECTIVE_034 (test-first bug fixing) | PASS | The red is demonstrated through the pre-existing test entry point with a deterministic injection (recorded in `research/deadlock-budget-probe.md`) before the harness change; the negative-control proof lands with the fix. |
| DIRECTIVE_041 (a test only where it guards real behaviour) | PASS | Two proofs, both about the harness verdict itself: "a slow-but-finite holder is not a deadlock" and "a never-finished participant still reds with diagnosis". No speculative tests. |
| DIRECTIVE_024 (locality of change) | PASS | Two files. No new module, no new abstraction, no product edit. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | PASS | Mission runs the decisions module slice and the architectural docs gates only; CI owns the full sweep. |
| Standing Order #5 / no new allowlist | PASS | No baseline or allowlist entry is added; `quarantine` is not used. |
| Pre-existing Failure Reporting Rule | PASS | #6773 is the report; unrelated reds are classified against the merge base in the PR body. |

No violations, so `## Complexity Tracking` stays empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/decisions-ratchet-deadlock-budget-01M67JEW/
├── plan.md                                    # This file
├── research.md                                # Discovery evidence (D-1..D-5)
├── spec.md                                    # FR/NFR/C/SC contract
├── research/deadlock-budget-probe.md          # Reproducible pre-fix red recipe
└── tasks/                                     # WP files (from /spec-kitty.tasks)
```

### Source Code (repository root)

```
tests/specify_cli/decisions/test_service_terminal_concurrency.py   # the ratchet + proof pair
docs/development/testing/testing-flakiness.md                      # audit-table row
```

**Structure Decision**: the ratchet already lives in one module with its `_Worker` and
`_Pause` helpers; the scenario body moves into a module-level helper so the ratchet and
the two new proofs run *the same* four-participant interleaving instead of three
near-copies (single canonical scenario, DIRECTIVE_024). No new test module: the file is
the surface #6773 names, and its marker set (`unit`) and budget expectations already
apply.

## Phase 0 — Research (complete)

Recorded in `research.md` (D-1..D-5): no lock-order cycle exists; the flake does not
reproduce on demand across 7 broad runs / 14 file runs / 40 in-process iterations; the
only load-shaped red mechanism is the product's fixed acquire bound surfacing as a
retryable refusal; the issue title's blamed short joins are in the safe direction; the
sanctioned remedy is the Tier-2 "remove the wall-clock dependency, never retry" policy.

The one open design question — *how much* to pin — is settled in the plan: pin the
scenario's acquire bound to "no bound" (an unbounded wait, exactly what `open_decision`
already uses at `_OPEN_LOCK_WAIT_S = None`), and let one harness budget be the only
deadline. A bounded-but-large value would reintroduce a second wall clock whose
relationship to the harness budget has to be re-argued for every future edit.

## Phase 1 — Design

### D1. One scenario, three callers

`_run_coexistence(tmp_path, *, slow_hold_s: float = 0.0)` builds the mission, opens the
two decisions, pins the acquire bounds, starts the four barrier-gated participants
(terminal calls, `open`, `doctor._repair`, status-lock writer), finishes them with the
backstop budget, and returns the per-worker results. The existing ratchet calls it with no
injection. This keeps the scenario single-sited so the proofs cannot drift from the test
they defend.

### D2. The scenario owns its acquire bound

Inside `_run_coexistence`, `monkeypatch`-style pinning (via `pytest.MonkeyPatch.context()`
so the helper can be called from a test that has no `monkeypatch` fixture, and so the pin
is undone even if a worker fails) sets:

- `specify_cli.decisions.service._LOCK_ACQUIRE_TIMEOUT_S = None`
- `specify_cli.cli.commands._decisions_doctor._LOCK_ACQUIRE_TIMEOUT_S = None`

Both are the documented "wait without a bound" mode of `machine_file_lock`
(`timeout_s=None`), already used by `open_decision`. Consequence: a holder that is slower
than any fixed bound is *slow*, not a refusal, and the only thing that can end the test
badly is a participant that never returns — which is what the ratchet is about. The
product's refusal contract keeps its own coverage in
`test_decisions_lock_waiter_times_out_and_writes_nothing` (0.3 s bound, same fixture), so
no assertion is lost (C-002).

### D3. One named backstop budget, above every legitimate wait

```python
_WAIT_S = 20.0            # a rendezvous participant must reach/leave its event
_DEADLOCK_BUDGET_S = 45.0  # a participant that has not finished by now is stuck
```

`_DEADLOCK_BUDGET_S` keeps more than 2x the largest legitimate wait inside the
scenario (`_WAIT_S = 20.0`, used by the barrier and the `_Pause` release) and stays
below **every** `@pytest.mark.timeout` marker in the file (60 s on the pause-driven
tests, 90 s on the ratchet), so a hang yields the harness verdict, not a bare
`Failed: Timeout` (NFR-002). Rationale is recorded next to the constant.

### D4. A deadlock verdict that says who

`_Worker.finish(timeout=_DEADLOCK_BUDGET_S)` keeps both of its guards (`not alive`,
`error is None`) but, on a timed-out join, raises with a report built by
`_deadlock_report(repo_root)`: `faulthandler.dump_traceback(all_threads=True)` (so the
blocked frame — `_sync_acquire`/`time.sleep`, or something else entirely — is visible)
plus every sidecar lock file under the mission's `decisions/` directory with its recorded
holder payload (`kernel.locks` truncates on release, so a non-empty record names the
holder; an empty one names a released lock). The message keeps the phrase
`worker did not finish` so existing greps still work.

### D5. Negative-control proof pair (non-vacuity)

- `test_coexistence_ratchet_is_indifferent_to_the_ambient_acquire_bound` — pins the
  ambient bound to 0.1 s and injects a 0.3 s finite hold; asserts the ratchet stays green.
  This is the fast encoding of the pre-fix red proven in
  `research/deadlock-budget-probe.md`, and it is non-vacuous because the same injection on
  a harness that honours the ambient bound reds (probe output).
- `test_deadlock_backstop_reports_a_participant_that_never_finishes` — a worker parked on
  an `Event` that is never set, finished with a 0.2 s budget: asserts the harness raises
  with `worker did not finish` and a report naming the parked frame, then releases the
  event (NFR-003: no leaked live work).

Both call the production entry points the ratchet uses, not a mock of the locking layer
(non-vacuity rule 3).

### D6. Docs disposition row

`docs/development/testing/testing-flakiness.md`'s "Audit + disposition of known flake
surfaces" table gains one row: surface, Tier 2, root cause (a correctness ratchet leaning
on a product wall-clock bound it does not own), disposition (fixed at root cause, no
retry), and the evidence pointer. `updated:` on the page is bumped and the docs freshness
gate is run.

## Implementation Concern Map

### IC-01 — Harness verdict owns the only deadline

- **Purpose**: Make "deadlocked" mean "a participant never returned", decided by one
  harness-owned budget, and stop the product's acquire bound from deciding it.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001,
  NFR-002, NFR-003
- **Affected surfaces**: `tests/specify_cli/decisions/test_service_terminal_concurrency.py`
- **Sequencing/depends-on**: none
- **Risks**: (a) the scenario helper must restore the pinned constants even when a worker
  raises, or a later test in the same xdist worker inherits an unbounded acquire — use a
  `MonkeyPatch.context()`; (b) raising the join budget must stay under the test's
  `timeout(90)` marker; (c) the proof pair must not slow the green path (NFR-001).

### IC-02 — The surface is recorded where the policy lives

- **Purpose**: Put this surface in the flakiness audit table so the next reader gets the
  tier, root cause and disposition instead of re-diagnosing it.
- **Relevant requirements**: FR-006, SC-004
- **Affected surfaces**: `docs/development/testing/testing-flakiness.md`
- **Sequencing/depends-on**: IC-01 (the row states the fix that landed)
- **Risks**: the docs freshness gate reads a generated index; regenerate only what this
  change touches and verify with `check_docs_freshness --ci` (errors=0).

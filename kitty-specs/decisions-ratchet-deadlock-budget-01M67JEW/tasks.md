# Tasks: Decisions Ratchet Deadlock Budget

**Mission**: `decisions-ratchet-deadlock-budget-01M67JEW` · **Branch**: `issue-6773-decisions-ratchet-deadlock-budget` (planning base and merge target)
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [research/deadlock-budget-probe.md](research/deadlock-budget-probe.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Deterministic red proof: pin the ambient acquire bound and inject a finite slow holder, confirm the pre-fix ratchet reds with a `LOCK_TIMEOUT` refusal | WP01 | |
| T002 | Extract the four-participant interleaving into one `_run_coexistence` helper; the existing ratchet calls it unchanged | WP01 | |
| T003 | Pin both decisions-lock acquire bounds inside the scenario; add `_DEADLOCK_BUDGET_S` and the `_deadlock_report` diagnostic to `_Worker.finish` | WP01 | |
| T004 | Proof pair: `test_coexistence_ratchet_is_indifferent_to_the_ambient_acquire_bound` and `test_deadlock_backstop_reports_a_participant_that_never_finishes` | WP01 | |
| T005 | Repetition evidence: 30 consecutive `-n 4 --dist loadfile` runs plus `-n0`, and the architectural/docs gates the file is subject to | WP01 | |
| T006 | `docs/development/testing/testing-flakiness.md`: audit-table row for this surface, page `updated:` bump | WP02 | |
| T007 | Docs freshness gate (`check_docs_freshness --ci`, errors=0) and the legacy-terminology gate | WP02 | |

## Phase 1 — The verdict

### WP01 — The harness verdict owns the only deadline

**Goal**: the coexistence ratchet reds only when a participant never returns, and a timed-out join names the stuck participant and the decisions lock. **Priority**: P1. **Prompt**: [tasks/WP01-harness-deadlock-budget.md](tasks/WP01-harness-deadlock-budget.md)
**Independent test**: `uv run --frozen pytest tests/specify_cli/decisions/test_service_terminal_concurrency.py -q -n0` and the same file under `-n 4 --dist loadfile` for 30 consecutive iterations.

T001 Deterministic red proof: pin the ambient acquire bound and inject a finite slow holder, confirm the pre-fix ratchet reds with a `LOCK_TIMEOUT` refusal (WP01)
T002 Extract the four-participant interleaving into one `_run_coexistence` helper; the existing ratchet calls it unchanged (WP01)
T003 Pin both decisions-lock acquire bounds inside the scenario; add `_DEADLOCK_BUDGET_S` and the `_deadlock_report` diagnostic to `_Worker.finish` (WP01)
T004 Proof pair: `test_coexistence_ratchet_is_indifferent_to_the_ambient_acquire_bound` and `test_deadlock_backstop_reports_a_participant_that_never_finishes` (WP01)
T005 Repetition evidence: 30 consecutive `-n 4 --dist loadfile` runs plus `-n0`, and the architectural/docs gates the file is subject to (WP01)

Dependencies: none. Risk: the scenario helper must undo its pinned constants even when a worker raises, or a later test in the same xdist worker inherits an unbounded acquire.

## Phase 2 — The record

### WP02 — The surface is recorded where the flake policy lives

**Goal**: the flakiness audit table carries this surface's tier, root cause, disposition and evidence, so the next reader is not left to re-diagnose it. **Priority**: P2. **Prompt**: [tasks/WP02-flakiness-audit-row.md](tasks/WP02-flakiness-audit-row.md)
**Independent test**: `uv run python -m scripts.docs.check_docs_freshness --ci` reports errors=0 and the row is present in the rendered page.

T006 `docs/development/testing/testing-flakiness.md`: audit-table row for this surface, page `updated:` bump (WP02)
T007 Docs freshness gate (`check_docs_freshness --ci`, errors=0) and the legacy-terminology gate (WP02)

Dependencies: WP01 (the row states the fix that landed). Risk: the freshness gate reads a generated index — regenerate only what this change touches and verify with the gate itself.

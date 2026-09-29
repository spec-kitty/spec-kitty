# Implementation Plan: Implement resumes after in_review to in_progress rejection

**Branch**: `ccr-806fafb9-5qycab` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/implement-rework-resume-01M3QA1X/spec.md`

## Summary

`start_implementation_status` (the shared implementation-start authority) refuses the
implementer's resume on an `in_progress` WP because its ownership check compares the
requester with the slot occupant, which after an `in_review → in_progress` rework verdict
is the reviewer. The fix admits the implementer of record, resolved by the existing
`status.review_roles.latest_implementer_actor` projection, through one pure predicate that
`move-task`'s ownership role allowance also uses, so the two ownership checks share one rule.
The resume stays an idempotent no-op on the lane (no event emitted).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich (CLI); no new dependencies
**Storage**: append-only `status.events.jsonl` (read only by this change)
**Testing**: pytest — real-CLI harness `tests/specify_cli/cli/commands/agent/_rework_loop_harness.py`; unit tests on the lifecycle arm and the predicate
**Target Platform**: Linux / macOS / Windows CLI
**Project Type**: single project (`src/specify_cli/`)
**Performance Goals**: no extra event-log read on the unchanged paths (NFR-001)
**Constraints**: no `--force` in the loop (C-002); reuse the canonical projection (C-001); complexity ≤ 15
**Scale/Scope**: 2 source modules, ~40 changed source lines

Supply-chain check (DIRECTIVE_051): no dependency decision in this mission — not applicable.

## Charter Check

- **Single canonical authority** — PASS: one predicate (`is_latest_implementer`) in `status/review_roles.py` serves both the lifecycle arm and `move-task`; no fourth implementer projection (C-001, #5340 stays the unification follow-up).
- **Architectural alignment** — PASS: the lifecycle imports `review_roles` function-locally (as it already does for `coordination.status_transition`), because `review_roles` imports `_actor_key`/`GENERIC_IMPLEMENTATION_ACTORS` from the lifecycle module at import time.
- **ATDD / red-first** — PASS: the real-CLI regression through `agent action implement` is RED on the planning base (exit 1, `WorkPackageClaimConflict`) and committed before the fix.
- **Tiered rigour** — status ownership is core domain: unit tests on every new branch (admit, third tool, generic, empty log, read failure) plus the real-CLI loop.
- **Terminology** — Mission / work package; no `feature` aliases introduced.

## Project Structure

### Documentation (this mission)

```
kitty-specs/implement-rework-resume-01M3QA1X/
├── spec.md
├── plan.md
├── research.md
├── tasks.md
├── tasks/WP01-implementer-resume.md
├── issue-matrix.json
└── traces/ (tooling-friction.md, approach.md, design-decisions.md)
```

### Source Code (repository root)

```
src/specify_cli/status/
├── review_roles.py              # + is_latest_implementer(latest, actor) predicate
└── work_package_lifecycle.py    # IN_PROGRESS arm admits the implementer of record
src/specify_cli/cli/commands/agent/
└── tasks_transition_core.py     # _ownership_role_allowance / _implementer_arm reuse the predicate

tests/specify_cli/cli/commands/agent/
├── test_rework_unforced_loop.py     # real-CLI resume + fail-closed
└── test_rework_guard_ratchets.py    # third tool refused via implement
tests/status/test_work_package_lifecycle.py   # lifecycle arm unit tests
tests/unit/status/test_review_roles.py        # predicate unit tests
```

**Structure Decision**: single project; changes stay inside `status/` plus the one
move-task core module that already consumes the projection.

## Complexity Tracking

No charter violations.

## Implementation Concern Map

### IC-01 — Implementer-of-record admission at the implementation-start authority

- **Purpose**: let the implementer of record resume an `in_progress` WP after a rework verdict, fail closed on read failure, keep third tools refused.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002, C-001, C-002, C-003
- **Affected surfaces**: `src/specify_cli/status/work_package_lifecycle.py` (IN_PROGRESS arm + extracted helper), `src/specify_cli/status/review_roles.py` (shared predicate), `src/specify_cli/cli/commands/agent/tasks_transition_core.py` (reuse predicate, behaviour-preserving)
- **Sequencing/depends-on**: none
- **Risks**: import cycle (mitigated by a function-local import); append-order vs Lamport disagreement between the projection and the reducer slot under merged-log reordering (accepted residual, #4941).

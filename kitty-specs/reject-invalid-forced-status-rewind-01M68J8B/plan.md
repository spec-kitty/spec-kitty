# Implementation Plan: Reject invalid forced status rewinds before append

**Branch**: `issue-6514-reject-invalid-forced-status-rewind` | **Date**: 2026-10-31 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/reject-invalid-forced-status-rewind-01M68J8B/spec.md`

## Summary

Move the `for_review → in_progress` `review_ref` requirement out of the auditor alone
and into the status FSM, so it is enforced *before* the append instead of after it. The
fact ("this edge's events require a `review_ref`") gets one owning definition in
`status/wp_state.py`; `WPState.check_transition` reads it on the admission path and
`status/validate.py::validate_event_schema` reads the same definition on the audit path.
The requirement is force-insurmountable: `--force --reason` still overrides the missing
structural edge, but it can no longer override this one. Refusal happens in the pure
validation step, before any lock-protected append, so the event log and `status.json` are
byte-identical afterwards. No new surface, no new CLI flag, no force-policy widening.
Grounding and the rejected alternatives: [research.md](research.md).

## Engineering Alignment

Taken autonomously inside the confirmed scope (mechanics only; operator-facing decisions
are recorded in research.md §5):

- **One predicate, two call sites.** `status/wp_state.py` gains
  `REVIEW_REF_REQUIRED_EDGES: frozenset[tuple[Lane, Lane]]` and
  `requires_review_ref(from_lane, to_lane) -> bool`. `validate.py` already imports from
  `wp_state`, so this adds no import edge and no layering change (C-001).
- **Force-insurmountable, like `genesis`.** `check_transition` already refuses `genesis`
  as a target before consulting force. The review-ref requirement joins it there: the
  structural-edge refusal keeps its historical message and ordering, then the
  requirement is evaluated on every admission that survives it, then force and the guard
  run as before. A force-free `for_review → in_progress` still returns the same
  `Illegal transition:` text it returns today.
- **Where the refusal lands.** The pipeline's step 6 (`validate_transition`) is the
  tree's only per-emit validation call and is pure (no writes, no locks), so raising
  `TransitionError` there leaves zero partial state by construction (NFR-001). Both
  generic doors — `agent status emit` and `orchestrator-api wp transition` — already
  build a `TransitionRequest` and route through that step, so both get the refusal with
  no per-surface edit (FR-005, FR-009).
- **What stays legal.** `move-task` supplies `review_ref="force-override"` on this edge
  (`tasks_transition_core.build_transition_plan`), so the operator's rewind keeps working
  (FR-008). Pinning that ratchet exposed a second hole: the sentinel was set only for an
explicit `--force`, while an unforced `for_review → in_progress` is *auto-promoted* to
  `emit_force=True` and wrote the same invalid row. The plan now fills its existing
  sentinel whenever it emits force on this edge (research D-7), so the conforming surface
  becomes conforming. Every other forced edge — `done`/`canceled` force-exits, `planned →
  in_progress`, `for_review → planned`, `in_review → in_progress` — is outside the new
  edge set or outside the requirement (FR-007).
- **Whitespace.** The predicate strips, matching the `review_ref.strip()` convention the
  `approved` state's guard already uses (`wp_state.ApprovedState.guard_for`), so
  `--review-ref "   "` is absent.
- **No recovery machinery is added.** The issue asks for the *documented* position on
  rows already written, not for a byte-rewriting repair. Recovery stays append-only and
  auditable (C-002); what ships here is the refusal plus the documentation.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich (existing); no dependency added, upgraded or removed
**Storage**: `status.events.jsonl` + `status.json` in the mission's status surface (unchanged shape)
**Testing**: pytest, red-first per WP; `tests/status/test_validate.py`,
`tests/status/test_wp_state_force_free_contract.py`, `tests/status/test_agent_status_emit_cli.py`,
a new `tests/status/test_forced_rewind_requires_review_ref.py`, and the `move-task` ratchet
`tests/specify_cli/cli/commands/agent/test_move_task_done_exit.py`
**Target Platform**: Linux, macOS, Windows 10+ (inherited CLI envelope)
**Project Type**: single (CLI)
**Performance Goals**: no measurable change on the legal path — the rule reads the
request already in hand, with no extra file or subprocess work (NFR-002)
**Constraints**: refused command writes zero bytes (NFR-001); complexity ≤ 15; diff
coverage ≥ 90% on changed lines
**Scale/Scope**: 3 source modules (`status/wp_state.py`, `status/validate.py`,
`cli/commands/agent/tasks_transition_core.py`), 1 message constant, 1 doc page, changelog

## Charter Check

| Gate | Status |
|---|---|
| Single canonical authority | Pass — one predicate owns "this edge requires `review_ref`"; both the writer and the auditor read it (C-001, FR-006). |
| Architectural alignment | Pass — the change stays inside `specify_cli.status`; `validate.py → wp_state.py` is an existing import direction; no new package edge. |
| Domain-driven splits + tiered rigour | Pass — the rule belongs to the aggregate's FSM (domain logic), not to a CLI shell. |
| ATDD-first | Pass — WP01 opens with the failing CLI acceptance test from the issue's own reproduction. |
| Terminology canon | Pass — Mission/lane vocabulary only; no `feature*` identifier introduced. |
| Append-only history | Pass — no historical event byte is read-modify-written; the diff never touches an existing `status.events.jsonl` (C-002). |
| No full heavy suites in mission | Pass — named test files only, plus the `move-task` ratchet file. |
| No force-policy widening | Pass — the change removes one illegal admission and grants force nothing new (C-003). |

Post-design re-check: no new violations. No ADR is needed: this narrows an existing
invariant onto its owning surface rather than changing an architectural boundary.

## Project Structure

### Documentation (this mission)

```
kitty-specs/reject-invalid-forced-status-rewind-01M68J8B/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/forced-rewind-refusal.md
└── tasks.md            # /spec-kitty.tasks
```

### Source Code (repository root)

```
src/specify_cli/status/wp_state.py       # REVIEW_REF_REQUIRED_EDGES, requires_review_ref, check_transition ordering, message
src/specify_cli/status/validate.py       # validate_event_schema reads the shared predicate
src/specify_cli/cli/commands/agent/tasks_transition_core.py  # fill the existing force-override sentinel whenever the plan emits force on this edge
docs/architecture/status-model.md        # guard table row + refusal + append-only recovery position
docs/changelog/CHANGELOG.md              # [Unreleased] Fixed, (#6514)
tests/status/test_forced_rewind_requires_review_ref.py   # red-first CLI acceptance + unit pins
tests/status/test_validate.py            # auditor side reads the same predicate
tests/status/test_wp_state_force_free_contract.py    # force-insurmountable pin
```

**Structure Decision**: single project; files above. No new module — the rule belongs in
the FSM that already owns edge legality.

## Implementation Concern Map

### IC-01 — The shared requirement and the admission order

- **Purpose**: Give "`for_review → in_progress` requires a `review_ref`" one owning
  definition and enforce it on the writer's admission path before force is consulted.
- **Relevant requirements**: FR-001, FR-003, FR-005, FR-006, FR-007, FR-008; C-001, C-003; NFR-002
- **Affected surfaces**: `src/specify_cli/status/wp_state.py`,
  `src/specify_cli/status/validate.py`,
  `src/specify_cli/cli/commands/agent/tasks_transition_core.py`
- **Sequencing/depends-on**: none
- **Risks**: reordering `check_transition` can silently change the message a force-free
  attempt sees. Pin the untouched non-force message on the same fixture. A guard must not
  consult `ctx.force` (`wp_state.py` §"NB: guards must NOT consult `ctx.force`"), so the
  requirement is evaluated in `check_transition`, never inside `guard_for`.

### IC-02 — The red-first acceptance proof

- **Purpose**: Witness the issue's own reproduction failing through the real CLI, then
  prove the refusal writes nothing, then prove the pointer-carrying rewind still lands.
- **Relevant requirements**: FR-002, FR-004, FR-009; SC-001, SC-002, SC-003, SC-004, SC-005; NFR-001, NFR-003
- **Affected surfaces**: `tests/status/test_forced_rewind_requires_review_ref.py`, plus the
  `move-task` ratchet file already in the tree
- **Sequencing/depends-on**: IC-01 (the refusal must exist for the positive control to
  distinguish "refused" from "cannot see an append")
- **Risks**: a refusal test without a same-fixture positive control is vacuous. Both
  assertions must run on one fixture, and the "nothing written" assertion must be a
  digest comparison, not a row-count guess.

### IC-03 — The operator-facing position

- **Purpose**: State the refusal and, for rows already written before this fix, the
  no-rewrite rule and the supported append-only route.
- **Relevant requirements**: FR-010; SC-006; C-002, C-004
- **Affected surfaces**: `docs/architecture/status-model.md`, `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-01 (the documented rule must match the shipped message)
- **Risks**: documenting a repair the tool does not ship would be fabricated capability.
  The page must say plainly what exists and what a maintainer must author.

## Complexity Tracking

No charter violations to justify.

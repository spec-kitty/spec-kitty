# Implementation Plan: Wire-valid approved reopen

**Branch**: `kitty/mission-wire-valid-approved-reopen-01M6EJW0` | **Date**: 2026-11-02 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/wire-valid-approved-reopen-01M6EJW0/spec.md`

## Summary

One owning definition (`status/wp_state.py::REVIEW_REF_REQUIRED_EDGES`) decides which
`-> in_progress` rewinds must carry a `review_ref`. It currently lists only
`for_review -> in_progress`, while the pinned `spec_kitty_events` contract gates the whole
review-ref-gated rewind family, of which this mission closes `for_review` and `approved` and
defers `in_review` to #7080 (its evidence is a structured `review_result` the emit path does
not yet turn into a `review_ref`). The emitter
(`build_transition_plan`), the writer (`WPState.check_transition`) and the auditor
(`validate_event_schema`) all read that one set, so three things follow from widening it:

1. the emitted forced `approved -> in_progress` payload gets the established
   `force-override` sentinel instead of `review_ref: null` (the reported defect);
2. the writer refuses a pointerless gated rewind on every door before the append, so no
   door can poison the append-only ledger;
3. the auditor reports legacy pointerless rows of the family, which the reference
   documents as an append-only, no-rewrite position.

No policy change: the forced arm survives (spec § "The decision the issue asks for"), the
evidence arm is untouched, and the vendored contract is consumed, not changed.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: `spec-kitty-events` (pinned; `spec_kitty_events.status` is the
wire contract), Typer CLI, pytest
**Storage**: append-only `status.events.jsonl` per mission + materialized `status.json`
**Testing**: pytest; `fast` unit pins under `tests/status/` and `tests/specify_cli/status/`,
one git-backed owned-checkout integration test under `tests/integration/`
**Target Platform**: Linux CLI (`spec-kitty` 4.0.0rc8)
**Project Type**: single Python package (`src/specify_cli`)
**Performance Goals**: the widened predicate adds no I/O, subprocess or network call on the
transition path (it is a frozenset membership test)
**Constraints**: append-only event log; the `spec-kitty-events` pin and the frozen events
surface (ADR `2026-10-29-1`) are untouched; no version bump
**Scale/Scope**: one predicate, three call sites already reading it, one emitter branch
already keyed on it, docs, tests

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan satisfies it |
|---|---|
| Single canonical authority | The edge set stays in `wp_state.py`; the emitter, writer and auditor keep reading it. No second literal set anywhere (`C-004`). |
| `change-apply-smallest-viable-diff` / locality of change | One frozenset gained two members; the emitter's existing sentinel fill and the writer's existing force-insurmountable check do the work. No new guard, no new module. |
| ATDD-first / test-first bug fixing | The red test drives the pre-existing entry point (owned-checkout `move-task`, then `agent status emit`), fails on the pre-fix tree, and the fix is what turns it green. |
| No widening of force reach | The change narrows one illegal write and cites an existing reference; it grants force nothing new (`C-002`). |
| Brownfield evidence | Grounding probes (below) are recorded in `research.md` with the exact rows and validator verdicts, not prose. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | Targeted suites only; CI owns the full sweep. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/wire-valid-approved-reopen-01M6EJW0/
├── plan.md              # This file
├── research.md          # Phase 0: grounding probes + contract evidence
├── data-model.md        # Phase 1: the predicate, the plan, the event, the sentinel
├── quickstart.md        # Phase 1: how a reviewer reproduces and verifies by hand
├── contracts/
│   └── review-ref-gated-rewind.md   # The frozen shape this mission pins
└── tasks.md             # Phase 2 output (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/specify_cli/
├── status/
│   ├── wp_state.py            # REVIEW_REF_REQUIRED_EDGES (the one definition) + docstring
│   └── validate.py            # auditor docstring that names the same set
├── cli/commands/agent/
│   └── tasks_transition_core.py   # sentinel fill comment (behaviour follows the set)
docs/
├── architecture/status-model.md   # gated family, per-writer pointer, append-only position
└── changelog/unreleased/<pr>.fixed.md
tests/
├── status/test_forced_rewind_requires_review_ref.py   # door refusals + family ratchet
├── specify_cli/status/test_wp_state.py                # writer unit pins
└── integration/test_owned_reopen_feedback.py          # the reported repro through move-task
```

## Phase 0 — Research (see `research.md`)

Grounding on `main` @ `9aed3a8012` (the mission's merge base) established:

- the issue reproduces through the production planner and writer, and the payload is
  wire-invalid with and without `force` (probe output recorded verbatim);
- the pinned contract's "Review-Ref-Gated Rewind Family" declares three edges and states
  the requirement holds whether or not the event is forced;
- `start_implementation_status` already stamps `force-override` on the same
  `approved -> in_progress` forced withdraw, so the conforming shape exists in-tree;
- 91 historical rows across committed mission logs sit on the family with
  `review_ref: null`, which the widened auditor will report — a documented, append-only
  position, not a rewrite.

## Phase 1 — Design (see `data-model.md`, `contracts/`)

The design is one predicate, one emitter rule and one refusal message:

- `REVIEW_REF_REQUIRED_EDGES = {(for_review, in_progress), (approved, in_progress)}` —
  exactly the edges this mission claims, no more (`C-006`); the contract's third gated
  edge, `in_review -> in_progress`, is deferred to #7080 and pinned as still admitted;
- `build_transition_plan`'s existing fill (`emit_force and requires_review_ref(...)` ⇒
  `force-override` when no pointer was supplied) now covers the approved reopen;
- `WPState.check_transition`'s existing force-insurmountable branch refuses a pointerless
  gated rewind with the existing `review_ref_required_message`, before any append;
- a supplied `--review-feedback-file` still wins: it reaches the plan as the pointer, so
  the row cites the real file and stays force-free (the evidence arm).

## Implementation Concern Map

| Concern | Where | Guarded by |
|---|---|---|
| IC-01 The one definition covers the contract's family | `status/wp_state.py` | family ratchet test that reads the pinned package |
| IC-02 The forced approved reopen cites the sentinel | `tasks_transition_core.py` (existing fill) | owned-checkout `move-task` repro + wire-validity assertion |
| IC-03 Every door refuses before the append | `status/wp_state.py` (writer) | `agent status emit` fixture: refusal + SHA-256 identity + pointer-carrying positive control |
| IC-04 Legacy rows and the recovery position are documented | `docs/architecture/status-model.md` | doc grep test |

## Risks

| Risk | Mitigation |
|---|---|
| Widening the auditor flags historical committed rows (91 across `kitty-specs/`) | The auditor is not run repo-wide in CI; the reference documents the append-only position. Verified no CI step validates the committed corpus. |
| The sibling `in_review` edge drags unrelated refusals | It is deliberately out of the set; `NFR-003` pins every pair's verdict, including `in_review -> in_progress` staying admitted (#7080), so an accidental widening or narrowing shows up. |
| A reviewer reads the sentinel as a fabricated pointer | The sentinel is an existing sanctioned member of `REVIEW_REF_FEEDBACK_SENTINELS`; `agent action implement` already emits it on this exact hop; the docstring and docs say it is non-resolvable. |
| Someone "fixes" the contract instead | `C-001` and `FR-009`: a ratchet asserts the pinned package's family is read, not patched, and the diff touches no pin or vendored file. |

## Testing strategy (targeted)

- `tests/integration/test_owned_reopen_feedback.py::test_owned_approved_reopen_feedback_contract[absent]`
  — the reported repro; gains the sentinel + wire-validity assertions.
- `tests/status/test_forced_rewind_requires_review_ref.py` — extended to the family: refusal
  on each gated edge through `agent status emit`, pointer-carrying positive control on the
  same fixture, and the ratchet that the local set equals the pinned contract's family.
- `tests/specify_cli/status/test_wp_state.py` — writer pins for the two added edges with the
  family's force-insurmountable message.
- `tests/status/test_validate.py` — the auditor reports a pointerless family row and stays
  silent on a pointer-carrying one.
- Docs grep test in `tests/status/` for the reference's family statement.

Not run locally: the full suite (charter `NO_FULL_HEAVY_SUITES_IN_MISSION`); CI owns it.

## Phase 2 — Tasks

Single work package candidate (`WP01`): predicate + emitter conformance + door refusals +
docs + tests. Slicing is decided in `tasks.md`; nothing here needs a second package.

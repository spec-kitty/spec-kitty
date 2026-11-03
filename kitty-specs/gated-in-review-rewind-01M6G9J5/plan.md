# Implementation Plan: Gated in_review rewind

**Branch**: `issue-7080-gated-in-review-rewind` | **Date**: 2026-11-03 | **Spec**: `kitty-specs/gated-in-review-rewind-01M6G9J5/spec.md`
**Input**: Mission specification from `kitty-specs/gated-in-review-rewind-01M6G9J5/spec.md`

## Summary

Two halves that only work together, as the issue states. First, the status emit path learns
what `move-task` already does: `prepare_transition` derives the wire `review_ref` from
`review_result.reference` when the caller supplied no pointer. Second, `in_review ->
in_progress` joins `REVIEW_REF_REQUIRED_EDGES`, so the writer refuses a pointerless rewind
before the append and the auditor reports a stored one. The #6955 deferral pin flips
deliberately, and the ratchet becomes merge-order independent so the pending `approved` edge
(#6955 / PR #7102) cannot falsify it.

## Technical Context

**Language/Version**: Python 3.11 (repo `.python-version`)
**Primary Dependencies**: `spec-kitty-events` (the pinned wire contract, read not modified), Typer CLI
**Storage**: append-only `status.events.jsonl` + derived `status.json` per mission
**Testing**: pytest; `fast` and `integration` marks per `pytest.ini`; golden FSM parity fixture `tests/status/fsm_parity_baseline.jsonl`
**Target Platform**: Linux CI (GitHub Actions), CLI + hosted-sync consumer
**Project Type**: single Python project (`src/specify_cli`, `tests/`)
**Performance Goals**: no new I/O on the decision path (NFR-002); the derivation is a field read
**Constraints**: the vendored contract is consumed, never changed (C-001); no gate weakened (C-002); append-only history (C-003)
**Scale/Scope**: one edge, one derivation seam, one golden-fixture amendment, one reference page, one changelog fragment

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — the gate stays in `REVIEW_REF_REQUIRED_EDGES`
  (`status/wp_state.py`), which the writer and the auditor both read; the pointer derivation
  goes into `status/transition_pipeline.prepare_transition`, the tree's only
  validation/event-build authority (contract `contracts/emit-pipeline.md` §1). No second
  literal, no per-door rule. **PASS**
- **ATDD-first** (DIRECTIVE_034, `test-first-bug-fixing`) — each half is red first through a
  pre-existing entry point (`agent status emit`, `prepare_transition`, the writer, the
  auditor, the golden parity fixture) before the fix. **PASS**
- **Locality of change** (DIRECTIVE_024) — two source files, one golden fixture, the reference
  page it changes, and the tests that pin them. No contract, no pin, no dependency bump. **PASS**
- **Terminology canon** — "Mission", "work package"/"WP", "lane" only. **PASS**
- **Test economy** (DIRECTIVE_041) — one new test file section for the half that is new
  behaviour; existing pins are flipped in place rather than duplicated. **PASS**

## Project Structure

### Documentation (this mission)

```
kitty-specs/gated-in-review-rewind-01M6G9J5/
├── plan.md              # This file
├── spec.md              # Mission specification
├── tasks.md             # Task/WP decomposition (tasks step)
└── traces/              # approach / design-decisions / tooling-friction
```

### Source Code (repository root)

```
src/specify_cli/status/
├── transition_pipeline.py   # prepare_transition: derive review_ref from review_result.reference
├── wp_state.py              # REVIEW_REF_REQUIRED_EDGES gains (IN_REVIEW, IN_PROGRESS)
└── validate.py              # auditor docstring names the widened edge set

tests/status/
├── fsm_parity_baseline.jsonl               # 4 golden rows move (in_review -> in_progress/doing)
├── test_forced_rewind_requires_review_ref.py  # deferral pin flips; derivation + door tests
└── test_transition_pipeline.py             # pipeline purity / derivation probe

docs/architecture/status-model.md            # gated family, pointer per writer, recovery position
docs/changelog/unreleased/<pr>.fixed.md      # per-PR fragment
```

**Structure Decision**: single project; the change stays inside the `status` package and the
tests/docs that pin it.

## Complexity Tracking

No charter violations.

## Implementation Concern Map

### IC-01 — The pointer reaches the wire

- **Purpose**: Make every status door record the review reference the caller already supplied
  in structured form, so an `in_review` exit can be gated without refusing a legitimate write.
- **Relevant requirements**: FR-001, FR-007, FR-009, NFR-002, C-002, C-004
- **Affected surfaces**: `src/specify_cli/status/transition_pipeline.py` (`prepare_transition`
  and a module-private helper), `tests/status/` pipeline + CLI door tests
- **Sequencing/depends-on**: none
- **Risks**: the derivation must fill only an *absent* pointer, otherwise it would override a
  caller's `--review-ref` or silence the existing `review_ref == review_result.reference`
  consistency refusal.

### IC-02 — The edge is gated, its pin flips deliberately

- **Purpose**: Refuse a pointerless `in_review -> in_progress` before the append, report a
  stored one, and move the #6955 deferral pin without letting it flip silently in either
  direction.
- **Relevant requirements**: FR-002, FR-003, FR-004, FR-005, FR-006, FR-008, NFR-001,
  NFR-003, C-001, C-003, C-005, C-006
- **Affected surfaces**: `src/specify_cli/status/wp_state.py`,
  `src/specify_cli/status/validate.py`, `tests/status/fsm_parity_baseline.jsonl`,
  `tests/status/test_forced_rewind_requires_review_ref.py`, `tests/status/test_transitions.py`
  (amendment note), `docs/architecture/status-model.md`, the changelog fragment
- **Sequencing/depends-on**: IC-01 (gating before the pointer derivation would refuse the
  legitimate structured write the issue names)
- **Risks**: the exact-set ratchet #6955 adds in PR #7102 must not be duplicated here; this
  branch asserts membership + subset-of-contract, never an exact set, so either merge order
  keeps both pins true.

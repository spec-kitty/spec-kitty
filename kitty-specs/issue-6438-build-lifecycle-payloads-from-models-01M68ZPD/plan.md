# Implementation Plan: Model-built payloads for the three post-mission lifecycle events

**Branch**: `issue-6438-build-lifecycle-payloads-from-models` | **Date**: 2026-10-31 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/issue-6438-build-lifecycle-payloads-from-models-01M68ZPD/spec.md`

## Summary

Three emitters in `src/specify_cli/status/lifecycle_events.py`
(`emit_reviewer_self_approval`, `emit_mission_reopened`,
`emit_follow_up_recorded`) build their payload as a bare `dict`, so a field the
published `spec_kitty_events` contract rejects is written to
`status.events.jsonl` and only detected later, on the consumer side. The plan is
to construct each payload from its canonical model
(`ReviewerSelfApprovalPayload`, `MissionReopenedPayload`,
`FollowUpRecordedPayload`) and persist `model_dump(mode="json",
exclude_none=False)` — the idiom the file's other three emitters already use —
leaving the envelope, the append primitive, the dedup keys and the emitters' own
pre-checks untouched. Tests pin both directions: the model dump is what lands,
and a model-invalid field raises before anything lands.

## Technical Context

**Language/Version**: Python 3.11+ (repo targets 3.11/3.12; `from __future__ import annotations`)
**Primary Dependencies**: `spec-kitty-events>=11.3.0,<12` (pydantic v2 models); `typer` CLI; `kernel.clock`
**Storage**: append-only JSONL — `<mission>/status.events.jsonl`, `.kittify/canonical-events.jsonl`
**Testing**: pytest, `pytest.mark.fast`; module tests under `tests/specify_cli/status/`
**Target Platform**: CLI (any OS the CLI supports)
**Project Type**: single project (`src/specify_cli/`)
**Performance Goals**: unchanged — payload construction is one pydantic validation per emitted event; emit is already a locked append
**Constraints**: no envelope/schema_version change, no new dependency, no private `spec_kitty_events` symbol
**Scale/Scope**: 1 source file, 3 functions; 1 new test module; 1 changelog entry

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Verdict | Evidence |
| --- | --- | --- |
| Canonical authority (DIRECTIVE_044) | Pass | The published `spec_kitty_events` models become the single construction authority in the emitter; no parallel schema is introduced. |
| Locality of change (DIRECTIVE_024) | Pass | Three function bodies in one file, plus tests and a changelog line. No call site, envelope or store change. |
| ATDD-first / red-first (DIRECTIVE_034, charter ATDD-First Discipline) | Pass | The rejected-field tests are written first and fail on the pre-change code (proved in research.md). |
| `__all__` convention (C-007) | Pass | No public name is added or removed; `__all__` untouched. |
| Tests-as-scaffold-not-friction (DIRECTIVE_041) | Pass | One contract-per-emitter test module; each assertion guards a standing invariant (contract conformance, fail-before-write), no shape/`__module__`/delegate pins. |
| No gate weakening (C-004) | Pass | No skip/xfail/marker change; no lint suppression. |
| Shared Package Boundary | Pass | Only public modules (`spec_kitty_events.lifecycle`, `.project_lifecycle`) are imported, function-locally like every sibling emitter; `tests/architectural/test_events_tracker_public_imports.py` stays green. |
| Terminology canon | Pass | "Mission" throughout; no `feature*` identifier introduced. |

No violations, so Complexity Tracking stays empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/issue-6438-build-lifecycle-payloads-from-models-01M68ZPD/
├── plan.md              # this file
├── research.md          # discovery + Phase 0 decisions
├── data-model.md        # the three payload entities and their invariants
├── quickstart.md        # how a reviewer reproduces and verifies
├── contracts/           # payload contract for the three events
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```
src/specify_cli/status/
└── lifecycle_events.py          # the three emitters change; nothing else does

tests/specify_cli/status/
└── test_model_built_payloads_6438.py   # new: model conformance + fail-before-write

docs/changelog/
└── CHANGELOG.md                 # [Unreleased] entry citing #6438
```

**Structure Decision**: single project. The change is confined to
`src/specify_cli/status/lifecycle_events.py`; the new test lives beside the
existing emitter suites in `tests/specify_cli/status/`, which is the mirrored
test tree for that module.

## Design

### The seam

Each emitter keeps its signature, its validation guards and its write call; only
the `payload` mapping changes:

```python
# before
payload: dict[str, Any] = {"mission_id": mission_id, ...}
# after
payload: dict[str, Any] = MissionReopenedPayload(
    mission_id=mission_id, ...
).model_dump(mode="json", exclude_none=False)
```

`model_dump(mode="json", exclude_none=False)` is what `emit_wp_created_local` and
`emit_artifact_phase_local` already do, and it preserves the current key order,
the current key set and the current `null` optionals, so a valid emit persists
byte-identical JSON.

### Order of operations inside each emitter

1. the emitter's own guards (`follow_up_type`/reference, `#1926` completion) —
   unchanged, and deliberately *before* construction so their named messages win;
2. model construction — a rejected field raises `pydantic.ValidationError` here;
3. `append_lifecycle_event(...)` — unchanged, so nothing is written when step 2
   raised.

### Why `ValidationError` is not wrapped

`emit_wp_created_local` and `emit_artifact_phase_local` already let
`ValidationError` escape, and `ValidationError` is a `ValueError`, so any caller
with `except ValueError` is unaffected. Wrapping would add a second failure
surface for one defect class. CLI rendering of that traceback is out of scope and
recorded in research.md as an explicit non-decision.

### Test design (red-first)

New module `tests/specify_cli/status/test_model_built_payloads_6438.py`, three
fixtures (a completed mission directory with `meta.json` for the two mission
emitters; a feature dir for the WP emitter) shared by a positive and a negative
assertion per emitter, so neither can drift:

- **positive**: `emit_*(...)` returns, the persisted row's `payload` equals
  `Model(**fields).model_dump(mode="json", exclude_none=False)`, and the line
  count grew by one;
- **negative**: `emit_*(<field the model rejects>)` raises `ValidationError` and
  the line count is unchanged.

The negative case for each emitter is chosen so that *only* the model can reject
it — never a case the emitter's own guard already covers (an empty `reason`, an
empty `recorded_by`, an empty `failure_reason`, rather than a missing
`pr_number`).

## Complexity Tracking

*No charter-check violations.*

## Implementation Concern Map

### IC-01 — Payload construction through the published models

- **Purpose**: Replace the three hand-built dicts with construction through the canonical model plus a JSON dump, so a contract-invalid payload fails at emit time.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, NFR-002, NFR-003, C-001, C-002
- **Affected surfaces**: `src/specify_cli/status/lifecycle_events.py` (`emit_reviewer_self_approval`, `emit_mission_reopened`, `emit_follow_up_recorded`)
- **Sequencing/depends-on**: none
- **Risks**: The dump must keep the current key order and `None` optionals, or existing ledger consumers and the historical-line comparison break. The emitters' guards must stay ahead of construction.

### IC-02 — Fail-before-write and model-conformance proof

- **Purpose**: Prove, per emitter, that a rejected payload writes nothing and a valid payload writes exactly the model dump.
- **Relevant requirements**: FR-004, FR-005, SC-001, SC-002, SC-003
- **Affected surfaces**: `tests/specify_cli/status/test_model_built_payloads_6438.py`; the pre-existing `test_post_mission_lifecycle_events.py`, `test_merged_at_writer_and_reopen_4090.py`, `test_lifecycle_events.py`
- **Sequencing/depends-on**: IC-01 (the tests are written first and must go green with it)
- **Risks**: A negative case that the emitter's own guard already rejects would pass vacuously before the change — choose fields only the model rejects.

### IC-03 — Operator-facing record

- **Purpose**: Record the user-visible consequence (a contract-invalid lifecycle payload is now refused at emit time) and answer the issue's acceptance items, including item 3's already-done status.
- **Relevant requirements**: SC-004
- **Affected surfaces**: `docs/changelog/CHANGELOG.md` ([Unreleased]); the PR body's `## Change` and `## Deferred`
- **Sequencing/depends-on**: IC-01
- **Risks**: None; keep the entry under 1,200 characters, impact-first, with `(#6438)`.

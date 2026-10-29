# Implementation Plan: Decision-significance adoption

**Branch**: `issue-6445-decision-significance-adoption` | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/decision-significance-adoption-01M5ZMNH/spec.md`

Branch contract: planning starts on `issue-6445-decision-significance-adoption`, plans on it and lands completed work on it (`branch_matches_target: true`). The topic branch later goes to `main` through a pull request; this mission never consolidates into `main`.

## Summary

Lock `spec-kitty-events` at 11.3.0 (done in the first commit of this branch, #6602), raise the supported floor to 11.3.0, and replace core's private decision-significance models with the package's. An authoring-side RACI role (actor id optional) stays local for mission templates and inference input; every resolved or persisted role uses the package `RaciRoleBinding`. The operator-ruled sentinels fill an id only after the existing input lookup fails.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `spec-kitty-events` 11.3.0 (`decision_significance` module), pydantic v2
**Storage**: the run's append-only `events.jsonl` (existing interim append, unchanged) and `MissionRunSnapshot.decisions` (untyped map)
**Testing**: pytest; red-first tests in `tests/next/` and `tests/runtime/`; the event consumer directories from the safe-adoption checklist
**Target Platform**: the `spec-kitty` CLI (Linux, macOS, Windows)
**Project Type**: single project (`src/`, `tests/`)
**Performance Goals**: no new I/O; model construction cost is unchanged
**Constraints**: PyPI-only consumption (C-001); no new write path (C-002); public imports only (C-003); `specify_cli/decisions/` untouched (C-004)
**Scale/Scope**: 5 runtime modules, 1 CLI adapter, 3 test files

## Charter Check

| Charter rule | Status |
|---|---|
| Single canonical authority | Pass: the package becomes the one owner of the significance, timeout and resolved-RACI models; the local copies are deleted, not kept beside it. |
| Architectural alignment / shared-package boundary | Pass: public `spec_kitty_events` imports, released PyPI version, gates `test_shared_package_boundary.py`, `test_pyproject_shape.py`, `test_events_tracker_public_imports.py` in the blast radius. |
| ADR 2026-10-22-1 (one canonical writer) | Pass: no new append path; #6446 deferred (Decision Moment `01M5ZMPFCN3BFSEQ8VTN6MT3HF`). |
| ATDD-first / red-first (Standing Order #4) | Pass: each work package starts with a failing test through the existing entry points (`resolve_raci`, `infer_raci`, the engine's audit-gate and soft-gate paths). |
| Tidy-first (Standing Order #2) | Pass: no preparatory refactor needed (see `research/phase0-grounding.md` §6). |
| Mission tracer files (Standing Order #3) | Seeded in `traces/`. |
| Complexity ≤ 15, ruff, mypy --strict, no new suppressions | Planned; checked at review. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/decision-significance-adoption-01M5ZMNH/
├── spec.md
├── plan.md
├── research/phase0-grounding.md
├── traces/{tooling-friction,approach,design-decisions}.md
├── checklists/requirements.md
└── tasks.md, tasks/            # /spec-kitty.tasks output
```

### Source Code (repository root)

```
pyproject.toml                                  # floor >=11.3.0,<12
tests/architectural/test_pyproject_shape.py     # pinned range
src/runtime/next/_internal_runtime/
├── schema.py        # RACIRoleBinding -> RACIRoleSpec (authoring); ResolvedRACIBinding deleted
├── significance.py  # SignificanceEvaluatedPayload, TimeoutExpiredPayload deleted; SoftGateDecision/DimensionScoreOverride use the package binding
├── raci.py          # resolution returns package models; sentinel fallback helper
├── engine.py        # imports; soft-gate actor via the sentinel helper
└── events.py        # emitter Protocol typed with package payloads
src/specify_cli/events/decision_log.py          # forwarding adapter typing
tests/next/test_internal_runtime_coverage.py
tests/runtime/test_bridge_engine.py
tests/specify_cli/events/test_decision_log.py
```

**Structure Decision**: single project; changes stay inside `runtime.next._internal_runtime` plus its one CLI adapter.

## Design

- **Authoring binding.** `schema.RACIRoleBinding` is renamed `RACIRoleSpec` (same fields: `actor_type`, optional `actor_id`). `RACIAssignment` keeps using it, so mission YAML is unaffected (YAML uses field names only).
- **Resolved binding.** `raci.resolve_raci` returns `spec_kitty_events.decision_significance.ResolvedRaciSnapshot`; `_resolve_actor` / `_resolve_actor_optional` return `RaciRoleBinding`.
  - Responsible and accountable keep the fail-closed `RACIEscalationPayload` path inside `resolve_raci` (unchanged).
  - Consulted and informed fall back to the sentinel instead of a null id.
- **Inferred fallback.** `infer_raci` returns a `ResolvedRaciSnapshot` with every id set to the sentinel for its type. It is built from a private inferred `RACIAssignment` that `resolve_raci` also uses for its inferred path, so input-based resolution still runs first there (FR-005). The engine's two `except MissionRuntimeError` fallbacks keep calling `infer_raci` unchanged.
- **Sentinel helper.** One function `raci.bind_actor(actor_type, actor_id) -> RaciRoleBinding` maps a missing or blank id to `HUMAN_IN_CHARGE_ACTOR_ID` (human) or `UNKNOWN_ACTOR_ID` (llm, service). The engine's soft-gate path (`engine.py:824`) uses it.
- **Payloads.** `engine` builds `spec_kitty_events.decision_significance.SignificanceEvaluatedPayload`; `events.RuntimeEventEmitter.emit_decision_timeout_expired` is typed with `DecisionTimeoutExpiredPayload`. `_record_significance` keeps the existing interim append.
- **Floor.** `pyproject.toml` `spec-kitty-events>=11.3.0,<12`, with `uv lock` refreshed (the lock content stays 11.3.0) and the shape test's pinned range updated.

## Implementation Concern Map

### IC-01 — Supported range

- **Purpose**: make the declared floor match the first published release with the imported symbols.
- **Relevant requirements**: FR-002
- **Affected surfaces**: `pyproject.toml`, `uv.lock`, `tests/architectural/test_pyproject_shape.py`, `.kittify/release/shared-package-compatibility.json` (`cli_range`)
- **Sequencing/depends-on**: none (FR-001 already committed)
- **Risks**: the shape test also checks the range contains 11.0.0 for retired-range detection; adjust that probe to the new floor.

### IC-02 — Package models and sentinels

- **Purpose**: delete the local copies and fill every actor id.
- **Relevant requirements**: FR-003, FR-004, FR-005, FR-006
- **Affected surfaces**: `schema.py`, `significance.py`, `raci.py`, `engine.py`, `events.py`, `specify_cli/events/decision_log.py`, `runtime_bridge_retrospective.py` (typing only), the three test files
- **Sequencing/depends-on**: IC-01
- **Risks**: tests that assert the local error wording of provenance violations; tests that construct `RACIRoleBinding` with no id for resolved contexts.

## Complexity Tracking

No charter violations.

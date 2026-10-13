# Implementation Plan: Native stale-content refusal enforcement

**Branch**: `issue-5879-native-stale-content-refusal` | **Date**: 2026-10-12 | **Spec**: `./spec.md`
**Input**: Mission specification from `kitty-specs/native-stale-content-refusal-01M4S2CQ/spec.md`

## Summary

Move the marker-gated stale/unfinished-content refusal (`validate_stage`) off the
orchestrator-api-only path and onto the native completion surfaces, so an API-authored Mission
cannot be completed with stale/dirty content by switching from the orchestrator-api to a native
command. Two native surfaces: (1) `spec-kitty next --result success` and (2) the `agent`
lifecycle finalize commands. The enforcement is hoisted to the single top-layer seam both the
native and orchestrator-api `next` paths traverse (`specify_cli/cli/commands/next_cmd.py::
next_step`), and the orchestrator-api's now-redundant local gate is removed so there is one
canonical authority. Native finalize reuses the existing `design.validation.finalization_scope`,
which also makes it take the cooperative `authoring_lock` (closing the writer-takes-no-lock half
of the ADR `2026-10-07-2` race). Grounded by two pre-spec squads (see `grounding-note.md`).

## Technical Context

**Language/Version**: Python 3.11+ (repo is 4.0.0rc7).
**Primary Dependencies**: typer (CLI), existing `specify_cli.design` application seam
(`validation.validate_stage` / `finalization_scope` / `require_unfinalized`, `receipts.authoring_lock`
/ `api_authoring_enabled`), `runtime.next.runtime_bridge_query.issued_step_id_for_mission`.
**Storage**: Git-common-dir host receipts + `.enabled` marker (existing); status event log (existing).
**Testing**: pytest; ATDD red-first in `tests/specify_cli/orchestrator_api/test_planning_client_journey.py`;
unit assertions in `tests/specify_cli/design/test_design_authoring.py`; `make test-fast` baseline;
targeted orchestrator-api / native-next / finalize dirs; specific architectural gate files only.
**Target Platform**: CLI (Linux/macOS/Windows).
**Project Type**: single project.
**Performance Goals**: CLI < 2s typical; the added gate is a read-only prerequisite proof, no new I/O
beyond the existing `validate_stage` reads.
**Constraints**: mypy --strict + ruff clean, no new suppressions; complexity ≤ 15; layer boundary
(C-001); no orchestrator-api behaviour change (C-002); scope boundary (C-003).
**Scale/Scope**: ~2 production files changed (`next_cmd.py`, the native finalize body) + remove the
api `_completion_gate`; ~2 new red-first test cases + unit assertions.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **ATDD-first (C-011)**: red-first native cases committed before the fix; reviewer verifies RED on
  `planning_base_branch`, GREEN on final. PASS (planned).
- **Single canonical authority / reconcile-don't-duplicate (DIRECTIVE_044)**: one enforcement site;
  the api `_completion_gate` is removed, not duplicated. PASS.
- **Architectural alignment (DIRECTIVE_001)**: seam placed in the top layer; runtime layer untouched;
  `test_layer_rules.py` stays green. PASS (verified in grounding).
- **No suppressions / tiered rigour**: core-domain change → full rigour, zero `# noqa`/`# type: ignore`
  additions. PASS (planned).
- **Terminology canon**: Mission (not Feature); no retired terms. PASS.
- **No full heavy suites in mission work**: targeted files + specific gate files only. PASS.

No violations → Complexity Tracking empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/native-stale-content-refusal-01M4S2CQ/
├── spec.md
├── plan.md                 # this file
├── grounding-note.md       # pre-spec squads + verification
├── tracers/                # tooling-friction / approach / design-decisions
└── tasks.md                # created by the tasks step
```

### Source Code (repository root)

```
src/specify_cli/
├── cli/commands/
│   ├── next_cmd.py                      # IC-01: add the marker-gated completion gate to next_step
│   └── agent/
│       ├── tasks_finalize.py            # IC-02: wrap native finalize in finalization_scope
│       └── mission_finalize.py          # IC-02: (same, mission finalize-tasks entry)
├── orchestrator_api/
│   └── runtime_next.py                  # IC-01: remove the now-redundant _completion_gate
└── design/
    ├── validation.py                    # reused (validate_stage / finalization_scope); no new authority
    └── receipts.py                      # reused (authoring_lock / api_authoring_enabled)

tests/
├── specify_cli/orchestrator_api/test_planning_client_journey.py   # red-first native cases
├── specify_cli/orchestrator_api/test_runtime_next.py              # reflect gate relocation
└── specify_cli/design/test_design_authoring.py                    # read-only + marker-gate unit asserts
```

**Structure Decision**: single project; changes are confined to the `specify_cli` top layer
(`cli/commands` + `orchestrator_api`) reusing the existing `specify_cli.design` seam. No new modules.

## Complexity Tracking

*No Charter Check violations — section intentionally empty.*

## Implementation Concern Map

> Concerns are not work packages. The tasks step translates these into WPs.

### IC-01 — Native `next` completion gate (shared seam)

- **Purpose**: Make `next_cmd.next_step` enforce the marker-gated `validate_stage` on `--result success`, so native `next` and the orchestrator-api `next` verb (which calls `next_step` in-process) share one enforcement authority; remove the api `_completion_gate`.
- **Relevant requirements**: FR-001, FR-002, FR-003; NFR-001, NFR-002; C-001, C-002.
- **Affected surfaces**: `src/specify_cli/cli/commands/next_cmd.py`, `src/specify_cli/orchestrator_api/runtime_next.py`.
- **Sequencing/depends-on**: none (first).
- **Risks**: root resolution for the marker/receipts (git common dir vs owned checkout); preserving single-JSON stdout + exit/`reason` mapping; reentrant `authoring_lock` nesting with the engine run-cursor lock; dead-symbol gate after removing `_completion_gate`.

### IC-02 — Native `agent` finalize-tasks gate + cooperative lock

- **Purpose**: Wrap native `agent mission finalize-tasks` (when `api_authoring_enabled`) in `design.validation.finalization_scope` (via `native_finalization_scope`; `agent tasks finalize-tasks` is deliberately not wrapped: it needs a hand-authored `tasks.md` the API-authoring flow never produces, so it is not a bypass surface), matching the orchestrator-api `tasks` verb — enforcing `validate_stage("tasks")` and acquiring `authoring_lock`.
- **Relevant requirements**: FR-004, FR-005; NFR-001; C-001, C-003.
- **Affected surfaces**: `src/specify_cli/cli/commands/agent/mission_finalize.py` (`tasks_finalize.py` intentionally untouched).
- **Sequencing/depends-on**: may follow IC-01 (independent, but IC-01 establishes the test fixture pattern).
- **Risks**: success-gated receipt re-stamp must mirror the api verb exactly; non-API-authored missions must stay byte-identical; `finalize-tasks` writes status directly — must not become a second status authority.

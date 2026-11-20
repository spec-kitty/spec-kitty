# Implementation Plan: API-claimed and canceled WPs reach acceptance

**Branch**: `kitty/mission-api-claim-accept-readiness-01M7X6Q6` (target `issue-5781-api-claim-accept-readiness`) | **Date**: 2026-11-20 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/api-claim-accept-readiness-01M7X6Q6/spec.md`

## Summary

The strict accept gate stops reading the snapshot `agent` slot and reads the implementer of record from `status/review_roles` (FR-001). A canceled WP with no implementer is exempt (FR-002). The repair hint is derived from the state machine through a pure `review_roles` helper (FR-003). The API and `agent status emit` claims record `agent` through the one claim-sidecar builder in `status/emit.py` (FR-004). `accept-mission` uses `status_lanes.mission_terminal_acceptability` (FR-005). The `planned` claim release is defined once in `status/` and used by both `move-task` and `orchestrator-api transition --to planned` (FR-006). The contract goes to 1.30.0 (FR-007). Evidence and design rationale: [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, ruamel.yaml, `spec-kitty-events` (consumed unchanged, C-001)
**Storage**: `status.events.jsonl` append-only event log (no schema change)
**Testing**: pytest, ATDD red-first through the real entry points (`orchestrator-api` Typer app, host `accept`, `move-task`, `agent status emit`) on real git fixtures; unit tests for the pure helpers
**Target Platform**: Linux, macOS, Windows (CLI)
**Project Type**: single
**Performance Goals**: no added event-log read in the accept gate (NFR-001)
**Constraints**: no reducer change in `spec_kitty_events`; ruff/format/mypy clean (NFR-002); diff coverage >= 90% (NFR-003)
**Scale/Scope**: about 8 source modules, about 6 test modules plus fixture updates

## Charter Check

- Single canonical authority: the implementer is read through `review_roles` only, the claim sidecar is built by one builder, and the planned release is defined once. Pass.
- Architectural alignment: all changes stay in `specify_cli` (`status`, `acceptance`, `orchestrator_api`, `cli/commands/agent`); no layer rule changes. Pass.
- ATDD-first: each WP opens with a red acceptance-test commit through the pre-existing entry point. Pass.
- Terminology: Mission/work package; no `feature` aliases added. Pass.
- Campsite (Standing Order #2): `summary_core.build_work_package_state` gains a parameter and loses the slot-based branch, so its complexity drops; the false comment at `:120-127` is rewritten. `tasks_move_task_hops._build_claim_review_override` shrinks to a call into the shared release helper.
- Standing Order #3: tracer files in `traces/`.

## Project Structure

### Documentation (this mission)

```
kitty-specs/api-claim-accept-readiness-01M7X6Q6/
├── spec.md  plan.md  research.md  data-model.md  quickstart.md
├── contracts/orchestrator-api-1.30.0.md
├── traces/ (tooling-friction.md, approach.md, design-decisions.md)
└── tasks.md, tasks/ (from /spec-kitty.tasks)
```

### Source Code (repository root)

```
src/specify_cli/status/emit.py                      # claim_policy_metadata: optional shell_pid, extra policy
src/specify_cli/status/claim_release.py (new)       # planned_claim_release_delta() — the one release authority
src/specify_cli/status/review_roles.py              # implementer_claim_target(lane)
src/specify_cli/status/__init__.py                  # re-exports
src/specify_cli/orchestrator_api/wp_lifecycle.py    # start-implementation / transition claim sidecar + planned release
src/specify_cli/orchestrator_api/consolidation.py   # accept_mission acceptable-ending aggregate
src/specify_cli/orchestrator_api/envelope.py        # CONTRACT_VERSION 1.30.0
src/specify_cli/cli/commands/agent/status.py        # emit --to claimed claim sidecar
src/specify_cli/cli/commands/agent/tasks_move_task_hops.py  # reuse the release helper
src/specify_cli/consolidation/done_bookkeeping.py   # reviewer fallback reads the approving actor (risk fold)
src/specify_cli/acceptance/summary_core.py          # gate via implementer, canceled exemption, derived hint
src/specify_cli/acceptance/__init__.py              # pass implementer per WP from the stream already read
src/charter/offering/skills/spec-kitty-orchestrator-api-operator/references/orchestrator-api-contract.md
tests/utils.py                                      # seed a real claim event (masking fixture)
```

## Complexity Tracking

No charter violations.

## Implementation Concern Map

### IC-01 — One claim sidecar for every claim path

- **Purpose**: every `planned -> claimed` write records `agent` the same way, so the snapshot, the views and the ownership guard see an owner.
- **Relevant requirements**: FR-004, FR-007
- **Affected surfaces**: `status/emit.py`, `orchestrator_api/wp_lifecycle.py`, `cli/commands/agent/status.py`, `orchestrator_api/envelope.py`, `consolidation/done_bookkeeping.py`
- **Sequencing/depends-on**: none
- **Risks**: the ownership guard now binds API-claimed WPs (intended parity). The done-bookkeeping reviewer fallback would read the implementer; it is folded to read the approving actor.

### IC-02 — One planned-release authority

- **Purpose**: a move into `planned` releases the claim slots on every path.
- **Relevant requirements**: FR-006
- **Affected surfaces**: new `status/claim_release.py`, `tasks_move_task_hops.py`, `orchestrator_api/wp_lifecycle.py`
- **Sequencing/depends-on**: none (same files as IC-01, so same WP)
- **Risks**: must not clear `implementer_of_record` (#4786); the release slots are only `agent`/`shell_pid`/`shell_pid_created_at`.

### IC-03 — Accept readiness from the implementer authority

- **Purpose**: the strict gate, the canceled exemption, the derived hint and accept-mission terminality.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-005
- **Affected surfaces**: `acceptance/summary_core.py`, `acceptance/__init__.py`, `status/review_roles.py`, `orchestrator_api/consolidation.py`, `tests/utils.py`
- **Sequencing/depends-on**: none for correctness. The contract-version comment block lands in IC-01's WP; this concern adds its line to that block.
- **Risks**: masking fixtures seed forced events with no implementing claim, so they must seed a real claim. The #4934 test is re-ruled.

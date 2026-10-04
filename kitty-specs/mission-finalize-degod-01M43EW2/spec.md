# Mission Specification: Decompose mission_finalize god-module

**Mission Branch**: `claude/modest-keller-6mvhd4` (single_branch topology)
**Created**: 2026-10-04
**Status**: Draft
**Input**: Issue #5627 — "Investigate & refactor: mission_finalize.py god-module (5,678 LOC)", plus operator steer: pure, behaviour-preserving phase extraction.

## Intent Summary

- **Primary actor**: a Spec Kitty maintainer changing `finalize-tasks` behaviour (for example the later plan/apply split, #5343).
- **Trigger**: the maintainer needs to change one finalize phase (planning-commit pin, commit pipeline, validation gates, ...) without reading a 5,678-line module.
- **Desired outcome**: each finalize phase lives in its own cohesive module. The command module stays a thin orchestrator. Operators see identical `finalize-tasks` behaviour.
- **Invariant**: behaviour is unchanged. Every import and test patch that targets `mission_finalize.<name>` keeps resolving **and** keeps intercepting.
- **Boundary**: no size limit or ratchet gate is added, and the #5343 plan/apply split is out of scope (decision `01M43EWG64HEBHVZ9T2HE4RJ45`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Change one finalize phase in isolation (Priority: P1)

A maintainer opens the module that owns the phase they need to change (for example the planning-commit pin). They change it there without touching the command module or unrelated phases.

**Why this priority**: this is the cohesion debt the issue names. Without it the later #5343 work starts from a god-module.

**Independent Test**: each phase module can be imported on its own, and the family's focused tests pass.

**Acceptance Scenarios**:

1. **Given** the refactored tree, **When** a maintainer looks for the planning-commit pin logic, **Then** it is in one dedicated module, not in the command module.
2. **Given** the refactored tree, **When** the command module is read, **Then** it holds only the command, its context/phase orchestration and the artifact-collection helpers.

### User Story 2 - Operators see no behaviour change (Priority: P1)

An operator runs `spec-kitty agent mission finalize-tasks` (with or without `--json`, `--validate-only`, `--refresh-planning-commit`). They get byte-identical results, refusals and exit codes.

**Why this priority**: the issue requires identical behaviour, and finalize has a history of regressions (#3311, #5573).

**Independent Test**: the existing finalize test corpus passes unchanged, apart from tests that read the source file or patch a moved name directly.

**Acceptance Scenarios**:

1. **Given** the existing finalize behavioural tests, **When** they run against the refactor, **Then** they pass with no assertion changes.
2. **Given** a test that patches `mission_finalize._emit_json` (or another historical seam), **When** the patched code path runs inside a phase module, **Then** the patch intercepts the call.

### User Story 3 - Structural guards keep watching the moved code (Priority: P2)

Architectural pins that read finalize source (pin authority, commit-outcome consumers, coord-writer census, guard-capability call sites, issue-matrix reader) keep covering every relocated function.

**Why this priority**: a pin that silently loses coverage is worse than a failing one.

**Independent Test**: each re-pointed pin passes and still finds the function or call site it guards in the moved module.

**Acceptance Scenarios**:

1. **Given** a guard that counted `_bootstrap_canonical_state_via_mission` call sites in one file, **When** call sites move to phase modules, **Then** the guard scans each module that holds one.

### Edge Cases

- A test patches an imported library name on `mission_finalize` (for example `status_entries` or `classify_recorded_pin`) that the command module no longer calls itself. It must stay a module attribute and still intercept.
- Log records must keep the `specify_cli.cli.commands.agent.mission_finalize` logger name, so caplog filters keep matching.
- Importing a phase module first, before `mission_finalize`, must not cause an import cycle.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Phase modules | As a maintainer, I want each finalize phase (shared seams, branch contract, validation gates, bootstrap/ownership, planning-commit pin, lanes, commit pipeline) in its own sibling module, so that I can change one phase in isolation. | High | Open | [build] | no — the command module must shrink, and each phase function must be defined in its new module |
| FR-002 | Stable re-export surface | As a maintainer, I want `mission_finalize` to re-export every name a phase module defines, so that existing imports keep working. | High | Open | [build] | no — an identity check per name fails if any name is missing |
| FR-003 | Patch interception preserved | As a test author, I want a patch on `mission_finalize.<name>` to intercept calls made from inside a phase module, so that existing seam tests keep exercising the real paths. | High | Open | [build] | no — paired interception tests patch the seam and assert that the phase-module call was captured |
| FR-004 | Thin command module | As a maintainer, I want the command module to keep only the command, its context/phase orchestration and the artifact helpers. | Medium | Open | [build] | no — measured by the command module's line count after the split |
| FR-005 | Structural pins follow the code | As a reviewer, I want every source-reading pin re-pointed at the module that now holds its target, without losing coverage. | High | Open | [build] | no — each pin must still find its target; a vacuous pin fails its own "found" assertion |
| FR-006 | Developer documentation | As a maintainer, I want the finalize internals doc to carry a module map, so that I can find a phase quickly. | Low | Open | [build] | yes — documentation only, checked by review and the docs freshness gate |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Behaviour parity | 100% of the pre-existing finalize behavioural tests pass with zero assertion edits. The only test edits allowed are re-pointing source paths and widening scanned modules. | Reliability | High | Open |
| NFR-002 | Command module size | The command module drops from 5,678 lines to at most 1,600 lines. | Maintainability | Medium | Open |
| NFR-003 | Static quality | 0 ruff findings, 0 mypy findings across the finalize module family, and complexity stays at 15 or below. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No size gate | No line-count limit or ratchet gate is added (issue #5627). | Business | High | Open |
| C-002 | Not the plan/apply split | The #5343 plan/apply split is out of scope. Phase bodies move verbatim. | Technical | High | Open |
| C-003 | Layering | The enforced layering (`kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli`) and the status model are untouched. New modules live in `specify_cli/cli/commands/agent/`. | Technical | High | Open |
| C-004 | Cycle-safe routing | Phase modules never import `mission_finalize` at module scope. Routing uses the lazy in-function seam-bridge idiom already used by `tasks_shared`. | Technical | High | Open |

### Key Entities

- **Finalize module family**: the command module plus its seven phase modules. Together they are the unit that structural pins scan.
- **Patch seam**: a name that tests patch on `mission_finalize`. It must stay a module attribute and be resolved through that module at call time.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A maintainer can find any single finalize phase in a module of at most about 1,300 lines, down from one 5,678-line file. — [build] · no-op passable: no
- **SC-002**: 0 behavioural regressions: the finalize test corpus (more than 5,000 tests) has no new failures relative to the base branch. — [ratchet] · no-op passable: yes — paired with the FR-003 interception tests on the same seams
- **SC-003**: Every relocated function guarded by a structural pin is still guarded: 0 pins lose a target. — [build] · no-op passable: no

## Assumptions

- Tests that read `mission_finalize.py` as text, or that patch a phase-module-internal name, are updated to read the module family or patch the owning module. That is a re-pointing, not an assertion change.
- `tests/integration/test_merge_lane_planning_data_loss.py::test_bare_slug_coord_mission_consolidates_onto_a_protected_target` is red on the base branch and is unrelated.

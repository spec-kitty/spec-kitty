# Mission Specification: Rename FEATURE_CONTEXT_UNRESOLVED host error code to Mission vocabulary

**Mission Branch**: `tech-debt/5976-mission-context-unresolved`
**Created**: 2026-10-11
**Status**: Draft
**Input**: Issue #5976 — "Rename the `FEATURE_CONTEXT_UNRESOLVED` machine error code to Mission vocabulary"

This is a **bulk edit** (`change_mode: bulk_edit`). The term rename and per-category
rules are captured in [`occurrence_map.yaml`](./occurrence_map.yaml): the mission renames
the exact string **`FEATURE_CONTEXT_UNRESOLVED` → `MISSION_CONTEXT_UNRESOLVED`** across every
host emitter, consumer, and test, plus the two live docs that name it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Host error code uses Mission vocabulary (Priority: P1)

An operator reading a host CLI `--json` failure (e.g. `spec-kitty agent mission
check-prerequisites --json`, `context resolve`, the owned-checkout refusals) sees the
error code `MISSION_CONTEXT_UNRESOLVED`, not the Terminology-Canon-forbidden
`FEATURE_CONTEXT_UNRESOLVED`, for the "mission handle/slug could not be resolved" condition.

**Why this priority**: The Terminology Canon prohibits `feature*` for the Mission domain
object; the machine code is the last host surface still carrying it (#5885/#5963 left it as
a tracked follow-up).

**Independent Test**: Every host emitter's `--json` payload and every test asserting the
code string uses `MISSION_CONTEXT_UNRESOLVED`; no live-code occurrence of
`FEATURE_CONTEXT_UNRESOLVED` survives.

**Acceptance Scenarios**:

1. **Given** a host command that cannot resolve a mission handle, **When** it emits its
   `--json` error payload, **Then** `error_code == "MISSION_CONTEXT_UNRESOLVED"`.
2. **Given** a `grep FEATURE_CONTEXT_UNRESOLVED` over live code (src, tests, live docs),
   **When** the mission is complete, **Then** it matches nothing outside immutable historical
   artifacts (ADRs, archive, prior `kitty-specs/` missions, the released CHANGELOG entry).

### User Story 2 — Public orchestrator-api contract is preserved (Priority: P1)

A consumer of the orchestrator-api (`check-prerequisites`, and every verb that delegates
through it) continues to receive the public error code `MISSION_NOT_FOUND` for this
condition — unchanged — and the new host token never leaks onto that public surface.

**Why this priority**: Operator-delegated triage ruling (#5976, 2026-10-10): "preserve
orchestrator-api public `MISSION_NOT_FOUND` normalization and its existing contract/tests;
do not let the new host token leak through as an accidental public API change." A breaking
public rename is out of scope.

**Independent Test**: The `_classify_check_prerequisites_error` translation maps the **new**
host code to the **unchanged** public `MISSION_NOT_FOUND`; the recursive sanitizer scrubs the
new host token so it never appears in a serialized orchestrator-api envelope.

**Acceptance Scenarios**:

1. **Given** a delegate payload carrying `error_code: "MISSION_CONTEXT_UNRESOLVED"`, **When**
   `check-prerequisites` classifies it, **Then** the envelope's top-level and nested
   `error_code` are both `MISSION_NOT_FOUND` and the serialized envelope contains neither
   `FEATURE_CONTEXT_UNRESOLVED` nor `MISSION_CONTEXT_UNRESOLVED`.

### Edge Cases

- A delegate payload that still carries the *old* `FEATURE_CONTEXT_UNRESOLVED` (e.g. a stale
  installed CLI) is out of scope — the host and its delegate are versioned together; the
  translation keys on the new token only.
- Immutable historical artifacts (ADRs, archive, prior missions, the released CHANGELOG
  entry) keep the old token verbatim — renaming them would falsify a historical record.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Host wire code renamed at every emitter | As an operator, I want host `--json` failures to report `MISSION_CONTEXT_UNRESOLVED` so the Terminology Canon holds on the machine surface. | High | Open | [build] | no — a host emitter still emitting the old token fails the grep guard |
| FR-002 | Host constants renamed at every definition/consumer | As a maintainer, I want the Python constants and their imports renamed so there is one consistent token per layer. | High | Open | [build] | no |
| FR-003 | Public `MISSION_NOT_FOUND` normalization preserved | As an orchestrator-api consumer, I want `MISSION_NOT_FOUND` unchanged and no host-token leak so my integration keeps working. | High | Open | [build] | no — paired with the leak-scrub assertion on the same fixture |
| FR-004 | Tests assert the new code; old string gone from live code | As a maintainer, I want tests to assert `MISSION_CONTEXT_UNRESOLVED` so the rename is enforced. | High | Open | [build] | no |
| FR-005 | Live docs + CHANGELOG compat note updated | As a reader, I want the orchestrator-api docs/skill ref to name the new host code and a CHANGELOG note to record the host error-code change. | Medium | Open | [build] | yes |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No public contract break | The public orchestrator-api error-code set is byte-identical before/after (MISSION_NOT_FOUND preserved); no version bump required. | Compatibility | High | Open |
| NFR-002 | Single token per layer | Each of the three cross-layer definition sites holds exactly `MISSION_CONTEXT_UNRESOLVED`; no divergent value. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Immutable history | Historical ADRs, archive, prior `kitty-specs/` missions, and the released CHANGELOG entry keep the old token verbatim. | Governance | High | Open |
| C-002 | No scope creep | The module `mission_feature_resolution.py` keeps its filename; only the error-code string/constants are in scope. | Technical | High | Open |
| C-003 | Cross-layer defs stay in place | Layer rules forbid `mission_runtime` importing from `specify_cli`, so the three definition sites are renamed in place, not consolidated. | Technical | Medium | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `grep -rl FEATURE_CONTEXT_UNRESOLVED src/ tests/ docs/api docs/changelog` (excluding the released historical CHANGELOG line and `docs/adr`/`docs/archive`) returns no live emitters/consumers — [build] · no-op passable: no
- **SC-002**: The orchestrator-api contract-preservation test asserts `MISSION_NOT_FOUND` output for a `MISSION_CONTEXT_UNRESOLVED` host input and no token leak — [build] · no-op passable: no
- **SC-003**: `make test-fast` plus the targeted blast-radius suites are green — [build] · no-op passable: no

## Work Package Decomposition

- **WP01 — Red-first guards**: flip the orchestrator-api contract-preservation test
  (`test_check_prerequisites_record_analysis.py`) and representative emitter tests to the new
  code; confirm red against the current tree.
- **WP02 — mission_runtime layer**: `resolution.py` (`_FEATURE_CONTEXT_UNRESOLVED_CODE` + value,
  4 raise sites) and `write_target_degrade.py` (import + use).
- **WP03 — specify_cli core + CLI emitters/consumers**: `core/owned_mission.py` (public +
  private constants), `cli/commands/_owned_checkout.py`, and the hard-coded literals in
  `mission_check_prerequisites.py`, `context.py`, `mission_feature_resolution.py`,
  `mission_record_analysis.py`, `mission_finalize.py`.
- **WP04 — orchestrator_api + runtime bridge (contract seam)**: retarget the
  `design_phase.py` translation source to the new host token while keeping the public
  `MISSION_NOT_FOUND` output and the recursive leak-scrub; `decision_verbs.py`;
  `runtime/next/runtime_bridge_query.py`.
- **WP05 — tests sweep**: the remaining ~29 test files; update the
  `test_no_for_feature_operator_text.py` docstring note (the scanner keys on prose, not the
  token, so no new violation).
- **WP06 — docs + changelog**: `docs/api/orchestrator-api.md`, the shipped orchestrator-api
  skill contract ref, and a `[Unreleased]` CHANGELOG host error-code compatibility note.

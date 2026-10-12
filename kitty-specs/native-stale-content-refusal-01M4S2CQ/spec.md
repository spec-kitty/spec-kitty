# Mission Specification: Native stale-content refusal enforcement

**Mission Branch**: `issue-5879-native-stale-content-refusal`  
**Created**: 2026-10-12  
**Status**: Draft  
**Input**: Issue #5879 — "Enforce the API-authored stale-content refusal on native completion (`spec-kitty next`, agent lifecycle)". Follow-up residual from PR #5851 / requirement #5846, recorded in ADR `2026-10-07-2`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Native `next` completion enforces the API-authoring contract (Priority: P1)

An external orchestrator authors a Mission's planning artifacts through the governed
orchestrator-api (so the Mission carries the API-authoring marker). A user — or an agent —
then completes a planning stage **natively** with `spec-kitty next --result success`. Today the
stale/unfinished-content refusal (`validate_stage`) runs only on the orchestrator-api `next`
path, so the native command silently completes the stage even when the content is stale, dirty,
unfinished, or has unresolved decisions — letting anyone bypass the API-authoring contract by
switching commands.

**Why this priority**: This is the core GA gap the operator flagged — both completion surfaces
must enforce the same marker-gated check before 4.0.0 GA, or the contract is defeatable.

**Independent Test**: Build an API-authored Mission (marker + receipts present), leave a stage's
content stale/unfinished, drive the **native** CLI `spec-kitty next --result success`, and assert
it refuses with the same typed reason the orchestrator-api path already returns
(`DESIGN_PREREQUISITES_FAILED` / `DESIGN_PARENT_STALE` / `DESIGN_CONTEXT_STALE` / `DESIGN_FINALIZED`).
On `origin/main` the native command completes (RED); after the fix it refuses (GREEN). A legacy
(no-marker) Mission is unaffected (byte-identical native behaviour).

**Acceptance Scenarios**:

1. **Given** an API-authored Mission whose issued stage has stale/unfinished content, **When** a user runs native `spec-kitty next --result success`, **Then** completion is refused with the typed `DESIGN_*` reason and the stage does not advance.
2. **Given** a non-API-authored (no-marker) Mission, **When** a user runs native `spec-kitty next --result success`, **Then** behaviour is byte-identical to today (no marker gate, no new refusal).
3. **Given** an API-authored Mission driven through the orchestrator-api `next` verb, **When** completion is requested, **Then** the existing refusal behaviour and error envelope are unchanged (single canonical authority, no double-enforcement).

---

### User Story 2 - Native `agent` finalize-tasks enforces the contract and cooperates on the lock (Priority: P2)

The same API-authoring contract must hold for the native agent-lifecycle completion commands
(`spec-kitty agent mission finalize-tasks` and `spec-kitty agent tasks finalize-tasks`), which
finalize planning by writing status directly. Today they take no authoring lock and never run
`validate_stage`, so (a) they can finalize an API-authored Mission with stale parents, and
(b) because they do not take the cooperative `authoring_lock`, a native finalize can race the
`require_unfinalized` guard used by the API authoring path (ADR `2026-10-07-2` residual #2).

**Why this priority**: Closes the second native completion surface named in the issue's "Ask",
and makes the native finalize cooperatively take `authoring_lock`, closing the writer-takes-no-lock
half of the documented race.

**Independent Test**: Build an API-authored Mission with stale `tasks`-stage parents; run the
native `agent … finalize-tasks`; assert it refuses with the typed `DESIGN_*` reason (RED on
`origin/main`, GREEN after). Assert the native finalize now acquires `authoring_lock`.

**Acceptance Scenarios**:

1. **Given** an API-authored Mission with stale/unfinished `tasks`-stage content, **When** native `agent … finalize-tasks` runs, **Then** it refuses with the typed `DESIGN_*` reason and does not finalize.
2. **Given** an API-authored Mission with valid, committed, current content, **When** native `agent … finalize-tasks` runs, **Then** it finalizes successfully and (success-gated) re-stamps receipts exactly as the orchestrator-api `tasks` verb does.
3. **Given** a non-API-authored Mission, **When** native `agent … finalize-tasks` runs, **Then** behaviour is byte-identical to today.

### Edge Cases

- A pending design input may name the upcoming stage before its prompt is issued; answering that input is issuance and must not require completed stage artifacts (preserve the existing `issued_step_id` authority — never a caller-supplied stage).
- A refusal raised inside native `next` must surface as the structured JSON error envelope (single-JSON-document stdout contract), not as stray stdout text, and must map to the same exit/`reason` the orchestrator-api path classifies as `RUNTIME_NEXT_FAILED`.
- `authoring_lock` is reentrant: nested acquisition (api verb → native `next_step`) must not deadlock the engine's own run-cursor lock.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Native `next --result success` runs the marker-gated `validate_stage` | As a maintainer, I want native `next` completion to refuse stale/unfinished content for an API-authored Mission so that the API-authoring contract cannot be bypassed by switching commands. | High | Open | [build] | no — paired with the valid-content positive control on the same fixture |
| FR-002 | Gate fires only when the API-authoring marker is present | As a user of a non-API-authored Mission, I want native `next` to behave exactly as before so that legacy/manual Missions are not newly constrained. | High | Open | [build] | no — paired with the marker-present refusal on the same fixture |
| FR-003 | Orchestrator-api `next` keeps identical behaviour via the shared seam (no double-enforcement) | As a maintainer, I want one canonical enforcement authority so that the api and native paths cannot drift. | High | Open | [folded] | no — pinned by the unchanged orchestrator-api journey assertions |
| FR-004 | Native `agent … finalize-tasks` runs the marker-gated `validate_stage("tasks")` under `authoring_lock` | As a maintainer, I want native finalize to refuse stale content for an API-authored Mission so that the agent-lifecycle surface enforces the same contract. | High | Open | [build] | no — paired with the valid-content finalize positive control |
| FR-005 | Native finalize cooperatively acquires `authoring_lock` | As a maintainer, I want native finalize to take the cooperative lock so that the writer-takes-no-lock half of the ADR `2026-10-07-2` race is closed. | Medium | Open | [build] | no — asserted by a lock-acquisition probe |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Read-only validation | `validate_stage` and the marker gate perform no writes on the completion path (completion state remains owned by the native authority). | Correctness | High | Open |
| NFR-002 | Typed failure fidelity | Every native refusal surfaces a typed `DESIGN_*` reason; no raw traceback, no stray stdout on the JSON path. | Reliability | High | Open |
| NFR-003 | mypy --strict + ruff clean | New/changed code passes `mypy --strict`, `ruff check`, and `ruff format --check` with zero issues and no new suppressions. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Layer boundary | The enforcement must live in `specify_cli.cli.commands` (top layer); it may NOT be placed in `src/runtime/` — `tests/architectural/test_layer_rules.py` forbids `runtime → specify_cli.design` / `specify_cli.cli`. (Reconciles the operator's "runtime-bridge composition-advance" hint with the enforced architecture.) | Technical | High | Open |
| C-002 | No api behaviour change | The orchestrator-api path's observable behaviour (refusals, error codes, envelope) must not change; removing its now-redundant local gate is a single-authority refactor, not a behaviour change. | Technical | High | Open |
| C-003 | Scope boundary | Do not widen beyond shared-seam enforcement for the two named native surfaces. The residual api-`plan`-read-under-lock and native `move-task` lock adoption are tracked follow-ups, not folded. | Technical | Medium | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An API-authored Mission with stale/unfinished content is refused on native `spec-kitty next --result success` with the same typed `DESIGN_*` reason as the orchestrator-api path — [build] · no-op passable: no
- **SC-002**: An API-authored Mission with stale `tasks` content is refused on native `agent … finalize-tasks` with a typed `DESIGN_*` reason, and native finalize acquires `authoring_lock` — [build] · no-op passable: no
- **SC-003**: Non-API-authored Missions and the orchestrator-api path show no observable behaviour change (byte-identical native behaviour; unchanged api journey assertions) — [folded] · no-op passable: no
- **SC-004**: The red-first native cases in `tests/specify_cli/orchestrator_api/test_planning_client_journey.py` are RED on `origin/main` and GREEN on the fix; `test_layer_rules.py` stays green — [build] · no-op passable: no

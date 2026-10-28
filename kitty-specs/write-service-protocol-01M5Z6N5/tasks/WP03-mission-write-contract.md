---
work_package_id: WP03
title: The mission-write contract module and refusal parity
dependencies:
- WP01
- WP02
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-009
- FR-010
- FR-011
- FR-012
- FR-013
- FR-014
- FR-018
- NFR-001
- NFR-004
- C-002
- C-003
- C-004
- C-007
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-6675-write-service-protocol
merge_target_branch: issue-6675-write-service-protocol
branch_strategy: Planning artifacts for this mission were generated on issue-6675-write-service-protocol. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6675-write-service-protocol unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
- T013
- T014
- T015
- T016
phase: Phase 2 - The contract
history:
- at: '2026-10-27T18:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: contracts/mission-write/
create_intent:
- contracts/mission-write/openapi.yaml
- contracts/mission-write/CHANGELOG.md
- tests/contract/test_mission_write_contract.py
- tests/contract/fixtures/mission_write_refusal_parity.yaml
execution_mode: code_change
model: ''
owned_files:
- contracts/mission-write/**
- contracts/tools/fixtures/example_check/required_examples.json
- tests/contract/test_mission_write_contract.py
- tests/contract/fixtures/mission_write_refusal_parity.yaml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – The mission-write contract module and refusal parity

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log and address every item before handing back.

## Objectives & Success Criteria

- `contracts/mission-write/` passes every contract check with the module counted (SC-001):
  `layout_check`, `structure_check`, `citation_check`, `provisional_check`, `example_check`,
  `enum_pin_check`, `event_mapping_check`, `leak_scan`, `codeowners_check`, `bundle.py` (twice,
  byte-identical, NFR-001), Gradle `validate_*`/`validateBundle_*`/`javaView_*`, `resolver_parity`,
  `client_smoke`, `lint_check` (vacuum), `breaking_check` (`NO_BASELINE_INITIAL_VERSION`),
  `release_check` dry run.
- Six operations exactly as `data-model.md` lists them (FR-002 to FR-006); the bearer scheme
  `writeToken` on every operation (FR-007); every refusal a `WriteRefusal` composing
  `_shared/schemas/Problem.yaml` (FR-009); codes and reasons as `oneOf` of `const` with a
  description each (vacuum `enum-case` forbids UPPER_SNAKE enums).
- The parity inventory names every code's CLI source or marks it protocol-only, and its test reads
  each cited file for the literal (FR-010 to FR-012, SC-002).
- Event rows reference the spec-kitty-events #92 envelope; nothing beyond `event_id` is defined
  (FR-013, C-003).
- Unruled behaviour carries `x-provisional` and is listed under `### Provisional` in
  `CHANGELOG.md` (FR-018): `statusCommit`, `replayed`, `EVENT_ID_CONFLICT`, `SERVICE_BUSY` with
  `Retry-After`, `REQUEST_TOO_LARGE`, `WRITE_LOCATION_UNVERIFIED`, the reason vocabulary, the
  `/shutdown` operation and the `draining` health status.
- Examples serialized by WP02's shapes validate against the bundle (SC-003).

## Context & Constraints

- Conventions: `contracts/README.md` (path file naming, relative `$ref`, `_index.yaml`, citations,
  `-SNAPSHOT`, closed responses). Follow `contracts/mission-status/` as the structural example.
- At least 5 path items (`DEFAULT_MIN_PATHS`); `_shared/` untouched; no `MissionLifecycleEvent`
  title; no property named like `worktreePath`, `featureDir`, `projectPath`.
- Leak scan: no host paths, e-mail addresses or token-shaped strings in examples; tokens never
  appear in examples (the bearer value is not part of any body).
- Citations: every property carries `x-source {path, symbol}` (a tracked file and a defined
  name) or `x-derived {rule, inputs}`. Cite the CLI source the field mirrors
  (`src/runtime/next/event_bridge.py` `WorkPackageTransition.rows`, `src/specify_cli/status/models.py`
  `StatusEvent.event_id`, `src/specify_cli/coordination/status_service.py` `EventLogWriteTarget`) or
  WP02's `src/specify_cli/status/write_service_protocol.py` symbols for protocol-only fields.
- ATDD-first: T010 before T011-T014.

## Branch Strategy

- **Strategy**: single_branch (set by finalize-tasks)
- **Planning base branch**: issue-6675-write-service-protocol
- **Merge target branch**: issue-6675-write-service-protocol

Implementation command: `spec-kitty agent action implement WP03 --agent claude --mission write-service-protocol-01M5Z6N5`

## Subtasks & Detailed Guidance

### Subtask T010 – Failing acceptance and parity tests

- `tests/contract/test_mission_write_contract.py`, using `contract_resolver` from
  `contracts/tools` (load it like the neighbouring tests do):
  - the resolved module has exactly the six paths and operationIds of the data model;
  - every operation's effective `security` is `[{writeToken: []}]` and the scheme is HTTP bearer;
  - every operation except `handshake` requires the `Spec-Kitty-Write-Protocol` header;
  - every non-2xx response composes `Problem` and every success response schema is closed;
  - the code `oneOf` of `WriteRefusal` equals `WriteRefusalCode` (WP02) as a set, and each code's
    status rule in the schema equals `REFUSAL_STATUS`; the reason URNs equal
    `WriteRefusalReason` URNs;
  - parity: every code in `tests/contract/fixtures/mission_write_refusal_parity.yaml` is either
    `origin: cli` with `source` (a tracked file) whose text contains the code literal, or
    `origin: protocol` with no source; every reason names `source` and `source_text`, a fragment
    found verbatim in that file; inventory codes == contract codes == `WriteRefusalCode`;
  - self-mutation (non-vacuity, SO-5): a copy of the inventory with one code's source swapped for
    an unrelated tracked file fails the parity predicate.

### Subtask T011 – Root, paths, parameters, responses

- `openapi.yaml`: `openapi: 3.1.0`, `info` (title `Mission Write API`, `version: 1.0.0-SNAPSHOT`,
  summary, description naming ADR 2026-10-27-1), `servers: [{url: /api/v1}]`, tags (`Service`,
  `WorkPackages`), `components.securitySchemes.writeToken` (http, bearer, description: the token is
  read from the endpoint file; never logged), root `security: [{writeToken: []}]`, `paths` map.
- `paths/`: `handshake.yaml`, `health.yaml`, `missions_missionId_work-package-transitions.yaml`,
  `missions_missionId_work-package-transitions_batch.yaml`,
  `missions_missionId_inner-state-annotations.yaml`, `shutdown.yaml`.
- `parameters/`: `MissionId.yaml` (path), `WriteProtocolVersion.yaml` (header, integer ≥ 1,
  required). `responses/`: one per refusal family (`Refused400`, `Unauthorized401`,
  `Forbidden403`, `NotFound404`, `Conflict409`, `TooLarge413`, `Unprocessable422`,
  `WriteFailed500`, `Busy503` with `Retry-After`), each `application/problem+json` of
  `WriteRefusal`. `_index.yaml` in each directory.

### Subtask T012 – Schemas with citations

- Per `data-model.md`: `MissionId`, `WpId`, `EventRow` (open object, `required: [event_id]`, the
  #92 envelope reference), `WriteSurface`, `RequestContext`, `TransitionUnit`, `TransitionBatch`,
  `AnnotationRequest`, `DurabilityAck`, `BatchDurabilityAck`, `Handshake`, `Health`,
  `HealthStatus`, `ProtocolVersion`. Responses closed (`additionalProperties: false`), every
  property described and cited, `schemas/_index.yaml`.

### Subtask T013 – Refusal vocabulary and inventory

- `schemas/WriteRefusal.yaml`: `allOf` of `Problem`, one `if code const X then status const N`
  per code (as `DriftRefusal` does), and a branch narrowing `code` to `WriteRefusalCode` and
  `type` to `WriteRefusalReason`. `schemas/WriteRefusalCode.yaml` / `WriteRefusalReason.yaml`:
  `type: string`, `oneOf` of `{const, description}`; the reason file carries `x-provisional`.
- `tests/contract/fixtures/mission_write_refusal_parity.yaml`: `codes:` (code, status, origin,
  source) and `reasons:` (reason, code, source, source_text).

### Subtask T014 – Examples, manifest, changelog

- `examples/`: one per success shape and at least three refusals (a guard refusal with a reason
  URN, a placement refusal, `WRITE_TOKEN_INVALID`), each referenced from its schema's `examples`.
- `contracts/tools/fixtures/example_check/required_examples.json`: a `"mission-write"` list.
- `CHANGELOG.md`: `# Changelog`, `## 1.0.0-SNAPSHOT`, `### Added`, `### Changed`, `### Removed`,
  `### Provisional` naming every `x-provisional` element by name.

### Subtask T015 – Cross-validation

- In `test_mission_write_contract.py`, bundle the module with `contract_resolver.resolve`, then
  validate with `jsonschema` (Draft 2020-12): `TransitionUnit.to_wire()` from a realistic
  `WorkPackageTransition`, a `TransitionBatch`, an `AnnotationRequest` against their request
  schemas; and every example file against its schema. `from_wire` of every success example
  round-trips.

### Subtask T016 – Whole suite

- Run every tool (`quickstart.md`), then with a JDK 21 and the pinned Gradle the full
  `bundle.py`, `resolver_parity.py`, `client_smoke.py`. vacuum and oasdiff are CI-only (pinned
  binaries); install them with `install_tools.py` if the network allows, otherwise record that
  CI runs them.

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q tests/contract/test_mission_write_contract.py tests/contract/test_example_check.py tests/contract/test_leak_scan.py tests/contract/test_structure_check.py tests/contract/test_codeowners_check.py tests/contract/test_layout_check.py
```

## Risks & Mitigations

- Citation check rejects a property: cite the closest real CLI symbol, never invent one.
- `if/then` branches over 28 codes are long; keep the file readable with one comment line per
  family.

## Review Guidance

- Compare the code list with the WP02 enum and the inventory; check every `origin: cli` literal by
  hand on two samples; confirm the provisional list matches the changelog.

## Progress & Status

Recorded through the status event log.

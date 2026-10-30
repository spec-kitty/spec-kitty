# Mission Specification: charter packs refusal code convergence

**Mission Branch**: `kitty/mission-charter-packs-refusal-code-convergence-01M66FC9`
**Created**: 2026-10-30
**Status**: Draft
**Input**: Issue spec-kitty/spec-kitty#6772 — "charter activate and deactivate report a malformed charter_packs config with different codes". Guidance: converge the two verbs on the one honest code, cover both verbs including `--json`, keep the "declared pack not fetched" refusal distinct.

## Context

With a malformed `charter_packs` value in `.kittify/config.yaml` (e.g. `charter_packs: [1, 2]`), the
two positional activation verbs refuse with different codes for the same broken file:

- `charter deactivate KIND ID [--json]` → `ACTIVE_CHARTER_CONFIG_INVALID` (the strict required-floor
  read wraps the registry failure in `ActiveCharterConfigError`, via
  `charter.activation.org_pack_discovery._strict_error`).
- `charter activate KIND ID [--json]` → `ACTIVATION_FAILED` (`charter.offering.drg.org_pack_config.require_declared_org_roots`
  raises a plain `ValueError` for the unreadable registry, and the activate path maps generic
  `ValueError`s to `ACTIVATION_FAILED`).

Both exit 1 and write nothing, but tooling branching on `error.code` sees two causes for one broken
file. The asymmetry is pinned by
`tests/specify_cli/cli/commands/charter/test_activation_json_6525.py::test_a_malformed_charter_packs_config_is_refused`
and documented as known in `docs/api/charter-commands.md` ("Error envelope and codes"), which this
mission removes.

The same `ValueError` from `require_declared_org_roots` also covers "a declared pack was never
fetched" (root is not a directory). That case must stay distinct: `activate` reports it as
`ACTIVATION_FAILED` naming the `spec-kitty charter fetch` remedy (#4984, #5779/#6006 fail-closed
posture), and no convergence of that refusal is in scope.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One code for one broken config (Priority: P1)

As an operator whose `.kittify/config.yaml` has a malformed `charter_packs` block, I want both
`charter activate` and `charter deactivate` to refuse with the same error code
(`ACTIVE_CHARTER_CONFIG_INVALID`) in both text and `--json` form, so that my tooling branches on the
code and always lands on the same remediation path (fix the config) regardless of which verb it ran.

**Why this priority**: The whole defect is the divergence; converging the code is the fix.

**Independent Test**: Run both verbs (text and `--json`) against a project whose
`charter_packs: [1, 2]`; all four refusals carry `ACTIVE_CHARTER_CONFIG_INVALID`, exit 1, and change
nothing under `.kittify/`.

**Acceptance Scenarios**:

1. **Given** a migrated activation project with `charter_packs: [1, 2]`, **When** I run
   `charter activate directive <id>`, **Then** it exits 1 with `Error (ACTIVE_CHARTER_CONFIG_INVALID)`
   naming the org pack registry, and `.kittify/` is byte-identical.
2. **Given** the same project, **When** I run `charter deactivate directive <id>`, **Then** it exits 1
   with `Error (ACTIVE_CHARTER_CONFIG_INVALID)` naming the org pack registry, and `.kittify/` is
   byte-identical.
3. **Given** the same project, **When** I run either verb with `--json`, **Then** stdout is exactly
   one JSON document `{"ok": false, "error": {"code": "ACTIVE_CHARTER_CONFIG_INVALID", "message": ...}}`
   with the same exit code as the text form.

### User Story 2 - The not-fetched refusal stays honest (Priority: P2)

As an operator who declared an org pack but never fetched it, I want `charter activate` to keep
refusing with `ACTIVATION_FAILED` naming the pack and the `spec-kitty charter fetch` remedy, so the
two failure modes (broken config vs. unfetched pack) stay distinguishable by code.

**Why this priority**: The convergence must not swallow the deliberately distinct fail-closed
posture of #4984.

**Independent Test**: Declare a pack whose root is absent on disk; `charter activate` refuses with
`ACTIVATION_FAILED` and the fetch remedy; the registry-unreadable case from Story 1 refuses with
`ACTIVE_CHARTER_CONFIG_INVALID`.

**Acceptance Scenarios**:

1. **Given** a project whose declared org pack root is not a directory, **When** I run
   `charter activate directive <id>`, **Then** it exits 1 with `ACTIVATION_FAILED` and a message
   naming the pack and `spec-kitty charter fetch`.
2. **Given** the typed-registry-error change, **When** any strict reader of the org-pack chain
   (effective set, preset application, requirement-kinds loader) reads the malformed registry,
   **Then** its existing refusal behaviour is unchanged (the new error type is still caught where
   `ValueError` was).

### Edge Cases

- `.kittify/config.yaml` absent or without any `charter_packs` key: zero declared packs; both verbs
  proceed as today (no refusal introduced by this change).
- A malformed registry under `--json`: exactly one JSON document on stdout, exit code equal to the
  text form (the existing `_assert_refusal` contract).
- `charter status` and the other charter commands that read the registry through their own paths:
  unchanged by this mission (their codes were already typed).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | activate converges on ACTIVE_CHARTER_CONFIG_INVALID | As an operator, I want `charter activate` to refuse a malformed org-pack registry with `ACTIVE_CHARTER_CONFIG_INVALID` (text and `--json`) so my tooling sees the config cause. | High | Open | [build] | no — paired with FR-002 on the same fixture |
| FR-002 | deactivate keeps the converged code | As an operator, I want `charter deactivate` to keep refusing the same malformed registry with `ACTIVE_CHARTER_CONFIG_INVALID` so both verbs agree. | High | Open | [ratchet] | no — paired with FR-001 on the same fixture |
| FR-003 | not-fetched stays distinct | As an operator, I want a declared-but-unfetched org pack to keep refusing `charter activate` with `ACTIVATION_FAILED` and the fetch remedy so the two causes stay distinguishable. | High | Open | [ratchet] | no — same-fixture positive control for FR-001/FR-002 |
| FR-004 | strict chain readers keep their contracts | As a developer, I want every strict caller of the org-pack chain to keep its documented refusal behaviour so the typed error does not change unrelated surfaces. | Medium | Open | [ratchet] | no — exercised by the existing suites of each caller |
| FR-005 | the asymmetry note is removed from the docs | As an operator reading the CLI reference, I want the `charter-commands.md` error-code table to describe the converged behaviour so the docs no longer pin a known asymmetry. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Refusal writes nothing | Both verbs' refusals for the malformed registry leave every file under `.kittify/` byte-identical (the existing refusal contract). | Reliability | High | Open |
| NFR-002 | No message-text branching | The CLI must distinguish the registry-unreadable refusal from the not-fetched refusal by exception type, never by matching message text. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Import graph stays acyclic | `charter.offering` must not import `charter.activation` at module load; the typed error crosses that seam only lazily, as `org_pack_discovery._strict_error` already does. | Technical | High | Open |
| C-002 | Local codes only | The refusal codes stay local UPPER_SNAKE codes of the CLI (contracts/cli-json.md), never spec-kitty-charter contract codes. | Technical | High | Open |
| C-003 | Smallest viable diff | The fix lands at the one shared seam (`require_declared_org_roots` / `resolve_pack_chain(strict=True)`), not as per-verb message matching in the CLI. | Technical | Medium | Open |

### Key Entities

- **Org pack registry**: the `charter_packs` block of `.kittify/config.yaml`, read strictly or
  leniently by `load_pack_registry`.
- **Typed registry error**: the new exception raised when the strict registry read fails; it carries
  the `ACTIVE_CHARTER_CONFIG_INVALID` code and remains catchable as `ValueError` by the existing
  strict readers.
- **Refusal**: the CLI's `CodedRefusal(code, message)` rendered as `Error (<CODE>): ...` or the
  `--json` error envelope, exit 1.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With `charter_packs: [1, 2]`, all four invocations (activate/deactivate × text/`--json`)
  refuse with `ACTIVE_CHARTER_CONFIG_INVALID`, exit 1, and leave `.kittify/` byte-identical — [build] · no-op passable: no
- **SC-002**: A declared-but-unfetched org pack still refuses `charter activate` with
  `ACTIVATION_FAILED` naming the pack and the fetch remedy — [ratchet] · no-op passable: no
- **SC-003**: The strict chain readers (effective set, preset application, requirement-kinds loader)
  keep their documented refusal behaviour; their existing suites pass unchanged — [ratchet] · no-op passable: no
- **SC-004**: `docs/api/charter-commands.md` no longer documents the activate/deactivate asymmetry,
  and the code table's `ACTIVE_CHARTER_CONFIG_INVALID` row covers the malformed `charter_packs`
  registry for both verbs — [build] · no-op passable: no

# Mission Specification: Write service API prefix (`/api/v1`)

**Mission Branch**: `issue-6910-write-service-api-v1-prefix`
**Created**: 2026-11-01
**Status**: Draft
**Input**: GitHub issue #6910 — "Service launcher client: call the write service under the pinned version".
Guidance recorded from the operator brief: small, tightly-scoped fix; red-first; do not
touch the EventBridge cut-over (#6195), the write shapes or the refusal vocabulary;
land before #6195, as the issue allows.

## Problem

`contracts/mission-write/openapi.yaml` declares `servers: [{url: /api/v1}]`, so every
operation in that contract is served under `/api/v1` (`/api/v1/handshake`,
`/api/v1/health`, `/api/v1/shutdown`, and the two work-package write paths). The
launcher's loopback client (`src/specify_cli/services/client.py`) sends the bare path
strings `/handshake`, `/health` and `/shutdown`. The service that `command-cli` exposes
answers on the contract's prefixed paths, so the launcher's ready check, health check
and stop call would 404 against the real binary. The operator ruled on 2026-10-31
(spec-kitty-events#156) that the contract wins. There is no test today that ties the
client's path strings to the contract, which is why the drift survived.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The launcher reaches a contract-conforming service (Priority: P1)

An operator runs a CLI command that needs the resident write service. The launcher
starts or reuses the service, proves it is ready, and later stops it. Every request it
sends lands on the path the write-service contract declares.

**Why this priority**: The launcher is the only caller of this client today; if its
paths are wrong, the read/write service flow cannot reach the real service at all.

**Independent Test**: Start the test stand-in service (which now serves only the
contract's prefixed routes) and drive `handshake`, `health` and `shutdown` through
`ServiceClient`; all three succeed and the process exits.

**Acceptance Scenarios**:

1. **Given** a running service that serves only `/api/v1/*`, **When** `ServiceClient.handshake()` is called, **Then** it answers with the endpoint's instance id and repository id.
2. **Given** the same service, **When** `ServiceClient.health()` is called, **Then** it reads `ready` for that instance.
3. **Given** the same service and a negotiated protocol major, **When** `ServiceClient.shutdown()` is called, **Then** the service drains and the process exits 0.

### User Story 2 - The prefix cannot drift again (Priority: P1)

A maintainer changes a client path or the contract. A contract test fails when a path
the client sends is not the contract's server prefix plus a path the contract declares,
so the next drift is caught in CI instead of in a live service.

**Why this priority**: The defect is exactly a second source of truth for the path
strings; a fix without the pin would regress the same way.

**Independent Test**: Run `tests/contract/test_mission_write_contract.py` with the
resolved contract tree; the path-pinning test enumerates the client's paths and the
contract's paths and fails on any mismatch, and a mutated path proves the pin bites.

**Acceptance Scenarios**:

1. **Given** the resolved contract, **When** the path-pinning test runs, **Then** every path the client can send is `<server url>/<declared path>` and the server url equals the client's prefix constant.
2. **Given** a client path edited to a bare path, **When** the pinning helper runs on it, **Then** it reports the path as un-prefixed.

### Edge Cases

- A service that answers the bare (unprefixed) path with 404: the client reports `ServiceUnreachable` naming the operation and the status, never a silent success — this is the pre-fix behaviour against the real service and the red-first observation.
- A path constant with a trailing slash or a doubled prefix (`/api/v1/api/v1/...`) must not pass the pin: the check compares the exact suffix against the contract's declared paths.
- The `missions/{missionId}/...` write paths are not sent by this client yet (#6195); the prefix constant is the single source they will be built from, and the pin covers every path the contract declares so binding them later cannot escape it.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Prefixed client paths | As an operator, I want the launcher client to call `/api/v1/handshake`, `/api/v1/health` and `/api/v1/shutdown` so that it reaches the service the contract describes. | High | Open | [build] | no — the stand-in service answers 404 on bare paths, so a no-op fails |
| FR-002 | One prefix constant | As a maintainer, I want the contract's server prefix defined once in the client's typed contract view and every operation path derived from it so that a future operation cannot be added under a different prefix. | High | Open | [build] | no — a duplicated literal would pass only by coincidence |
| FR-003 | Contract path pin | As a maintainer, I want a contract test that compares every client path against the resolved contract's `servers` url and declared paths so that path drift fails CI. | High | Open | [ratchet] | no — the same-fixture positive control asserts the real paths pass and a mutated bare path fails |
| FR-004 | Stand-in service matches the contract | As a test author, I want the test stand-in write service to serve only the contract's prefixed routes so that the red test exercises the real mismatch instead of shadowing it. | Medium | Open | [build] | no — the stand-in 404s on bare paths, so the old client fails |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No new warm-path cost | The change adds no import and no I/O to the client's warm path; paths stay module-level string constants. | Performance | Medium | Open |
| NFR-002 | No secret in messages | Failure messages keep naming the operation by its prefixed path and never the bearer token (existing invariant, re-asserted for the new path strings). | Security | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Contract wins | `contracts/mission-write/openapi.yaml` (`servers: /api/v1`) is authoritative; the client conforms to it, never the reverse. | Technical | High | Open |
| C-002 | Scope ceiling | No change to request/response shapes, refusal vocabulary, endpoint file format, launcher behaviour or the #6195 EventBridge cut-over. | Technical | High | Open |

### Key Entities

- **Write-service path**: an operation path the client sends, always `API_PREFIX` plus a path declared by the contract.
- **Contract server url**: the `/api/v1` prefix declared in the contract's `servers` entry, the authority for the prefix.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All three client operations succeed against a stand-in service that serves only the contract's prefixed routes (3/3 calls, existing tests pass). — [build] · no-op passable: no
- **SC-002**: A contract test enumerates 100% of the client's sent paths and fails if any is not `<contract server url>/<declared path>`. — [ratchet] · no-op passable: no
- **SC-003**: Zero bare `/handshake`, `/health` or `/shutdown` path literals remain in `src/specify_cli/services/`. — [ratchet] · no-op passable: no

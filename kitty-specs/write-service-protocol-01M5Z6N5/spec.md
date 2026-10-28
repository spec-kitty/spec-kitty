# Mission Specification: Mission Write API: CLI to write-service protocol

**Mission Branch**: `issue-6675-write-service-protocol`
**Created**: 2026-10-27
**Status**: Draft
**Input**: User description: "Mission Write API: CLI to write-service protocol contract (#6675, epic #6117, ADR 2026-10-22-1). Contract-first, no service implementation."

## Intent Summary (confirmed 2026-10-27)

The CLI's EventBridge client and the future Java write service need one agreed, machine-checked
boundary before either is built. This Mission delivers that boundary as a contract: the
operations, their request and response shapes, the refusal vocabulary, the token handshake and
version negotiation. It writes no events and changes no CLI behaviour.

- **Primary actor**: the author of the CLI's write-service client (EventBridge adapter) and the
  author of the Java write service, each building against the contract independently.
- **Trigger**: a work package transition, a batch of transitions, or a standalone inner-state
  annotation that the CLI must persist through the service.
- **Outcome**: a validated contract module, a recorded decision, and typed client-side shapes,
  all checked by the repository's existing contract gates.
- **Rule that must always hold**: the service is authoritative. It owns the lane state machine,
  the guards and dependency gating; anything the CLI checks first is advisory.

Operator rulings (2026-10-25, on #6675; 2026-10-27, in this Mission's Decision Moments):
loopback HTTP on `127.0.0.1` with a random port; port and a random bearer token in a file in the
git common dir (one writer per clone); service-authoritative validation with refusal codes that
match today's CLI codes; one `O_APPEND` write of a full JSON line, `fsync`ed before the ack, with
a batched `fsync` for multi-event operations; Windows semantics documented under the lock; the
refusal `code` reuses existing CLI codes verbatim and guard reasons are minted as provisional
URNs; the bearer scheme is declared natively, which needs a narrow amendment of the contract
layout check; protocol questions the operator has not ruled carry provisional defaults; the
client side ships typed shapes and a single binder with no transport.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Build the client against a validated contract (Priority: P1)

The author of the CLI's write-service client reads one contract module and learns every operation,
request body, success body and refusal the service can return, and generates a client from it.

**Why this priority**: without a contract, the client and the service drift; every later step of
epic #6117 (#6193, #6194, #6195, #6676) depends on this boundary.

**Independent Test**: the repository's contract checks (layout, structure, citations, examples,
lint, bundle, generator validation, client generation) pass for the new module, and a malformed
variant of it is refused.

**Acceptance Scenarios**:

1. **Given** the new module, **When** the contract checks run over the contracts tree, **Then**
   every check passes and the module is counted.
2. **Given** a work package transition with its annotations, **When** the author looks up the
   transition operation, **Then** the request carries the rows in order, the request context and
   the write location, and the success body states that the unit was durably appended.
3. **Given** a batch of transitions, **When** the author looks up the batch operation, **Then** the
   contract states that the batch lands whole or not at all, with one `fsync`.

### User Story 2 - Branch on a refusal the same way the CLI does today (Priority: P1)

A client receives a refusal and branches on a stable code that is the same string the CLI raises
today, so moving the write into the service changes no exit code or error code a user sees.

**Why this priority**: parity of refusal codes is the operator's binding condition for moving
validation into the service.

**Independent Test**: an inventory names, for every refusal code in the contract, either the CLI
source that raises that exact string today or that it is protocol-only; a test fails if a reused
code string is missing from its cited source or if the contract and the inventory disagree.

**Acceptance Scenarios**:

1. **Given** a transition the lane state machine forbids, **When** the service refuses it,
   **Then** the body is the shared problem shape with code `TRANSITION_REJECTED` and a reason URN
   naming the guard (for example the illegal-edge reason).
2. **Given** a destination that is a protected branch, **When** the service refuses it, **Then**
   the code is `PROTECTED_BRANCH_REFUSED`, the string the CLI uses today.
3. **Given** a code the contract mints that has no CLI counterpart (token invalid, protocol
   version unsupported, service busy, request too large), **When** the inventory is read, **Then**
   it is marked protocol-only.

### User Story 3 - Find, trust and negotiate with the running service (Priority: P2)

The client finds the service of its clone through a file in the git common dir, proves it holds
the token, checks the service's identity and agrees a protocol version before it sends a write.

**Why this priority**: a stale file, a recycled port or a version skew must fail closed rather
than send a write to the wrong process.

**Independent Test**: the endpoint-file reader refuses a file with broader permissions, a
malformed file and a non-loopback host, and accepts a well-formed one; the handshake operation
returns the supported versions and the instance identity the file names.

**Acceptance Scenarios**:

1. **Given** an endpoint file readable by other users, **When** the client reads it, **Then** it
   refuses with a named error and does not use the token.
2. **Given** a client that asks for a protocol version the service does not support, **When** it
   calls any operation, **Then** the service refuses with `PROTOCOL_VERSION_UNSUPPORTED` and the
   list of versions it supports.
3. **Given** a request without the bearer token, or with a wrong one, **When** it reaches the
   service, **Then** it is refused with `WRITE_TOKEN_INVALID` and no detail that echoes the token.

### User Story 4 - Know which questions are still open (Priority: P3)

A maintainer reading the contract sees which protocol behaviours are proposals awaiting an
operator ruling (idempotent retry, backpressure, token rotation, MCP mode, shutdown, size cap).

**Independent Test**: each such element carries a provisional marker naming the open decision,
and each is listed in the module's changelog and the decision record's open questions.

**Acceptance Scenarios**:

1. **Given** the shutdown operation, **When** a maintainer reads it, **Then** it is marked
   provisional and the open decision is named.

### Edge Cases

- A retry of a unit whose ack was lost: the contract states the proposed idempotency rule (same
  event ids and identical rows answer as already persisted; same ids with different rows refuse).
- The service is busy serializing another write: the proposed answer is a busy refusal with a
  retry hint, never a silent queue without bound.
- An empty unit, or a batch with an empty unit: refused as a malformed request.
- An event row whose shape is owned elsewhere (spec-kitty-events #92): the contract references
  that envelope and never redefines it.
- Windows: no POSIX modes; the endpoint file's owner-only access is stated as an ACL rule, and the
  lock semantics are referenced from the lock work (#6193).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Contract module exists and passes every contract gate | As a client author, I want a `mission-write` contract module that the existing contract checks validate so that I can build against it. | High | Open | [build] | no — the checks count modules, and the module's own negative variants must be refused |
| FR-002 | Work package transition operation | As a client author, I want one operation that persists one work package transition unit (the transition, then its annotations, in order) with its request context so that the port's unit maps to one request. | High | Open | [build] | no |
| FR-003 | Batch transition operation | As a client author, I want a batch operation that lands several units whole or not at all with one batched `fsync` so that multi-event operations have one durability point. | High | Open | [build] | no |
| FR-004 | Standalone inner-state annotation operation | As a client author, I want an operation for a standalone inner-state annotation so that the annotation door can move behind the port. | Medium | Open | [build] | no |
| FR-005 | Handshake with identity and version negotiation | As a client author, I want a handshake that returns the supported protocol versions, the service version and the instance identity so that I can detect a stale endpoint file or a version skew before writing. | High | Open | [build] | no |
| FR-006 | Health operation | As a launcher author (#6676), I want a health operation so that start and stale-daemon recovery can probe the service. | Medium | Open | [build] | no |
| FR-007 | Bearer token on every operation | As a security reviewer, I want every operation to require the bearer token, declared as a native security scheme, so that no write is accepted from a process that cannot read the endpoint file. | High | Open | [build] | no — a fixture with a scheme beside other root components must be refused |
| FR-008 | Contract layout allows only root security schemes | As a contract maintainer, I want the layout check to admit a root `components.securitySchemes` and refuse every other root component so that bundles stay a build product. | High | Open | [build] | no — paired negative fixture |
| FR-009 | Refusal envelope reuses the shared problem shape | As a client author, I want every refusal to be the shared problem shape with a `code` from a closed vocabulary and a status fixed by the code so that I branch on the code only. | High | Open | [build] | no |
| FR-010 | Refusal codes reuse today's CLI codes verbatim | As a CLI user, I want each refusal code the service returns for an existing CLI refusal to be the exact string the CLI raises today so that moving the write changes no code I see. | High | Open | [build] | no — the parity test reads the cited source |
| FR-011 | Guard reasons as provisional URNs | As a client author, I want each guard refusal to carry a reason URN from a closed, provisional vocabulary so that the Java core's reason is machine-checkable before the CLI adopts it. | Medium | Open | [build] | no |
| FR-012 | Parity inventory and check | As a reviewer, I want an inventory that maps every contract refusal code to its CLI source or marks it protocol-only, checked by a test so that parity is explicit and cannot drift. | High | Open | [build] | no — self-mutation: a removed code or a wrong source fails it |
| FR-013 | Event rows reference the events envelope | As a maintainer, I want request rows to reference the spec-kitty-events #92 envelope instead of redefining it so that there is one owner of the row shape. | High | Open | [build] | no |
| FR-014 | Durability acknowledgement | As a client author, I want the success body to state that the rows were appended in one write and synced before the ack so that the durability contract is visible to the client. | High | Open | [build] | no |
| FR-015 | Endpoint file format and reader | As a client author, I want a defined endpoint file (location, fields, permissions) and a reader that refuses a malformed, over-permissive or non-loopback file so that discovery fails closed. | High | Open | [build] | no |
| FR-016 | Typed client-side shapes | As a client author, I want typed request, response, refusal and endpoint shapes in the CLI whose serialized examples validate against the contract so that the client and the contract cannot drift. | High | Open | [build] | no — examples produced by the types are validated against the bundle |
| FR-017 | Single composition-root binder | As a client author, I want one binder that sets both halves of the EventBridge port at once so that an adapter is bound in one place. | Medium | Open | [build] | no |
| FR-018 | Provisional defaults for unruled questions | As a maintainer, I want idempotent retry, backpressure, token rotation, MCP mode, shutdown and the size cap to carry proposed defaults marked provisional so that open decisions are visible, not silently decided. | Medium | Open | [build] | no |
| FR-019 | Decision record | As a maintainer, I want an accepted decision record of the protocol that amends ADR 2026-10-22-1's transport question and append-semantics clause so that the ruling is on the record. | High | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bundle determinism | Two bundles of the new module from the same tree are byte-identical (0 differing bytes). | Reliability | High | Open |
| NFR-002 | Endpoint file confidentiality | The endpoint file is mode `0600` in a directory of mode `0700` on POSIX; a reader refuses any group or other permission bit (0 accepted over-permissive files across the test matrix). | Security | High | Open |
| NFR-003 | No credential echo | No refusal body, example, log message or error text in the contract or the client shapes contains a token value (0 hits in the leak scan and in a test that renders every refusal). | Security | High | Open |
| NFR-004 | Gate cost | The new contract tests add under 10 s to the contract-tools test job on a CI runner. | Performance | Medium | Open |
| NFR-005 | Quality gates | `ruff check`, `ruff format --check` and `mypy` report 0 issues on new and changed Python files. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Contract only | No service implementation, no transport and no change to how the CLI writes events today. | Technical | High | Open |
| C-002 | Operator rulings bind | Loopback HTTP on `127.0.0.1` with a random port; token file in the git common dir; service authoritative; one `O_APPEND` line write, `fsync` before ack, batched `fsync` for multi-event operations. | Technical | High | Open |
| C-003 | Envelope not redefined | The event envelope is owned by spec-kitty-events #92; the contract references it. | Technical | High | Open |
| C-004 | Shared vocabulary untouched | `contracts/_shared/` is not changed; the shared problem shape is used as is. | Technical | High | Open |
| C-005 | Coordinate by reference | #6676 (launcher) and #6193 (lock spike) are referenced, not changed. | Business | Medium | Open |
| C-006 | Priced debt | New dead-module and dead-symbol allowlist entries carry an issue and an exit (#6195, the cut-over that binds the client). | Technical | High | Open |
| C-007 | Scope of operations | Work package transitions and annotations only; the Mission-state-advance half of the port is deferred. | Business | Medium | Open |

### Key Entities

- **Write request unit**: one work package transition and its annotations, in order, with the
  request context (Mission identity, work package, actor, caller's checkout) and the resolved
  write location the service verifies.
- **Durability acknowledgement**: the persisted event ids and the statement that they were
  appended in one write and synced before the answer.
- **Refusal**: the shared problem shape with a code from a closed vocabulary, a status fixed by
  the code and, for guard refusals, a reason URN.
- **Endpoint file**: the per-clone file in the git common dir that names the port, the token,
  the instance identity and the supported protocol versions.
- **Parity inventory**: the map from each refusal code to the CLI source that raises it today, or
  to "protocol-only".

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every contract check passes with the new module counted (modules count rises by 1) and every paired negative variant is refused. — [build] · no-op passable: no
- **SC-002**: 100% of the contract's refusal codes appear in the parity inventory, and 100% of reused codes are found verbatim in their cited CLI source. — [build] · no-op passable: no
- **SC-003**: 100% of the examples serialized from the client-side shapes validate against the bundled contract. — [build] · no-op passable: no
- **SC-004**: 0 changes to the bytes the CLI writes and 0 changes to existing CLI test outcomes (the targeted suites and `make test-fast` pass unchanged). — [ratchet] · no-op passable: yes — paired with SC-001 to SC-003 on the same change

## Assumptions

- The work package transition unit is today's port unit (the transition, then its annotations);
  commit and cut move into the service at step 4 of the migration order and are reported in the
  acknowledgement as a nullable field until then.
- The client sends the resolved write location during the strangler (ADR 2026-10-22-1 D-3); the
  service verifies it.
- The protocol version is an integer major, starting at 1, sent on every request.

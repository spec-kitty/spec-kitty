---
title: 'ADR: the write-service protocol is loopback HTTP with a bearer token from the git common dir'
description: 'The CLI reaches its write service on 127.0.0.1 with a per-clone bearer token; the service is authoritative, refuses with the CLI''s codes, and acks one synced append.'
status: Accepted
date: '2026-10-27'
updated: '2026-10-29'
---

# The write-service protocol is loopback HTTP with a bearer token from the git common dir

**Status:** Accepted (2026-10-27). Operator rulings of 2026-10-25 (on #6675) and 2026-10-27 (the Decision Moments of Mission `write-service-protocol-01M5Z6N5`). Amended by [ADR 2026-10-29-1](2026-10-29-1-the-events-domain-and-its-java-services-live-in-spec-kitty-events.md) (the events services live in spec-kitty-events); see Amendment 2026-10-29.

> **What was ruled and what is derived.**
> - **Ruled by the operator (2026-10-25):** loopback HTTP on `127.0.0.1` with a random port; the port and a random bearer token in a file in the git common dir, one writer per clone; the service is authoritative and refuses with structured codes that match the CLI's; one `O_APPEND` write of a full JSON line, `fsync` before the ack, a batched `fsync` for multi-event operations; Windows semantics documented under the lock.
> - **Ruled by the operator (2026-10-27):** the refusal `code` reuses the CLI's codes verbatim and the guard reasons are minted as provisional URNs; the bearer scheme is declared natively in the contract (a narrow amendment of the contract layout check); protocol questions not yet ruled carry provisional defaults; the client side ships typed shapes and one binder with no transport; the shapes' dead-code debt is priced with the #6195 exit (Decision Moments DM-01M5Z6TDWPD1RGWDNXQGQW27C9 and DM-01M5ZC1PYHBB6QB02YQ4H1V52P: 11 dead-symbol entries in `category_c_write_service_client_6675` and one dead-module entry).
> - **Derived:** clauses marked *(derived)*.
> - **Open:** the open questions at the end carry defaults that hold until the operator rules otherwise.

**Date:** 2026-10-27

**Deciders:** Stijn Dejongh (operator).

**Technical Story:**
- #6675 (this protocol), in epic #6117 (Mission Write API).
- It amends [ADR 2026-10-22-1](2026-10-22-1-the-java-write-service-is-the-canonical-event-writer.md): open question 3 (transport and trust model) and D-7 (which append semantics are authoritative).
- Coordinated by reference, not changed: #6676 (the fail-closed launcher), #6193 (the lock-interop spike), #6195 (the lane-transition cut-over that binds the client), spec-kitty/spec-kitty-events#92 (the event envelope).
- The contract: [`contracts/mission-write/openapi.yaml`](../../../contracts/mission-write/openapi.yaml). The client shapes: `src/specify_cli/status/write_service_protocol.py`.

**Reader:** a maintainer building the write-service client behind the EventBridge port, or the Java write service, or its launcher.

---

## Context and Problem Statement

ADR 2026-10-22-1 makes a resident Java service per repository the one event writer, reached through the CLI's EventBridge port. It left the transport open, with a local socket as the default (open question 3), and left the append semantics open (D-7). Nothing defined what the CLI sends, what the service answers, how a client finds and trusts the running service, or how the two agree on a protocol version.

The read service (`services/mission-status-api`) already sets a local precedent: it binds `127.0.0.1` only and refuses a foreign `Host`, a foreign `Origin` and a cross-site fetch. It has no token, because it only reads.

The CLI refuses writes today with codes scattered over many modules, and the lane state machine's guards raise free text with no code at all; only the `orchestrator-api` edge turns them into codes (`TRANSITION_REJECTED`, `WP_ALREADY_CLAIMED`, `DEPENDENCIES_NOT_SATISFIED`). Moving validation into the service must not change a code a user or a script sees.

## Decision Drivers

- **One writer per clone** (ADR 2026-10-22-1 D-2).
- **Fail closed:** a stale endpoint, a recycled port, a foreign process or a version skew must refuse, never write to the wrong place.
- **No lost history:** a write is acknowledged only when it is durable.
- **Parity:** the service's refusals carry the codes the CLI raises today.
- **Contract first:** the client and the service are built against one checked boundary.

## Considered Options

1. **A local socket, a named pipe on Windows** (ADR 2026-10-22-1's default).
2. **Loopback HTTP on `127.0.0.1` with a random port and a bearer token** (chosen, ruled).
3. **Standard input and output of a process per write** (rejected by ADR 2026-10-22-1 D-2: a start per transition).

## Decision Outcome

**Chosen option:** "Loopback HTTP on `127.0.0.1` with a random port and a bearer token". It reuses the read service's HTTP stack, guard and contract tooling, it is the same on every platform, and an OpenAPI contract describes it with the tools the repository already runs.

### D-1: transport

- The service binds `127.0.0.1` only, on a port the operating system picks (port 0), and never `localhost`, `0.0.0.0` or IPv6 *(derived from the read service's BindGuard)*.
- Every request passes the read service's guard: `Host` is `127.0.0.1:<port>`, an `Origin` (when present) names the same, and `Sec-Fetch-Site: cross-site` is refused. A refusal is `403` with `REQUEST_REFUSED`.
- The contract is `contracts/mission-write`, served under `/api/v1`, version `1.0.0-SNAPSHOT` until its first release.

### D-2: the endpoint file and the token

- **Location** *(ruled)*: `<git-common-dir>/spec-kitty-write-service/endpoint.json`. Every worktree of a clone resolves the same git common dir, so all reach one service; a separate clone has its own.
- **Fields** *(derived)*: `schema_version` (1), `host` (`127.0.0.1`), `port`, `token`, `instance_id` (a ULID minted at each start), `pid` (diagnostics only), `protocol_versions` (informative: the handshake's list is authoritative), `started_at`.
- **Token** *(ruled: random bearer token; derived: its form)*: 32 random bytes, URL-safe base64 without padding (at least 43 characters), new on every start. It is sent as `Authorization: Bearer <token>` on every request and is never logged, echoed in a body or written anywhere else.
- **Permissions** *(derived)*: on POSIX the directory is `0700` and the file `0600`, both owned by the user. The client refuses a file or directory with any group or other permission bit, a symbolic link, a FIFO or any other non-regular file, another owner, or a host other than `127.0.0.1` (`WRITE_SERVICE_ENDPOINT_EXPOSED`, `..._NOT_LOOPBACK`, `..._MALFORMED`, `..._MISSING`). It judges the file on `lstat` before it opens it, opens it once without following a link and without blocking, and no refusal carries the token or an exception that holds the file text.
- **Windows** *(derived)*: the directory and the file carry an ACL that grants access to the owner only; the service sets it. The client, which has no mode bits to read, still refuses a link or a non-regular file and checks the shape and the loopback host.
- **One service per clone** *(derived from ADR 2026-10-22-1 D-2)*: before it publishes the file, the service takes an exclusive OS lock on `spec-kitty-write-service/service.lock` and holds it for its whole life; a second service that cannot take the lock exits without publishing. It publishes by writing a temporary file in the same directory and renaming it into place, so a reader never sees a partial file. At exit it deletes `endpoint.json` only while the file still names its own `instance_id`. Starting, health-checking and recovering a stale service is the launcher's (#6676).

### D-3: the service is authoritative

- The service validates every unit against the lane state machine, its guards and dependency gating, verifies the request's write location against its own resolution, and refuses with a code. A CLI pre-check is advisory only: it may shape a message, never skip or replace the service's check.
- **During the strangler the request carries rows, not a command** *(derived from ADR 2026-10-22-1 open questions 1 and 2)*. The client sends what the EventBridge port holds (`WorkPackageTransition`): the rows the CLI built, in order, and the request context (actor, the checkout that holds the Mission directory, relative to the repository root checkout, the Mission directory inside it, and the CLI's write contract target as `writeSurface`). The command form of ADR 2026-10-22-1 D-3, in which the service also stamps git-derived evidence (`policy_metadata.lane_head`) itself, arrives with migration step 4; until then the service does not change a row's content. Nothing a host path can leak through travels.
- Every row of a unit names the unit's `wpId`, and a row that names a Mission names the path's `missionId`; otherwise the request is `REQUEST_MALFORMED`.
- **What the port does not hold yet** *(derived)*: the destination branch (`EventLogWriteContract` has none, so `destinationRef` is null until placement moves into the service), the owned-checkout fact (the service resolves ownership itself and refuses with `OWNED_MISSION_PATH_REFUSED`), and the `missionId` of the path (the #6195 adapter reads it from the Mission's `meta.json` in the write location).
- Parity of validation will be proven by the #6194 conformance corpus.
- The port's Mission-state-advance half (the run events of `RuntimeEventEmitter`) has no operation in protocol major 1; those events stay outside #6195.

### D-4: handshake and version negotiation

- `GET /handshake` and `GET /health` need the bearer token but no protocol header. The handshake returns the supported protocol majors, the service version, the `instanceId` and the `repositoryId`.
- `repositoryId` *(derived)* is the lowercase hex SHA-256 of the UTF-8 bytes of the git common dir's real path in forward-slash form (Python `Path.resolve().as_posix()`), with the case the file system reports. Java computes the same string from `toRealPath()` with separators replaced; a cross-language fixture lands with the Java client of #6192.
- The client requires `instanceId` to equal the endpoint file's `instance_id` and `repositoryId` its own digest, or it refuses. It then sends the highest major both sides speak, on every other request, in `Spec-Kitty-Write-Protocol`. A missing header, a value that is not an integer, or an unsupported major is `400 PROTOCOL_VERSION_UNSUPPORTED`.
- A protocol major changes only with a breaking change of the contract; additive changes keep the major *(derived from the contracts versioning rule)*.

### D-5: durability

- A unit (one transition and its annotations) is appended in **one `O_APPEND` write of full JSON lines** and synced with `fsync` before the `201`. A batch of units is **one write and one `fsync`**, all or nothing. A refusal writes nothing.
- This rules ADR 2026-10-22-1 D-7's open point: the single `O_APPEND` write is authoritative, not the CLI's temporary-file-and-replace.
- **Encoding** *(derived from ADR 2026-10-22-1 D-7)*: the service owns the row encoding and writes the bytes the CLI's one encoder writes, `store.serialize_event_line`: `sanitize_event_for_log` first (it strips host and developer fields such as `hostname` and `developer_email`), then `json.dumps(..., sort_keys=True)`. It never writes the bytes as received, and it judges a retry by comparing sanitized rows as JSON values. The client sends rows unsanitized.
- **Windows:** there is no `O_APPEND` atomicity guarantee between processes; the service holds the repository's write lock around the write, and the lock's semantics on Windows are settled by the lock-interop spike (#6193). This record does not decide them.
- Where the topology commits status, the commit joins the unit at migration step 4 of ADR 2026-10-22-1; until then the acknowledgement's `statusCommit` is null.
- A fully replayed batch writes nothing and acknowledges `fsyncs: 0`; `fsynced: true` means the rows are durable, synced now or when they were first written.

### D-6: refusals

- Every refusal is the shared `Problem` (`application/problem+json`) with a `code` and the `status` that code fixes. The service checks a request in this order and answers the first refusal: the Host and Origin guard (403), the bearer token (401), the protocol header (400), the size cap (413), the body's shape (400), then the domain (404, 409, 422).
- A code that names an existing CLI refusal is **the CLI's string, verbatim** (20 codes, from `orchestrator_api/wp_lifecycle.py`, `coordination/*`, `status/locking.py`, `status/store.py` and `cli/selector_resolution.py`). A wrapper the CLI raises around another code (`BOOKKEEPING_POLICY_REFUSED`, `BOOKKEEPING_LOCK_TIMEOUT`) is never returned; the wrapped code is.
- The contract mints 9 **protocol-only** codes with no CLI counterpart: `REQUEST_MALFORMED`, `PROTOCOL_VERSION_UNSUPPORTED`, `WRITE_TOKEN_INVALID`, `REQUEST_REFUSED`, `WRITE_LOCATION_UNVERIFIED`, `EVENT_ID_CONFLICT`, `REQUEST_TOO_LARGE`, `SERVICE_BUSY` (retry the same service after `Retry-After`) and `SERVICE_DRAINING` (re-read the endpoint file).
- A guard refusal also carries `type`, a URN `urn:spec-kitty:write-refusal:<reason>` from a closed vocabulary of 15 reasons (provisional), each bound to one code. The CLI raises these reasons as text today; adopting the same vocabulary in the CLI is a follow-up.
- A refused batch names the unit that failed in `instance`, as the JSON pointer `#/units/<index>` of the request.
- The codes and reasons are written as constants rather than an `enum`, because the contract lint admits only snake_case and PascalCase enum values. Their governance is the parity inventory `tests/contract/fixtures/mission_write_refusal_parity.yaml`: a test reads each cited CLI file for the literal and holds the contract, the client vocabulary and the inventory equal.

### D-7: the event envelope is referenced, not redefined

- A request row is the spec-kitty-events envelope (spec-kitty/spec-kitty-events#92). The contract requires only `event_id` and leaves the rest of the row open; the envelope's owner defines it.

### D-8: the client side

- `specify_cli.status.write_service_protocol` holds the typed shapes of the contract (requests with `to_wire()`, responses with `from_wire()`), the refusal vocabulary, version negotiation, the repository id and the endpoint-file reader. It has no transport.
- `runtime.next._internal_runtime.events.bind_event_bridge` binds both halves of the EventBridge port at the composition root, all or nothing. Open-core binds none.
- Neither has a `src/` caller until the client adapter binds at the #6195 cut-over, so both are priced dead-code debt (ADR 2026-09-30-1) with that exit.

### D-9: the contract layout admits a security scheme

- A contract module's root `openapi.yaml` may declare `components.securitySchemes` and nothing else under `components`; anything more is still a bundled document (`TRACKED_BUNDLE`). This lets the bearer scheme be native, so a generated client sends it.

### Consequences

#### Positive

- One checked boundary for the client, the service and the launcher.
- A stale file, a recycled port or another clone's service is refused before any write.
- Moving validation into the service changes no code a user sees.
- The durability point of every write is explicit.

#### Negative

- An HTTP server sits on the write path; a local process of the same user that can read the endpoint file can write.
- 20 codes now have two homes (the CLI and the contract) until the CLI writers are deleted at the cut-over; the parity test is what keeps them equal.
- Priced dead-code debt until #6195.

#### Neutral

- The read service and its contract are unchanged.
- The CLI writes events exactly as before; nothing binds the port in open-core.

### Confirmation

- The contract checks pass for `contracts/mission-write` (layout, structure, citations, examples, leak scan, lint, bundle, generator validation, client generation).
- `tests/contract/test_mission_write_contract.py`: six operations, the bearer scheme on all, the protocol header on all but the handshake and health, closed success bodies, a `WriteRefusal` for every refusal, refusal parity with the CLI sources, and the client shapes validating against the contract.
- `tests/specify_cli/status/test_write_service_protocol.py`: the endpoint reader refuses an exposed, malformed, symlinked or non-loopback file and never names the token.

## Open questions (each with a provisional default)

Every provisional element is settled before the contract's first release (`1.0.0`): after it, a change to a closed response is a major version.

1. **Idempotent retry.** Default: a retry whose event ids are all persisted with identical rows (compared as JSON values) answers `201` with `replayed: true` and `appendedLines: 0`; an event id persisted with different content, or a unit only some of whose event ids are persisted, is `409 EVENT_ID_CONFLICT`.
2. **A torn tail.** Default: a crash between the write and the `fsync` can leave an unterminated last line. The service checks the tail of a log before it serves its first write and refuses to append after an unterminated line until it is repaired; the repair rule belongs to the lock-interop spike (#6193).
3. **Concurrency and backpressure.** Default: the service serializes writes per repository with a bounded queue; beyond it, it answers `503 SERVICE_BUSY` with `Retry-After`. It never queues without bound.
4. **Token rotation.** Default: the token changes only at a service start; there is no in-life rotation.
5. **MCP mode.** Default: none in protocol major 1; an MCP surface would be a separate deployable over the same use cases.
6. **Shutdown and idle exit.** Default: `POST /shutdown` drains (health reads `draining`, writes answer `SERVICE_DRAINING`) and exits; the service also exits after an idle period (ADR 2026-10-22-1 open question 4). Whether the launcher uses the operation, a signal or only the idle exit is open.
7. **Request size cap.** Default: 1 MiB per request (`413 REQUEST_TOO_LARGE`). A batch of more than 64 units is a shape error (`400 REQUEST_MALFORMED`).
8. **Write-location verification.** Default: until resolution moves into the service (ADR 2026-10-22-1 open question 2), a mismatch between the request's location and the service's resolution is `422 WRITE_LOCATION_UNVERIFIED`.
9. **When the status commit joins the unit** and whether the acknowledgement names it (`statusCommit`).
10. **An unknown refusal code.** Default: the client treats a code it does not know as a protocol error and refuses the write; a new code is a contract change.

## Pros and Cons of the Options

### A local socket, a named pipe on Windows

- **Pros:** file-system permissions guard the socket; no port to discover.
- **Cons:** two transports to build and test (a Unix socket and a Windows named pipe); the read service's HTTP stack, guard and contract tooling do not apply; OpenAPI does not describe it.

### Loopback HTTP with a bearer token (chosen)

- **Pros:** one transport on every platform; the read service's stack, guard and tooling apply; the contract is checked by the tools the repository already runs.
- **Cons:** a port any local process can connect to, so the token and the guard carry the trust; a file that names the port can go stale.

### A process per write

- **Pros:** nothing resident.
- **Cons:** a start on every transition (rejected by ADR 2026-10-22-1 D-2).

## More Information

- The read service: `services/mission-status-api/README.md` (bind and guard rules).
- Contract conventions: `contracts/README.md` (the security-scheme rule is added there).
- The current-state map: [event ledger writers and readers](../../architecture/event-ledger-writers-and-readers.md).

## Amendment 2026-10-29 (Accepted): the events services live in spec-kitty-events

[ADR 2026-10-29-1](2026-10-29-1-the-events-domain-and-its-java-services-live-in-spec-kitty-events.md) records the operator and CEO ruling of 2026-10-29 that the events domain's Java services and contracts move to `spec-kitty-events`, and that core consumes a released, pinned build.

- **The launcher (#6676).** The launcher stays in core and resolves the binary from the pinned release (2026-10-29-1 D-3 to D-5). The native-image build half of #6676 moves to `spec-kitty-events`. The protocol, the endpoint file and the trust model are unchanged; the pin records the protocol versions the build serves, and the launcher refuses a build whose versions do not intersect `SUPPORTED_PROTOCOL_VERSIONS`.

Nothing else in this record changes.

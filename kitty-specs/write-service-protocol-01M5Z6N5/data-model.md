# Data Model: CLI to write-service protocol

Contract field names are camelCase (the `contracts/` convention); the endpoint file is a CLI-side
file and uses snake_case like `meta.json`.

## Operations (module `mission-write`, served under `/api/v1`)

| Path | Method | operationId | Success | Notes |
|------|--------|-------------|---------|-------|
| `/handshake` | GET | `handshake` | 200 `Handshake` | The protocol header is optional here, so a client can discover the supported majors. |
| `/health` | GET | `getHealth` | 200 `Health` | For the launcher (#6676). |
| `/missions/{missionId}/work-package-transitions` | POST | `recordWorkPackageTransition` | 201 `DurabilityAck` | One unit. |
| `/missions/{missionId}/work-package-transitions/batch` | POST | `recordWorkPackageTransitionBatch` | 201 `BatchDurabilityAck` | Whole or nothing, one write, one `fsync`. |
| `/missions/{missionId}/inner-state-annotations` | POST | `recordInnerStateAnnotation` | 201 `DurabilityAck` | A standalone annotation. |
| `/shutdown` | POST | `shutdown` | 202 (no body) | Provisional. |

Every operation requires the bearer scheme `writeToken` (HTTP bearer). Every operation except
`handshake` and `getHealth` requires the header `Spec-Kitty-Write-Protocol` (an integer major, minimum 1).

## Request entities

- **EventRow**: an open object whose shape is owned by the spec-kitty-events #92 envelope (today
  the CLI's `StatusEvent` / `InnerStateChanged` row). The contract requires only `event_id` and does
  not redefine anything else.
- **RequestContext**: `actor` (string), `checkout` (repository-relative path of the caller's
  checkout, `.` for the repository root checkout), `missionDirectory` (checkout-relative Mission
  directory, the resolved write location the service verifies), `writeSurface`
  (`checkout_append` | `coordination_transaction_append`, the contract's names for the CLI's
  `EventLogWriteTarget` values), `destinationRef` (branch name or null).
- **TransitionUnit**: `wpId`, `rows` (1..n `EventRow`, the transition first, then its
  annotations), `context` (`RequestContext`). Invariant: lands whole or not at all.
- **TransitionBatch**: `units` (1..64 `TransitionUnit`). Invariant: one write, one `fsync`, all or
  nothing.
- **AnnotationRequest**: `wpId`, `row` (`EventRow`), `context`.

## Response entities (closed)

- **DurabilityAck**: `eventIds` (in write order), `appendedLines` (integer), `fsynced` (`true`),
  `statusCommit` (string or null; provisional until commit joins the unit at migration step 4),
  `replayed` (boolean; provisional idempotency).
- **BatchDurabilityAck**: `units` (one `DurabilityAck` per unit, in order), `fsyncs` (`1`, or `0` when every unit was replayed).
- **Handshake**: `protocolVersions` (integers, ascending), `serviceVersion` (string),
  `instanceId` (the endpoint file's `instance_id`), `repositoryId` (lowercase hex SHA-256 of the
  forward-slash real path of the git common dir).
- **Health**: `status` (`ready` | `draining`), `instanceId`.

## Refusal (`WriteRefusal`)

The shared `Problem` with `code` one of the constants below and `status` fixed by the code. A
guard refusal also carries `type`, a reason URN `urn:spec-kitty:write-refusal:<reason>`.

| code | status | origin |
|------|--------|--------|
| `TRANSITION_REJECTED` | 409 | CLI (`orchestrator_api/wp_lifecycle.py`) |
| `WP_ALREADY_CLAIMED` | 409 | CLI (`orchestrator_api/wp_lifecycle.py`) |
| `DEPENDENCIES_NOT_SATISFIED` | 409 | CLI (`orchestrator_api/wp_lifecycle.py`) |
| `WP_NOT_FOUND` | 404 | CLI (`orchestrator_api/wp_lifecycle.py`) |
| `MISSION_NOT_FOUND` | 404 | CLI (`cli/selector_resolution.py`) |
| `STATUS_LOCK_HELD` | 409 | CLI (`status/locking.py`) |
| `BOOKKEEPING_DOUBLE_EVENT_ID` | 409 | CLI (`coordination/transaction_errors.py`) |
| `COORD_STATUS_SURFACE_DIVERGED` | 409 | CLI (`coordination/transaction_errors.py`) |
| `PROTECTED_BRANCH_REFUSED` | 422 | CLI (`coordination/types.py`) |
| `DESTINATION_REF_NOT_FOUND` | 422 | CLI (`coordination/types.py`) |
| `DESTINATION_REF_INVALID_SHAPE` | 422 | CLI (`coordination/policy.py`) |
| `DESTINATION_REF_NOT_LOCAL` | 422 | CLI (`coordination/policy.py`) |
| `BOOKKEEPING_WORKTREE_MISSING` | 422 | CLI (`coordination/transaction_errors.py`) |
| `FALLBACK_COORD_WORKTREE_UNRESOLVED` | 422 | CLI (`coordination/status_transition.py`) |
| `COORDINATION_BRANCH_DELETED` | 422 | CLI (`coordination/surface_resolver.py`) |
| `COORDINATION_WORKTREE_UNMATERIALIZED` | 422 | CLI (`coordination/surface_resolver.py`) |
| `OWNED_MISSION_PATH_REFUSED` | 422 | CLI (`coordination/status_transition.py`) |
| `COORD_STATUS_SURFACE_UNREADABLE` | 500 | CLI (`coordination/transaction_errors.py`) |
| `STATUS_EVENT_PERSISTENCE_VERIFICATION_FAILED` | 500 | CLI (`status/store.py`) |
| `BOOKKEEPING_COMMIT_FAILED` | 500 | CLI (`coordination/transaction_errors.py`) |
| `WRITE_LOCATION_UNVERIFIED` | 422 | protocol-only (the CLI raises `StatusContractError` without a code); provisional |
| `REQUEST_MALFORMED` | 400 | protocol-only |
| `PROTOCOL_VERSION_UNSUPPORTED` | 400 | protocol-only |
| `WRITE_TOKEN_INVALID` | 401 | protocol-only |
| `REQUEST_REFUSED` | 403 | protocol-only (the Host and Origin guard; the read service's `request_refused`) |
| `EVENT_ID_CONFLICT` | 409 | protocol-only; provisional (idempotency) |
| `REQUEST_TOO_LARGE` | 413 | protocol-only; provisional (size cap) |
| `SERVICE_BUSY` | 503 | protocol-only; provisional (backpressure, with `Retry-After`) |
| `SERVICE_DRAINING` | 503 | protocol-only; provisional (shutdown: re-read the endpoint file) |

`BOOKKEEPING_POLICY_REFUSED` and `BOOKKEEPING_LOCK_TIMEOUT` are CLI wrappers: the service returns
the wrapped code (`PROTECTED_BRANCH_REFUSED`, `STATUS_LOCK_HELD`, ...), never the wrapper.

### Reason vocabulary (provisional)

`unknown_lane`, `illegal_transition`, `force_requires_actor_and_reason`, `actor_required`,
`dependencies_unsatisfied`, `workspace_context_required`, `implementation_evidence_required`,
`reason_required`, `review_ref_required`, `reviewer_approval_required`, `review_evidence_invalid`,
`force_note_required`, `done_evidence_incomplete`, `claim_held_by_other_actor`,
`start_rejected`. Each maps to one code (`dependencies_unsatisfied` → `DEPENDENCIES_NOT_SATISFIED`,
`claim_held_by_other_actor` → `WP_ALREADY_CLAIMED`, the rest → `TRANSITION_REJECTED`) and to the
CLI source text that raises it today.

## Endpoint file

`<git-common-dir>/spec-kitty-write-service/endpoint.json`, written by the service (temp file and
rename), read by the client.

| field | type | rule |
|-------|------|------|
| `schema_version` | int | `1` |
| `host` | str | exactly `127.0.0.1` |
| `port` | int | 1..65535 |
| `token` | str | URL-safe base64, at least 43 characters (32 random bytes) |
| `instance_id` | str | ULID, new on every start |
| `pid` | int | the service process id (diagnostics only, never trusted for identity) |
| `protocol_versions` | list[int] | non-empty, ascending |
| `started_at` | str | ISO-8601 UTC |

POSIX: the file is `0600` and its directory `0700`; the reader refuses any group or other bit,
a symbolic link, or another owner. Windows: an owner-only ACL (documented; the reader checks what
the platform exposes). Reader refusals: `WRITE_SERVICE_ENDPOINT_MISSING`,
`WRITE_SERVICE_ENDPOINT_MALFORMED`, `WRITE_SERVICE_ENDPOINT_EXPOSED`,
`WRITE_SERVICE_ENDPOINT_NOT_LOOPBACK`. No error text includes the token.

## Client handshake sequence

1. Read the endpoint file (refuse on any reader refusal).
2. `GET /handshake` with the bearer token; require `instanceId` to equal the file's
   `instance_id` and `repositoryId` to equal the client's own digest; pick the highest common
   major, or refuse.
3. Send writes with `Spec-Kitty-Write-Protocol: <major>`.

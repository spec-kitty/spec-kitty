# Changelog

All notable changes to the `mission-write` contract are recorded here, newest first. The module
version is the `info.version` of `openapi.yaml`.

## 1.0.0-SNAPSHOT

Initial entry (#6675, ADR 2026-10-27-1). This version is not yet released: it becomes `1.0.0` in
the release commit, and the release is the tag `contract-mission-write-v1.0.0`. Until then the
breaking-change job has no baseline and reports `NO_BASELINE_INITIAL_VERSION`.

### Added

- The bearer security scheme `writeToken`, required by every operation (the token is the one in
  the endpoint file of the git common dir).
- `GET /handshake`: the protocol majors the service speaks, its version, its instance id and the
  identity of the clone it serves (`Handshake`). It needs no protocol header.
- `GET /health`: `ready` or `draining`, and the instance id (`Health`, `HealthStatus`). Like the
  handshake it needs no protocol header.
- `POST /missions/{missionId}/work-package-transitions`: one transition unit (`TransitionUnit`:
  the rows in order, the request context) acknowledged after one synced write (`DurabilityAck`).
- `POST /missions/{missionId}/work-package-transitions/batch`: up to 64 units in one write and
  one `fsync`, all or nothing (`TransitionBatch`, `BatchDurabilityAck`).
- `POST /missions/{missionId}/inner-state-annotations`: one standalone annotation
  (`AnnotationRequest`).
- `POST /shutdown`: drain and exit.
- The header parameter `Spec-Kitty-Write-Protocol` (`ProtocolVersion`), required by every
  operation except `handshake` and `health`.
- `EventRow`: the row shape is the spec-kitty-events envelope (spec-kitty/spec-kitty-events#92),
  referenced, not redefined; only `event_id` is required here.
- `RequestContext` and `WriteSurface`: the actor, the caller's checkout and the resolved write
  location the service verifies.
- `WriteRefusal`, `WriteRefusalCode` (29 codes; 20 are the CLI's codes verbatim and 9 are
  protocol-only) and `WriteRefusalReason` (15 guard reasons as URNs, each bound to its code), with
  one response per status family. A refused batch names the failing unit in `instance`.

### Changed

- Nothing yet.

### Removed

- Nothing yet.

### Provisional

- `statusCommit` and `replayed` of `DurabilityAck`: when the status commit joins the unit, and
  idempotent retry.
- `WriteRefusalReason`: the guard reason vocabulary and its carriage in `type`.
- `HealthStatus` (`draining`) and the operation `/shutdown`: how the service is stopped.
- The protocol-only codes `EVENT_ID_CONFLICT`, `SERVICE_BUSY`, `SERVICE_DRAINING`,
  `REQUEST_TOO_LARGE` and `WRITE_LOCATION_UNVERIFIED` are provisional. An enum value cannot carry
  `x-provisional`, so they are marked in their descriptions only, and `provisional_check.py` does not
  see them: removing one of them later is a breaking change.
- Every provisional element is settled before the first release (`1.0.0`): after it, a change to
  a closed response is a major version.

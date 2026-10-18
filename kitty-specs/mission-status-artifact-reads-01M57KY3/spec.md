# Mission Specification: Mission Status Read API: artifact reads and dashboard route inventory

**Mission Branch**: `issue-957-dashboard-read-rehome`
**Created**: 2026-10-18
**Status**: Draft
**Input**: Operator task: "Run ONE governed Spec Kitty mission for #5533 and #957, under epic #5528 (ADR 2026-10-01-2, D-8). Inventory first (#5533); implement #957: mission-detail read-only artifact routes on the read path, per the contract. Build only on the open-core Read API. Governance reads (#954/#955 closed not-planned): do not implement; list proposed replacement slices for the operator."

## Context

The bundled dashboard was deleted by #5530 (PR #5545, commit `3d5c85d09`, 2026-10-01). Its status routes have a home in
the Mission Status Read API (ADR `docs/adr/4.x/2026-10-01-2-mission-status-read-api-and-dashboard-extraction.md`, D-2,
D-9, D-10). Its artifact and governance routes do not yet. The `mission-status` contract (`contracts/mission-status/`,
`1.0.0-SNAPSHOT`) already defines two artifact operations, `listArtifacts` and `getArtifactContent` (added by #5625),
and a test-side Python reference reader executes their rules (`tests/contract/_mission_status_artifacts.py`). The Java
read service (`services/mission-status-api/`, #5529) serves only the project header, the Mission overview page, the
change stream and the contract document; every other contract path answers 404 by design.

This Mission does two things:

1. **Inventory (#5533).** Every route of the removed dashboard is recovered from git history (the parent of `3d5c85d09`)
   and given exactly one home: a contract operation, a governance domain verb with `--json`, or DROPPED. The mapping is a
   committed artifact of this Mission (`route-inventory.md`).
2. **Artifact reads (#957, artifact slice).** The Java read service serves `listArtifacts` and `getArtifactContent` as the
   contract writes them, giving the same answer as the Python reference reader.

**Clean-room constraint.** PRs #6264 and #6265 were retracted by their author with an explicit request that their work
not be used. Nothing in this Mission is derived from their branches, commits, diffs or review threads. Every input is
`main`, git history before #5545, the ADRs, the contract and the issues' own text.

### Discovery decisions (recorded from the operator task and the issues)

- **D1 — which read path.** The artifact routes are served by the Java read service, the external form of the Read API
  (ADR amended D-4, D-10: "#957 the detail resource"). The CLI's native Python read path is not extended here; no CLI
  `--json` verb is added for artifacts in this Mission.
- **D2 — no contract change.** The contract is implemented as written. A disagreement between the contract text and the
  Python reference is reported, never resolved by editing the contract in this Mission.
- **D3 — split.** `getMission`, `getWorkPackage` and `getWorkPackageDetail` stay open on #957 for a later slice (they
  depend on the WP-file reader and the phase basis). This Mission is the artifact slice only.
- **D4 — governance is not implemented.** #954 and #955 stay closed not-planned. Proposed replacement slices are listed in
  the inventory and the PR for the operator to decide.
- **D6 — the reference order binds where the contract text is looser (post-spec squad).** The contract's prose orders
  413 before 500 and says an oversize file "is not read". The reference opens the file and takes the size from the open
  handle first, so an oversize file that cannot be opened is 500. This Mission follows the reference: open (failure 500),
  size from the open handle (over the cap 413, content not read), then read. The contract text is not edited (C-001).
  The disagreement is reported in the PR for the contract owner.
- **D7 — the Mission index is the service's.** The reference rebuilds an uncapped index of every `meta.json` per call.
  The service reads each `meta.json` through its existing 1 MiB cap, with no link followed at the final component. A
  `meta.json` over the cap, or one that cannot be read or parsed, is skipped as the reference skips an unparseable one.
  This is a recorded divergence for files over 1 MiB only.
- **D5 — lifecycle events untouched.** The `spec-kitty-events` package is extracting the Mission Lifecycle events to host
  them canonically. This Mission does not touch `/events`, `MissionLifecycleEvent` or the lifecycle reducer.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A UI lists and reads a Mission's planning artifacts (Priority: P1)

A dashboard (for example `spec-kitty-mission-ui`) shows one Mission's spec, plan, tasks, research, contracts, checklists,
work package prompts and review cycles, as the removed dashboard did, by calling the local read service.

**Why this priority**: it is the user-visible gap the dashboard removal left; artifacts are files, not events, so no other
read surface serves them.

**Independent Test**: start the service against a fixture project; `GET /api/v1/missions/{missionId}/artifacts` returns
the eligible files, and `GET .../artifacts/content?path=spec.md` returns the redacted text.

**Acceptance Scenarios**:

1. **Given** a Mission with `spec.md`, `plan.md`, `research/notes.md` and `tasks/WP01-x.md`, **When** the listing is read,
   **Then** each is one entry, sorted by path in UTF-8 byte order, with the contract kind, size, whole-second UTC
   modification time and `readable: true`, and `status.events.jsonl` / `status.json` are not listed.
2. **Given** a text artifact that names a home directory and an e-mail address, **When** its content is read, **Then** the
   body carries `[path]` and `[email]` in their place and `redacted: true`, and `sizeBytes` is the raw file size.
3. **Given** an unknown Mission id, **When** either operation is called, **Then** the answer is 404 `not_found`.

### User Story 2 - The service refuses what it must not serve (Priority: P1)

An operator runs the service against a project they trust. It must never serve a credential, never follow a link out of
the Mission, and never read an oversize file.

**Why this priority**: the removed dashboard was deleted for its trust defects (#4767–#4769, #4249); the replacement must
not reopen them.

**Independent Test**: a fixture with a symbolic link, a file holding a GitHub token, a NUL-byte file, an invalid UTF-8
file and a 262,145-byte file; each read answers the contract's refusal and the listing marks each `readable: false` (the
link is not listed).

**Acceptance Scenarios**:

1. **Given** a file holding `ghp_` plus 36 alphanumerics, **When** it is read, **Then** 422 `artifact_secret` and no content.
2. **Given** `research` is a symbolic link to a directory outside the Mission, **When** the listing is read or
   `research/x.md` is requested, **Then** nothing below it is listed and the read is 404 `not_found`.
3. **Given** a path `../meta.json`, `/etc/passwd`, `a\b`, an empty path, or the parameter sent twice, **When** the content
   is read, **Then** 400 `invalid_artifact_path`.
4. **Given** a file of 262,145 bytes, **When** it is read, **Then** 413 `artifact_too_large`. The file is opened and its
   size taken from the open handle, but its content is not read (D6).

### User Story 3 - The operator knows where every removed dashboard route went (Priority: P2)

The operator and the UI contributors can look up each removed route and see its new home or that it was dropped, and why.

**Why this priority**: #5533's acceptance; it unblocks the UI repository's migration.

**Independent Test**: every route in `router.py` at `3d5c85d09^` appears exactly once in `route-inventory.md` with a home.

**Acceptance Scenarios**:

1. **Given** the router of `3d5c85d09^`, **When** the inventory is checked, **Then** every route (and every dossier
   sub-route) has one row naming a contract operation, a verb, or DROPPED with its reason.

### Edge Cases

- A Mission directory with more than 1000 eligible files: the first 1000 in byte order, `truncated: true`.
- A file that vanishes between the walk and its stat: omitted from the listing.
- A file name that is not valid UTF-8 on disk, or a path over 512 characters: not eligible, never listed.
- A root status record named with other case (`STATUS.JSON`): not an artifact (404), as the contract writes.
- Two Mission directories holding the same `mission_id`: the first in name order is served, as the reference does.
- A Mission directory that cannot be listed but can be traversed (mode 0311): the listing is 500 `artifact_listing_unreadable`.
  A content read still succeeds, because an lstat needs only search permission. A Mission directory whose lstat fails is
  500 `artifact_unreadable` for a content read and 500 `artifact_listing_unreadable` for a listing.
- Lengths are counted in Unicode code points (Python `len`, JSON Schema `maxLength`), never in UTF-16 units. Names sort by
  code point, which equals UTF-8 byte order.
- The root status records match by Python `str.casefold()`, so `STATUS.JSON`, `ſtatus.json` (U+017F) and `ﬆatus.json`
  (U+FB06) are status records and are refused 404.
- A `path` query value with a malformed percent-encoding is 400 `invalid_artifact_path`.
- Residuals (accepted, as the service README's threat note accepts them): every component is checked with lstat before
  the open, and the open itself refuses a link only at the final component, so an intermediate directory swapped for a link
  between the check and the open is not caught. A hard link to a file outside the Mission is a regular file and is served
  when no credential pattern matches. A path swapped for a FIFO after the check can block the open. On a case-insensitive
  or normalizing file system (macOS), `SPEC.md` and an NFD name reach the same file as their canonical forms. Under a
  non-UTF-8 locale the JVM cannot represent non-ASCII names, so a run needs a UTF-8 locale.
- An empty file: 200 with `content: ""`, `sizeBytes: 0`, `redacted: false`.
- A leading byte order mark: kept in `content`.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Route inventory | As the operator, I want every route of the removed dashboard mapped to a contract operation, a governance `--json` verb, or DROPPED, in one committed artifact, so that #5533's acceptance is checkable. | High | Open | [build] | no — a check counts the router's routes against the inventory rows |
| FR-002 | listArtifacts served | As a UI, I want `GET /api/v1/missions/{missionId}/artifacts` to return the contract's `ArtifactListing` so that I can show a Mission's files. | High | Open | [build] | no — the route answered 404 before this Mission |
| FR-003 | getArtifactContent served | As a UI, I want `GET /api/v1/missions/{missionId}/artifacts/content?path=` to return the contract's `ArtifactContent` so that I can show one file. | High | Open | [build] | no — the route answered 404 before this Mission |
| FR-004 | Eligibility and path rule | As an operator, I want the service to accept only the contract's artifact paths and eligible files (no symlink anywhere on the path, regular file, not a root status record) so that nothing outside the Mission is served. | High | Open | [build] | no — paired negative fixtures (link, `..`, status records) on the same tree as a positive |
| FR-005 | Order of decision and refusals | As a client, I want each refusal (400, 404, 413, 415, 422, 500) as an `application/problem+json` body with `type: about:blank`, `status`, the contract's code and the reference's fixed title and detail, decided in the reference's order (D6), so that I can branch on `code`. | High | Open | [build] | no — one fixture per code |
| FR-006 | Redaction and credential refusal | As an operator, I want host paths and e-mail addresses redacted and credential-bearing files refused, with the same patterns as the Python source of truth (`leak-patterns.json`), so that no secret or host detail is served. | High | Open | [build] | no — a planted token, path and address |
| FR-007 | Conformance with the Python reference | As the contract owner, I want the Java answers to equal the Python reference reader's on shared fixture trees so that there is one answer with two implementations (ADR amended D-5). | High | Open | [build] | no — the same fixtures run through both; a planted difference fails |
| FR-008 | Out-of-scope routes stay 404 | As the contract owner, I want the remaining unimplemented operations (`getMission`, `getWorkPackage`, `getWorkPackageDetail`, `/drift`, `/ops/invocations`) to keep answering 404 like any unknown path. | Medium | Open | [ratchet] | yes — unchanged behaviour, pinned by the existing test |
| FR-009 | Read allowlist documented | As an operator, I want the service's README and its allowlist constant to name the artifact reads exactly, entry for entry, so that what the service opens stays reviewable. | Medium | Open | [build] | no — the parity test fails on a missing entry |
| FR-010 | Governance replacement slices proposed | As the operator, I want proposed replacement slices for the governance reads (charter body, glossary health/terms, decay watch) listed, not implemented, so that I can decide. | Low | Open | [build] | yes — documentation only |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded reads | No read of an artifact exceeds 262,145 bytes; a file over 262,144 bytes is decided from its size and its content is not read. A listing visits at most the eligible tree and returns at most 1000 entries. | Performance | High | Open |
| NFR-002 | No link following | Every component below the Mission directory is checked with lstat before any open or listing, and the open uses NOFOLLOW on the final component. The walk never enters a link. The residual window between check and open is documented (Edge Cases). | Security | High | Open |
| NFR-003 | No echo | No refusal body carries the requested path, a Mission directory, file content or an operating-system message. | Security | High | Open |
| NFR-004 | Read-only | The service writes nothing, takes no lock, starts no process for these routes, and stays behind the existing loopback Host/Origin guard. | Security | High | Open |
| NFR-005 | Latency | Measured, not gated: on a warm JVM (after 5 discarded requests), the median of 20 listings of this repository's largest Mission directory by file count, and of 20 content reads of its `spec.md`, recorded in the PR. Target: listing under 500 ms, content under 100 ms. | Performance | Medium | Open |
| NFR-006 | Regular files only | A file is opened only after an lstat shows a regular file. The walk never opens a FIFO, a socket or a device, and the size is taken from the open handle. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Contract unchanged | `contracts/mission-status/` is not edited; the version stays `1.0.0-SNAPSHOT`. | Technical | High | Open |
| C-002 | Open-core only | No hosted, sync, drain or auth surface is added or referenced (AGENTS.md "Team Kitty" section, ADR D-9/D-10). | Business | High | Open |
| C-003 | Clean room | Nothing from PRs #6264 / #6265 is opened or used. | Business | High | Open |
| C-004 | Governance not implemented | No charter, glossary, lint or diagnostics read is added to the read service or the CLI. | Business | High | Open |
| C-005 | Lifecycle events untouched | `/events`, `MissionLifecycleEvent` and the reducer are not changed (spec-kitty-events extraction). | Technical | High | Open |
| C-006 | Test policy | Targeted tests plus `make test-fast` and the service's own Gradle `test`; no `make test-full` and no whole `tests/architectural/` sweep. | Technical | Medium | Open |

### Key Entities

- **Artifact**: an eligible regular file below a Mission's primary directory (`kitty-specs/<mission>/`), identified by its
  forward-slash path relative to that directory, classed by the contract's ordered path classifier.
- **Route inventory row**: one removed dashboard route, its handler, what it read, and its new home or DROPPED reason.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the routes in the router of `3d5c85d09^` (28 rows once the artifact names, the listing/file split and the four dossier sub-routes are expanded) have exactly one row in the inventory — [build] · no-op passable: no
- **SC-002**: Both artifact operations answer every response the contract lists (200, 400, 404, 413, 415, 422, 500), each validated against the contract schema — [build] · no-op passable: no
- **SC-003**: On every shared conformance fixture, the Java body and status equal the Python reference's, field for field — [build] · no-op passable: no
- **SC-004**: The service's Gradle `test` task is green with the artifact routes removed from the out-of-scope list and every other out-of-scope route still 404 — [ratchet] · no-op passable: no

## Assumptions

- The Python reference reader is the executable statement of the contract's rules for these operations; where it and the
  contract text agree, both are binding.
- `modifiedAt` depends on the host and is excluded from byte-for-byte conformance comparison (the contract says so); it is
  compared by format.
- The Mission directory is the primary planning surface `kitty-specs/<mission>/`, never a coordination copy, as the
  reference reader states (planning artifacts live on the primary partition).

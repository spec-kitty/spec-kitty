# Mission Specification: Pinned service binaries

**Mission Branch**: `issue-6590-pinned-service-binaries`
**Created**: 2026-10-29
**Status**: Draft
**Input**: User description: "Pinned service binaries for core: one mechanism to pin, fetch, verify and launch backend service binaries released by sibling repositories (spec-kitty-events `service-v*` now, spec-kitty-charter later), with a fail-closed launcher." Governed by [ADR 2026-10-29-1](../../docs/adr/4.x/2026-10-29-1-the-events-domain-and-its-java-services-live-in-spec-kitty-events.md); see also ADR 2026-10-22-1 (D-2, D-5), ADR 2026-10-27-1 (endpoint file, handshake, health) and ADR 2026-10-03-1 (charter service trust model).

## Intent Summary (confirmed 2026-10-29)

- **Actors:** a CLI user whose command needs a backend service; a core maintainer who bumps a pin; CI.
- **Triggers:**
  - the first time a command needs the write service (the charter service later);
  - `make sync-services` in a checkout or a CI job;
  - `spec-kitty service vendor` for a pin bump.
- **Outcome:** the CLI runs only a binary whose bytes match the pinned digest. The binary is fetched once into a shared cache, then started or reused within its scope. The write service is one instance per repository (git common dir).
- **Rules that always hold:**
  - No unverified binary runs. The one exception is the developer opt-in: `SPEC_KITTY_SERVICE_UNPINNED=1` plus an explicit path, which warns on every start.
  - A missing, mismatched, unsupported or unhealthy service refuses with a named code and a remedy.
  - There is no fallback writer in Python.
  - CLI reads never need a binary.
  - The wheel ships no binary.
  - HTTP release downloads have one owner module and a gate.
- **Decisions (Decision Moments):** this mission builds the full launcher lifecycle now, tested against a fake service (DM-01M64N7524YHFFNB9HJKBX1EVA). Unpinned local binaries are allowed only behind the opt-in (DM-01M64N7896B6GT50FWXZ3E5K70).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A command gets a verified service without manual setup (Priority: P1)

A CLI user runs a command that needs the write service. They have never installed a service. The CLI finds no running instance, fetches the binary for their platform from the pinned release, checks its digest and starts it. The command then proceeds. On the next command the CLI reuses the running instance.

**Why this priority**: every later step of the events-domain move depends on the CLI being able to obtain and start a trustworthy service. Without it the write path cannot move off the in-process writer.

**Independent Test**: point the pin at a local fixture release that contains a fake service binary. Run the resolve-and-start entry point twice in a clean cache. The first run fetches, verifies, starts and returns a healthy endpoint. The second run starts nothing and returns the same instance.

**Acceptance Scenarios**:

1. **Given** an empty cache and a pin whose asset for the host platform exists, **When** the launcher is asked for the write service, **Then** it downloads that asset, verifies its digest, starts it, waits for a healthy handshake and returns its endpoint.
2. **Given** a healthy instance already published for this repository, **When** the launcher is asked again, **Then** it reuses that instance and starts no new process.
3. **Given** the cached binary's bytes no longer match the pin, **When** the launcher resolves it, **Then** it discards the cached copy, fetches again, and runs only bytes that match.

---

### User Story 2 - A missing or untrustworthy service refuses clearly (Priority: P1)

A user is offline, on an unsupported platform, or has a corrupted download. Their command stops with a named reason and a concrete next step. It never runs an unverified binary and never falls back to writing in-process.

**Why this priority**: fail-closed behaviour is a binding rule (ADR 2026-10-22-1 D-5). A silent fallback would bring back two writers.

**Independent Test**: drive the launcher against fixtures for each failure: no network and no cache, digest mismatch, unsupported platform with no JVM, a service that never becomes healthy, and a service that reports an incompatible protocol version. Check each refusal code and remedy text.

**Acceptance Scenarios**:

1. **Given** no cached binary and an unreachable release host, **When** the write service is needed, **Then** the command refuses with `SERVICE_BINARY_MISSING`. The remedy names `spec-kitty service fetch` and the offline asset directory.
2. **Given** a downloaded asset whose digest differs from the pin, **When** it is verified, **Then** the command refuses with `SERVICE_BINARY_DIGEST_MISMATCH` and nothing is executed.
3. **Given** a host platform the pin has no native asset for, and no Java runtime of the required version, **When** the service is needed, **Then** the command refuses with `SERVICE_UNSUPPORTED_PLATFORM`.
4. **Given** a started service that does not answer a healthy handshake within the start budget, **When** the launcher waits, **Then** it stops that process and refuses with `SERVICE_UNHEALTHY`.
5. **Given** a running service whose protocol versions do not intersect the CLI's, or whose instance or repository identity does not match, **When** the launcher connects, **Then** it refuses with `SERVICE_VERSION_MISMATCH`.
6. **Given** any of these refusals, **When** a read-only CLI command (for example a status read) runs, **Then** it still succeeds.

---

### User Story 3 - Developers and CI get the same binaries the user gets (Priority: P2)

A maintainer runs `make sync-services` in a fresh checkout or worktree. CI runs the same step through a shared action. Both fetch every pinned asset the job needs into the shared cache and verify it. `--offline` works from the cache alone, and `--check` verifies without fetching.

**Why this priority**: CI conformance against the read service, and every developer run, must use the same verified bytes users get, mirroring how pack trees are fetched today.

**Independent Test**: with a fixture pin, run the sync command in online, offline (warm cache) and check modes. Confirm the exit codes, the cached files and their digests. Corrupt one cached file and confirm `--check` fails and an online run repairs it.

**Acceptance Scenarios**:

1. **Given** a fixture pin, **When** `make sync-services` runs, **Then** every pinned asset for the requested services and the host target is in the cache with a matching digest, and the command exits 0.
2. **Given** a warm cache and no network, **When** the sync command runs with `--offline`, **Then** it succeeds without contacting any host.
3. **Given** a corrupted cached asset, **When** the sync command runs with `--check`, **Then** it exits non-zero and names the asset. An online run then replaces the asset.

---

### User Story 4 - A maintainer bumps a pin through one command (Priority: P2)

When a new `service-v*` release exists, a maintainer runs `spec-kitty service vendor --service <name> --tag <tag>`. The command resolves the tag to its commit, downloads every asset, records each digest and rewrites only the lockfile. A CI gate fails when the lockfile is malformed, still a placeholder, or disagrees with the release.

**Why this priority**: hand-edited digests are how a pinning scheme silently decays. One bump path keeps the lockfile honest.

**Independent Test**: run the vendor command against a local fixture release and compare the written lockfile with the release's published checksums. Run `--check` on a tampered lockfile and expect a refusal.

**Acceptance Scenarios**:

1. **Given** a fixture release with per-target assets and a checksum list, **When** `spec-kitty service vendor` runs, **Then** the lockfile records the tag, the resolved commit, each asset's name and digest, and the protocol versions, and no other file changes.
2. **Given** a release whose published checksum list disagrees with the downloaded bytes, **When** the vendor command runs, **Then** it refuses and leaves the lockfile unchanged.
3. **Given** a release requiring a newer core than the running one, **When** the vendor command runs, **Then** it refuses with the version requirement named.

---

### User Story 5 - A developer runs a locally built service on purpose (Priority: P3)

A developer working in spec-kitty-events builds a service locally and wants the CLI to use it. They set `SPEC_KITTY_SERVICE_UNPINNED=1` and point the CLI at the binary's path. The CLI runs it and prints a warning on every start. Without the opt-in, the same path is refused unless its digest matches the pin.

**Why this priority**: it unblocks cross-repository development without weakening the default. It is only a convenience.

**Independent Test**: point the explicit-path setting at a fake binary that matches no pin. Without the opt-in, expect `SERVICE_BINARY_DIGEST_MISMATCH`. With the opt-in, expect a start and a warning line.

**Acceptance Scenarios**:

1. **Given** an explicit binary path whose digest matches no pin and no opt-in, **When** the service is needed, **Then** the command refuses with `SERVICE_BINARY_DIGEST_MISMATCH`.
2. **Given** the same path with `SPEC_KITTY_SERVICE_UNPINNED=1`, **When** the service is needed, **Then** it starts and a warning naming the unpinned path is printed on every start.

### Edge Cases

- Two CLI processes start the write service for the same repository at the same moment: exactly one instance survives. The other process reuses it, guarded by the service's exclusive lock and endpoint file (ADR 2026-10-27-1 D-2).
- A stale endpoint file names a process that has died, or a recycled process id: the launcher treats it as stale and starts a fresh instance. It never trusts a process id alone; it checks the instance identity through the handshake.
- An endpoint file that is a symlink, world-readable, or names a non-loopback host is refused with the existing `WRITE_SERVICE_ENDPOINT_*` codes and never connected to.
- A download is interrupted midway: no partial file is ever executed, and the next run starts over.
- The cache directory is not writable: the command refuses with `SERVICE_BINARY_MISSING`, and the remedy names the asset directory override.
- The pin is still the committed placeholder (no release yet): every resolve refuses with a pin-invalid code instead of trying to download.
- Windows: the native asset carries `.exe`. The asset directory and cache paths follow the existing cross-platform cache-root rules used for packs.
- A JVM fallback is selected (native asset absent, Java of the required major version present): the jar's digest is verified just like a native binary.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Service pin lockfile | As a maintainer, I want one lockfile per service recording the release tag, the resolved commit, the protocol versions, the minimum core version and, per target, the asset name and digest, so that every consumer runs the same bytes. Placeholder and malformed pins are refused on load. | High | Open | [build] | no — a malformed or placeholder pin fixture must be refused, paired with a valid pin on the same fixture |
| FR-002 | Digest-verified fetch into a shared cache | As a CLI user, I want a pinned asset fetched once into a per-service, per-tag cache and re-verified on every resolve, so that a corrupted or tampered cache is never trusted. | High | Open | [build] | no — a cached file with flipped bytes must be discarded and refetched |
| FR-003 | One owner for release-asset downloads | As a maintainer, I want every HTTP download of a release asset to go through a single module, enforced by a gate with an empty allowlist, so that timeout, proxy and scheme policy are decided once. | High | Open | [build] | no — a planted download call outside the owner must fail the gate |
| FR-004 | Binary resolution order | As a CLI user, I want the launcher to resolve a service binary in a fixed order (explicit path, install-provided slot, cached native asset, verified JVM jar with a matching Java runtime, refusal), so that the outcome is predictable and the most specific source wins. | High | Open | [build] | no — each tier is exercised by a fixture where only that tier is available |
| FR-005 | Fail-closed refusals with remedies | As a CLI user, I want a missing, mismatched, unsupported, unhealthy or incompatible service to refuse with `SERVICE_BINARY_MISSING`, `SERVICE_BINARY_DIGEST_MISMATCH`, `SERVICE_UNSUPPORTED_PLATFORM`, `SERVICE_UNHEALTHY` or `SERVICE_VERSION_MISMATCH` and a concrete remedy, never falling back to in-process writing, so that I know exactly what to do. | High | Open | [build] | no — each code has its own failing fixture, plus a passing fixture on the same harness |
| FR-006 | Launch-when-down, reuse when up | As a CLI user, I want the write service started once per repository and reused across invocations, discovered through the endpoint file in the git common dir, so that commands stay fast and there is one writer. | High | Open | [build] | no — the second resolve must start no process (process-count assertion) |
| FR-007 | Health and identity on every connect | As a CLI user, I want the launcher to confirm a healthy handshake whose instance and repository identity and protocol version match before handing out an endpoint, so that I never talk to a stale or foreign process. | High | Open | [build] | no — a fake service with a mismatched repository id must be refused |
| FR-008 | Stale-instance recovery | As a CLI user, I want a dead or unhealthy published instance replaced by a fresh one, with process identity checked beyond the process id, so that a crash does not block my next command. | Medium | Open | [build] | no — a stale endpoint naming a dead process must result in a new healthy instance |
| FR-009 | Explicit stop | As a maintainer or a test, I want a way to stop a running service instance for a repository, so that cleanup is deterministic. | Medium | Open | [build] | no — after stop, the endpoint is gone and a later resolve starts a new instance |
| FR-010 | Pre-fetch and offline asset directory | As a user on a restricted network, I want `spec-kitty service fetch` to pre-fetch assets, and an asset-directory setting to supply them offline (still digest-checked), so that I can work air-gapped. | Medium | Open | [build] | no — with the network disabled, an asset directory fixture must satisfy the resolve and a wrong-digest file in it must be refused |
| FR-011 | Developer opt-in for unpinned binaries | As a developer, I want `SPEC_KITTY_SERVICE_UNPINNED=1` plus an explicit path to run a locally built binary with a warning on every start, so that I can test cross-repository changes. Without the opt-in the same path must match the pin. | Low | Open | [build] | no — the same fixture is refused without the opt-in and started with it |
| FR-012 | Sync command for checkouts and CI | As a maintainer, I want `make sync-services` (with `--offline` and `--check`) and a shared CI action that fetch and verify the pinned assets a job needs, so that developer and CI runs use the user's bytes. | High | Open | [build] | no — `--check` on a corrupted cache must exit non-zero |
| FR-013 | Single bump command and pin gate | As a maintainer, I want `spec-kitty service vendor --service --tag` to be the only path that rewrites a lockfile, and a CI gate that fails on a malformed or drifted pin, so that digests are never hand-edited. | High | Open | [build] | no — a tampered lockfile must fail `--check` |
| FR-014 | No binary in the wheel or sdist | As a release owner, I want the packaging guard to prove that no service binary or cache content ships in the wheel or sdist, while the lockfiles do ship, so that the wheel stays pure. | High | Open | [ratchet] | yes — paired with a planted binary in a scratch build tree that the guard must reject |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Warm-path latency | With a healthy instance already running, the resolve-and-connect step adds at most 150 ms (p95 over 20 runs on the CI Linux runner) to a command. | Performance | High | Open |
| NFR-002 | Cold start budget | A cold start, from a cached binary to a healthy handshake, gives up after 15 s by default (configurable) and then refuses with `SERVICE_UNHEALTHY`. The fake service used in tests starts within 2 s. | Reliability | High | Open |
| NFR-003 | Nothing unverified executes | 100% of executed binaries are digest-verified against the pin immediately before execution, except under the explicit developer opt-in. This is proven by a test that counts executions against verifications. | Security | High | Open |
| NFR-004 | Bounded downloads | A download aborts after a 60 s inactivity timeout and accepts only `https://` (and `file://` for fixtures) sources. Proxy settings from the environment are honoured. | Security | High | Open |
| NFR-005 | Owner-only endpoint secrets | Files the launcher writes or trusts that contain a token are owner-only (POSIX 0600 or 0700, an owner-only ACL on Windows), consistent with ADR 2026-10-27-1. | Security | High | Open |
| NFR-006 | Cross-platform | The resolution, cache and launcher behaviour passes its tests on Linux and macOS in the per-PR matrix and on Windows in the Windows lane. | Portability | Medium | Open |
| NFR-007 | Quality gates | New code passes ruff, ruff format, mypy and the complexity ceiling of 15, with no new suppressions. New branches meet the 90% diff-coverage gate. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Follow ADR 2026-10-29-1 | Lockfile shape, cache location, resolution order, refusal codes, CI-only read service and the single download owner follow ADR 2026-10-29-1 D-3 to D-8. Any deviation needs an ADR amendment. | Technical | High | Open |
| C-002 | Mirror the packs precedent | Pin, fetch, cache, sync and vendor mirror the pack pin tooling (pin model, fetch-and-verify, sync script, composite action, vendor command), so maintainers recognise one pattern. | Technical | High | Open |
| C-003 | No real pin before the release | No lockfile with real digests is committed until spec-kitty-events cuts its first `service-v*` release. Until then tests use a local fixture release. A committed placeholder pin, if any, must be refused at resolve time. | Business | High | Open |
| C-004 | Layering | Pin, fetch and cache primitives live in the root `kernel` layer. The launcher and CLI commands live in `specify_cli`. No new layer edges violate the enforced chain, and no `pyproject.toml` package set change is needed. | Technical | High | Open |
| C-005 | Out of scope | Removing `services/` (the cut-over), binding the EventBridge to the write service (#6195), charter seam routing, and building native images are out of scope. | Business | High | Open |
| C-006 | Protocol fidelity | The launcher speaks the ADR 2026-10-27-1 protocol (endpoint file, handshake, health, bearer token) using the existing `write_service_protocol` shapes and does not redefine them. | Technical | High | Open |
| C-007 | Read service never launched by the CLI | No CLI command starts the read service. It is pinned for CI conformance only (ADR 2026-10-29-1 D-6). | Technical | Medium | Open |

### Key Entities

- **Service pin**: the recorded choice of one released build per service. It holds the service name, source repository, tag, resolved commit, protocol versions, minimum core version, and per target the asset name and digest. Optional entries cover the contract-bundle, contract-tools and conformance-fixture assets.
- **Service target**: a platform key (linux-x64, linux-arm64, macos-arm64, windows-x64, plus a platform-neutral JVM jar) mapped to the host.
- **Cached asset**: a downloaded file stored per service and tag. It is trusted only while its digest matches the pin.
- **Service instance**: a running service for a scope (the git common dir for the write service; a worktree for the charter service). It is published through an endpoint file with host, port, token, instance id, process id and protocol versions.
- **Refusal**: a named failure code with a human remedy, raised instead of any fallback.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a clean environment, a command that needs the write service gets a verified, running instance on its first run with no manual setup, and the second run starts no new process. — [build] · no-op passable: no
- **SC-002**: Each of the five failure situations (offline with no cache, tampered download, unsupported platform without Java, never-healthy service, incompatible service) produces its own named refusal and remedy, and in none of them does any unverified code run. — [build] · no-op passable: no
- **SC-003**: Read-only commands succeed on a machine that has no service binary at all. — [ratchet] · no-op passable: yes, paired with SC-002's refusal on the same machine for a write
- **SC-004**: A maintainer can move a service to a new release with one command, and CI rejects any pin that was hand-edited or does not match its release. — [build] · no-op passable: no
- **SC-005**: Released wheels and sdists contain zero service binaries. — [ratchet] · no-op passable: yes, paired with a planted-binary build that the guard rejects

## Assumptions

- spec-kitty-events publishes per-target assets, a JVM jar, the contract-bundles, contract-tools and conformance-fixtures assets, and a `SHA256SUMS` file under stable names on `service-v<ver>` (agreed with the spec-kitty-events side on 2026-10-29). Only `<ver>` changes between releases.
- The write-service deployable does not exist yet. The fake service used in tests implements the ADR 2026-10-27-1 handshake and health endpoints and the endpoint-file publication, and nothing else.
- The JVM fallback requires a Java runtime of the major version spec-kitty-events builds with (25), detected from the environment.
- Idle shutdown policy for the write service (ADR 2026-10-27-1 open question 6) stays undecided. This mission provides an explicit stop and leaves idle exit to the service.

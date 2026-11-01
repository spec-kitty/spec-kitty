# Mission Specification: Name spec-kitty-charter's `service-v*` release line for `charter-service`

**Mission Branch**: `kitty/mission-charter-service-pin-line-01M6BTXZ`
**Created**: 2026-11-01
**Status**: Draft
**Input**: GitHub issue #6909, "Service pins: name spec-kitty-charter's service-v* release line for charter-service"

## Context

Core pins each service it does not build. `spec-kitty-charter` now releases the charter
service from its own repository on its own `service-vX.Y.Z[-pre]` line, matching core's
`_TAG_RE`, with the assets core already expects (spec-kitty-charter ADR-0046, decision 4).
Core still describes that service in spec-kitty-events terms:

- `src/kernel/service_pin.py:70-71` marks the `spec-kitty-charter-service` asset prefix
  "Provisional".
- `src/specify_cli/services/vendor.py` defaults **every** service to
  `https://github.com/spec-kitty/spec-kitty-events`, so the first `charter-service` bump
  would need `--repository`.
- `spec-kitty service vendor --help`, `pins/README.md` and the `kernel.service_pin`
  module docstring name spec-kitty-events as the release home of every service.
- A vendored asset is checked against the release's `SHA256SUMS` only; its build
  provenance is not checked, even though both release workflows attest every asset
  (spec-kitty-charter ADR-0046, decision 6; spec-kitty-events ADR 0003).
- Nothing proves end to end, through the production fetch path and with a fixture pin,
  that the charter service's pinned digest is verified on install.

**Operator guidance (2026-11-01)**: every PR carries `pr:pause-ci` at creation; rebase
only when `mergeable` reports `CONFLICTING`. Never merge, never arm auto-merge, never
push to `main`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bump the charter pin without naming its repository (Priority: P1)

A maintainer runs `spec-kitty service vendor --service charter-service --tag service-v0.1.0`
in a core checkout, with no `--repository`. The written pin names the charter repository,
so the first charter release is pinnable exactly like an events release.

**Why this priority**: without it the first charter-service bump silently targets
spec-kitty-events and refuses, or needs a flag nobody will remember.

**Independent Test**: write no pin, call `vendor_pin(service="charter-service", repository=None)`
against a captured download request, and assert the request's repository is
`https://github.com/spec-kitty/spec-kitty-charter`; repeat for `write-service` and
`read-service` to the events repository.

**Acceptance Scenarios**:

1. **Given** no `charter-service` pin exists, **When** I vendor `charter-service` with no
   `--repository`, **Then** the pin records `https://github.com/spec-kitty/spec-kitty-charter`.
2. **Given** an existing pin whose `repository` is set, **When** I bump it with no
   `--repository`, **Then** the current pin's repository is kept.
3. **Given** any service, **When** I pass `--repository`, **Then** that repository is used.

---

### User Story 2 - Read the owning repository from the pin model and its docs (Priority: P1)

An operator reading `kernel/service_pin.py`, `pins/README.md` or `service vendor --help`
learns that each service's `service-v*` release comes from the service's own repository,
and that the charter service's asset prefix is its recorded name, not a provisional one.

**Why this priority**: the stale wording is what made the charter release look unpinnable.

**Independent Test**: assert the charter prefix equals `spec-kitty-charter-service` in a
three-service table, and assert the `vendor --help` text names `spec-kitty-charter` and no
longer tells the reader that every service defaults to `spec-kitty-events`.

**Acceptance Scenarios**:

1. **Given** the prefix table, **When** I read `DEFAULT_ASSET_PREFIXES`, **Then** the
   charter entry is `spec-kitty-charter-service` with no provisional marker.
2. **Given** `spec-kitty service vendor --help`, **When** I read `--repository` and
   `--tag`, **Then** they say the default is the service's own release repository and
   name spec-kitty-charter as the charter service's.

---

### User Story 3 - A bump verifies build provenance before writing the pin (Priority: P1)

A maintainer bumps a pin from a GitHub release. Before the lockfile is written, core
verifies each downloaded asset's build attestation with
`gh attestation verify <asset> --repo <owner/repo> --signer-workflow <repo>/.github/workflows/service-release.yml --source-ref refs/tags/<tag>`.
A release whose attestation is missing or signed by another workflow or ref refuses, and
the lockfile stays byte-identical.

**Why this priority**: the digest in `SHA256SUMS` is produced by the same run that is
being trusted; the attestation is the independent provenance proof ADR-0046 decision 6
and the events ADR both describe.

**Independent Test**: with a fake `gh` seam, a bump over a `https://github.com/...`
repository calls the verifier once per pinned asset with the signer workflow and tag ref;
a verifier failure raises the stable refusal code and leaves the lockfile unchanged. A
`file://` fixture repository skips the check and reaches no subprocess.

**Acceptance Scenarios**:

1. **Given** a GitHub release with valid attestations, **When** I vendor it, **Then** each
   pinned asset is verified before the pin is written.
2. **Given** an attestation that `gh` rejects, **When** I vendor it, **Then** the bump
   refuses with a stable code and the lockfile is byte-identical.
3. **Given** `gh` is not installed, **When** I vendor a GitHub release, **Then** the bump
   refuses with a code that names the remedy, and `--no-attestation` is documented as the
   explicit escape hatch.
4. **Given** a `file://` fixture release, **When** I vendor it, **Then** no attestation
   command runs and the bump succeeds.

---

### User Story 4 - Installing the charter service verifies its pinned digest (Priority: P2)

With the first fixture pin for `charter-service`, `spec-kitty service fetch --service
charter-service` downloads the pinned native asset, verifies it against the pin's digest,
and caches it; a release whose bytes do not match the pin refuses with
`SERVICE_BINARY_DIGEST_MISMATCH` and caches nothing.

**Why this priority**: it is the install half of the same trust chain, and the issue asks
for it to be proved with a fixture pin rather than assumed.

**Independent Test**: build a `file://` fixture release and pin for `charter-service`,
fetch it through the CLI, and assert the cached copy's digest; then tamper with the
release asset and assert the refusal code on the same fixture.

**Acceptance Scenarios**:

1. **Given** a `charter-service` fixture pin, **When** I fetch it, **Then** the cached
   asset is byte-identical to the release asset and the command exits 0.
2. **Given** the same fixture with tampered bytes, **When** I fetch it, **Then** the
   command refuses with `SERVICE_BINARY_DIGEST_MISMATCH` and caches nothing.

---

### Edge Cases

- The release repository is `file://` (fixtures, offline mirrors): there is no GitHub
  attestation to check; the vendor skips the provenance step and still checks digests.
- The repository is `https://` but not GitHub: no signer workflow can be derived; the
  bump refuses unless the operator passes `--no-attestation`, which is documented as
  "never for a real bump".
- An existing pin's repository is a `file://` mirror; a later bump keeps it and skips the
  provenance step, exactly like a fresh `file://` bump.
- `gh` is installed but unauthenticated, or the release is private to another account:
  the refusal names the remedy without echoing the repository's userinfo or a digest.
- A release asset is added to `SHA256SUMS` but not to the pin (an ignored file): it is not
  verified, because the pin never trusts it.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Per-service default repository | As a maintainer, I want `charter-service` to default to the charter repository and the events services to the events repository so that a first bump needs no `--repository`. | High | Open | [build] | no |
| FR-002 | Recorded asset prefix, no provisional marker | As a maintainer, I want the charter asset prefix recorded as spec-kitty-charter's own name so that nothing reads as pending. | High | Open | [ratchet] | yes — paired with the three-service prefix table that also asserts the two events prefixes on the same fixture |
| FR-003 | Provenance check before a pin is written | As a maintainer, I want each vendored asset's build attestation verified (signer workflow and source ref) before the lockfile is written so that a release from another workflow or tag cannot be pinned. | High | Open | [build] | no |
| FR-004 | Owner named in help and docs | As an operator, I want `service vendor --help`, `pins/README.md` and the pin module docstring to name each service's own release repository so that the charter release line is discoverable. | Medium | Open | [build] | no |
| FR-005 | Install-time digest proof for charter-service | As an operator, I want a fixture pin proving `service fetch` verifies the charter service's digest and refuses tampered bytes so that the install half of the trust chain is tested. | High | Open | [ratchet] | yes — paired with the positive fetch on the same fixture that proves the probe sees a verified asset |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Fixtures stay offline | Vendoring a `file://` repository performs 0 network requests and 0 subprocess invocations, so every existing offline vendor/fetch test stays offline. | Reliability | High | Open |
| NFR-002 | No secrets or digests in refusals | An attestation refusal message contains no 64-hex digest and no URL userinfo; a test asserts both. | Security | High | Open |
| NFR-003 | No new runtime dependency | The provenance check adds 0 Python dependencies; it shells out to `gh` at most once per pinned asset, only from the maintainer-only vendor path, never from fetch, status or start. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Unchanged tag, target and fallback model | `_TAG_RE`, `ServiceTarget`, `service_hosts`, the jar fallback and `CHARTER_SERVICE.launchable` stay unchanged. | Technical | High | Open |
| C-002 | Layer boundary | The kernel keeps no repository table and no `gh` call: `kernel.service_pin` owns the prefix/tag rules, `specify_cli.services` owns the repository defaults and the provenance check. | Technical | High | Open |
| C-003 | The pin stays the trust root | A user fetch/start never calls `gh`; the pinned digest alone decides what runs. Provenance is checked once, when the pin is written. | Technical | High | Open |

### Key Entities

- **Service pin** (`pins/<service>.source.yaml`): service, repository, `service-v*` tag,
  commit, protocol versions, `requires_core`, per-target asset names and digests, extras.
- **Default repositories**: the owning repository for each of the three known services.
- **Build attestation**: the release workflow's provenance statement over each asset in
  `SHA256SUMS`, identified by repository, signer workflow and source tag ref.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A `charter-service` bump with no repository argument writes a pin whose
  repository is `https://github.com/spec-kitty/spec-kitty-charter`; the two events
  services write the events repository. — [build] · no-op passable: no
- **SC-002**: A bump whose attestation `gh` rejects writes no pin (0 bytes changed) and
  exits with a stable refusal code; a bump whose attestation passes writes the pin. — [build] · no-op passable: no
- **SC-003**: `spec-kitty service fetch --service charter-service` on a fixture pin caches
  a digest-verified asset, and the same fixture with tampered bytes refuses with
  `SERVICE_BINARY_DIGEST_MISMATCH` and caches nothing. — [ratchet] · no-op passable: yes — paired positive/negative control on one fixture
- **SC-004**: `service vendor --help` and `pins/README.md` contain 0 statements that every
  service releases from spec-kitty-events, and both name spec-kitty-charter for
  `charter-service`. — [build] · no-op passable: no

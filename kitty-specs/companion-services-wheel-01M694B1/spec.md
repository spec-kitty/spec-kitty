# Mission Specification: Optional companion services wheel

**Mission Branch**: `companion-services-wheel`
**Created**: 2026-10-31
**Status**: Draft
**Input**: Operator ruling 2 of 2026-10-31 (#6117 comment 6544221340), tracked by #6904. The operator accepted all twelve recommendations of `docs/plans/events-domain-move/companion-wheel-research.md` §3 (Decision Moment `01M694BE2Z24AWM044Y2EQT83S`).

## Intent Summary (confirmed)

- **Primary actors:** a developer or team installing Spec Kitty on a machine with no network access at first use, and the maintainer who cuts a CLI release.
- **Trigger:** the user runs one install command that asks for the service binaries along with the CLI.
- **Outcome:** the service binaries the CLI launches are installed with the CLI. The first use needs no download. The main CLI package still ships no binary.
- **Invariant:** a binary is used only when its bytes match the digest pinned by the installed CLI. Installing the companion never weakens that check, and nothing in the companion is rebuilt from source.
- **Boundary:** the events read service never reaches user machines (ADR 2026-10-29-1 D-6). Only the services the CLI launches (the write service and the charter service) are carried.

## Domain Language

| Term | Meaning | Avoid |
|------|---------|-------|
| Companion wheel | The optional `spec-kitty-services` distribution that carries pinned service binaries | "native wheel", "bundle wheel" |
| Install slot | The `spec_kitty.service_binaries` entry-point group that resolution consults after an explicit path and before the cache | "plugin" |
| Pin | A `pins/<service>.source.yaml` lockfile: release tag, commit and per-asset sha256 | "lock", "manifest" (the manifest is the companion's own record of what it carries) |
| Fallback wheel | The binary-free, any-platform companion build that every host can install | "empty wheel" |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Offline-ready install in one command (Priority: P1)

A developer on a supported host (linux x64 or arm64, Apple Silicon macOS, Windows x64) installs the CLI together with the companion in one command. Later, with no network, the CLI starts the write service from the companion's binary.

**Why this priority**: this is the reason the operator asked for the companion.

**Independent Test**: install a companion built from fixture pins and assets, remove network access and the cache, and resolve the write service. It resolves from the install slot, and its digest matches the pin.

**Acceptance Scenarios**:

1. **Given** a companion built for this host and CLI version, and an empty cache, **When** the CLI resolves the write service offline, **Then** it uses the companion's binary, digest-checked, and downloads nothing.
2. **Given** the companion is installed and the cache already holds the pinned build, **When** the CLI resolves, **Then** the companion's binary is still the source (the install slot comes before the cache).
3. **Given** an explicit binary path is also set, **When** the CLI resolves, **Then** the explicit path wins over the companion.

---

### User Story 2 - The companion can never run an unpinned binary (Priority: P1)

**Why this priority**: the companion adds an install-time path for executables, so it must not become a way around the digest pin.

**Independent Test**: plant a companion binary whose bytes differ from the pin and resolve.

**Acceptance Scenarios**:

1. **Given** a companion for the CLI's own version whose binary does not match the pin, **When** the CLI resolves, **Then** it refuses with `SERVICE_BINARY_DIGEST_MISMATCH` and does not fall through to the cache, even when the cache holds a good copy.
2. **Given** a companion built for a *different* CLI version, **When** the CLI resolves, **Then** the companion offers nothing, and resolution falls through to the cache or the fetch as if the companion were absent.

---

### User Story 3 - Every host can install the extra (Priority: P2)

A developer on an unsupported host (Intel macOS, musl Linux, Linux with a glibc older than the floor, Windows on ARM) runs the same install command.

**Why this priority**: an opt-in extra must never break the CLI install itself.

**Independent Test**: the fallback wheel installs on any platform and its providers offer no binary.

**Acceptance Scenarios**:

1. **Given** an unsupported host, **When** the user installs the CLI with the services extra, **Then** the install succeeds through the fallback wheel, and the CLI behaves exactly as without the companion (it fetches on first use).

---

### User Story 4 - The maintainer releases the companion with the CLI (Priority: P1)

The maintainer pushes a release tag. The release workflow builds one companion wheel per native target, plus the fallback wheel, from the release commit's pins. It verifies every asset against its pinned digest and every wheel against the size cap, and publishes the companion before the CLI.

**Why this priority**: without the pipeline, the companion never reaches users.

**Independent Test**: run the build script against fixture pins and a fixture release, then inspect the wheels it writes.

**Acceptance Scenarios**:

1. **Given** fixture pins for the write and charter services with all four native targets, **When** the build runs, **Then** it writes four platform wheels and one fallback wheel. Each platform wheel holds exactly the pinned assets of its target, byte-identical, and an embedded manifest that equals the pins.
2. **Given** a fixture asset whose bytes do not match its pin, **When** the build runs, **Then** it fails, naming the asset, and writes no wheel.
3. **Given** no pin exists (today), **When** the build runs, **Then** it writes only the fallback wheel.
4. **Given** a pin for the read service, **When** the build runs, **Then** the read service is not packed.
5. **Given** a wheel would exceed 95 MB, **When** the build runs, **Then** it fails. Above 60 MB it warns.

### Edge Cases

- A pin has no native build for a target but has a jar: that target's platform wheel carries nothing for that service (the jar stays on the fetch path), and its provider offers nothing.
- A pin lists a native target for one service but not the other: each platform wheel carries only what is pinned for its target.
- The companion's provider is imported on a host it was not built for (forced install): the binary for that host is absent, so the provider offers nothing.
- The main CLI wheel or sdist picks up a companion file or a binary by accident: the packaging guard fails.
- A cold cache in the release job: the services sync step fetches before it verifies, so it does not fail spuriously.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | ADR amendment | As a maintainer, I want ADR 2026-10-29-1 D-4 amended to record the companion wheel's name, version lock, tags, build-from-pinned-assets rule, size limits, resolution order and offline install, so that the decision has one recorded authority. | High | Open | [build] | no |
| FR-002 | Companion package source | As a maintainer, I want a `spec-kitty-services` package source whose providers register the `write-service` and `charter-service` entry points and return the bundled host binary, or nothing, so that the CLI's install slot can find it. | High | Open | [build] | no |
| FR-003 | Version-skew guard | As a user, I want the companion's providers to offer nothing when the installed CLI version differs from the version the companion was built for, so that a skew degrades to the fetch instead of a refusal. | High | Open | [build] | no |
| FR-004 | Build from pinned assets | As a maintainer, I want a build script that fetches every native target of every user-facing service through the kernel fetch owner, verifies each digest, and writes one wheel per target plus a fallback wheel, never rebuilding a binary, so that the companion holds exactly the pinned bytes. | High | Open | [build] | no |
| FR-005 | Read service excluded | As the operator, I want the build to skip the read service whatever pins exist, so that it never ships to users. | High | Open | [build] | no |
| FR-006 | Honest platform tags | As a user, I want each platform wheel tagged for its target (`manylinux_2_39_x86_64`, `manylinux_2_39_aarch64`, `macosx_11_0_arm64`, `win_amd64`), with the Linux glibc floor as an explicit build input, so that pip installs it only where it can run. | High | Open | [build] | no |
| FR-007 | Size gate | As a maintainer, I want the build to fail when a wheel exceeds 95 MB and warn above 60 MB, so that a release never hits PyPI's per-file cap at upload time. | Medium | Open | [build] | no |
| FR-008 | Services extra | As a user, I want `pip install "spec-kitty-cli[services]"` to install the companion of exactly the CLI's version, so that one command gives an offline-ready install. | High | Open | [build] | no |
| FR-009 | Release pipeline | As a maintainer, I want the release workflow to build and verify the companion wheels in their own job and directory, and to publish them from their own environment before the CLI, so that the CLI's exact extra always resolves. | High | Open | [build] | no |
| FR-010 | Packaging guard | As a maintainer, I want a guard that fails when the main wheel or sdist carries a binary or a companion file, and when a companion wheel's contents differ from the pinned digests, so that both invariants are enforced. | High | Open | [build] | no |
| FR-011 | Resolution preference pinned | As a maintainer, I want tests that pin the install slot's place in resolution (after explicit, before a warm cache, jar support, wrong digest refuses even with a warm cache), so that later changes cannot silently reorder it. | High | Open | [ratchet] | no — each test pairs the companion case with a positive control on the same fixture |
| FR-012 | Release checks and checklist | As a maintainer, I want the release workflow to fetch and verify the host's pinned services next to the packs check, and the release checklist to list the service and companion steps, so that a drifted pin cannot ship. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Reproducible wheels | Building twice from the same pins and assets yields byte-identical wheels (fixed timestamps, sorted members). | Reliability | High | Open |
| NFR-002 | Fast tests | The companion build and guard tests run in under 10 s in total on fixture assets, with no network access. | Performance | Medium | Open |
| NFR-003 | Digest integrity | 100% of the binaries in a companion wheel match a pinned sha256. Zero binaries in the main wheel and sdist. | Security | High | Open |
| NFR-004 | Code quality | The new code passes `ruff check`, `ruff format --check` and `mypy --strict` with zero issues and no new suppressions. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Main wheel stays pure | `spec-kitty-cli` stays `py3-none-any` and ships pins only (ADR 2026-10-29-1 D-4). | Technical | High | Open |
| C-002 | No frozen path touched | No change under the D-9 frozen set (`services/`, the moving `contracts/` paths, `docs/architecture/event-ledger-writers-and-readers.md`). | Technical | High | Open |
| C-003 | One fetch owner | Assets are fetched only through `kernel.service_artifacts`; no new HTTP client. | Technical | High | Open |
| C-004 | No new build dependency | The companion is assembled with the Python standard library. | Technical | Medium | Open |
| C-005 | Companion source outside `src/` | The companion's Python source lives in `packages/spec-kitty-services/` and is excluded from the CLI sdist. | Technical | High | Open |
| C-006 | Out of scope | The core cut-over PR, the #6195 EventBridge binding and install docs. | Business | High | Open |
| C-007 | Fixture pins | Real pins may not exist yet; tests use fixture pins and assets. | Technical | Medium | Open |

### Key Entities

- **Companion manifest**: the companion's record of what it carries: CLI version, and per service its tag, target, asset name and sha256. It must equal the release commit's pins for the carried targets.
- **Companion wheel**: one per native target plus the fallback. Same version as the CLI.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a supported host with the companion installed and no network, the write service resolves on the first try with zero downloads. — [build] · no-op passable: no
- **SC-002**: 0 binaries ship in the main CLI wheel and sdist, and 100% of the binaries in companion wheels match their pins. — [build] · no-op passable: no
- **SC-003**: The services extra installs successfully on 100% of hosts, the unsupported ones included (through the fallback wheel). — [build] · no-op passable: no
- **SC-004**: A release with a drifted or tampered asset fails before anything is published. — [build] · no-op passable: no

## Assumptions

- Binary sizes are unmeasured. The 60–85 MB per-wheel estimate (research note §2) is checked by the size gate at build time, not assumed.
- The operator registers the PyPI pending Trusted Publisher for `spec-kitty-services` and creates the GitHub environment `pypi-services` before the first real publish. These are PR prerequisites, not mission work.
- The events native builds run on `ubuntu-24.04`, so the Linux glibc floor is 2.39 until the events side lowers it.

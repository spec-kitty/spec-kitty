# Mission Specification: The companion wheel's platform floor comes from the binary

**Mission Branch**: `issue-6948-companion-wheel-platform-floor`
**Created**: 2026-11-01
**Status**: Draft
**Input**: Issue #6948, "Companion wheel: derive the platform floor (manylinux glibc, macOS minos) from the binary at build time" — follow-up to #6904 (ADR 2026-10-29-1, Amendment 2026-10-31). Operator guidance: the PR is opened by this run and the operator merges; the change closes the issue's failure mode, adds fixtures rather than real binaries (the pins are still empty), and keeps the released tag stable.

## Intent Summary (confirmed)

- **Primary actors:** the maintainer who cuts a CLI release, and the developer who installs `spec-kitty-cli[services]` on their host.
- **Trigger:** the release workflow builds the companion platform wheels from the release commit's pinned service binaries.
- **Outcome:** the OS minimum each wheel's tag claims is read from the binaries that wheel carries, and the build refuses to publish a wheel whose binaries need a newer OS than the tag says.
- **Invariant:** every byte a wheel carries still matches its pinned SHA-256; this Mission only adds a claim check on top of that, and it never rebuilds a binary.
- **Boundary:** build-time only. Nothing changes in the CLI's runtime resolution order, in the pins' format, or in the contents of the wheels.

## Domain Language

| Term | Meaning | Avoid |
|------|---------|-------|
| Platform floor | The oldest OS a binary needs: the glibc `major.minor` for Linux, the macOS `minos` for Apple Silicon | "minimum version", "ABI level" |
| Declared floor | The floor the release build is told to claim (`--glibc-floor`, `--macos-floor`); it becomes the wheel tag | "configured floor", "default floor" |
| Measured floor | The floor read out of a pinned binary's own headers | "detected floor", "actual floor" |
| Platform tag | The wheel's `manylinux_2_39_x86_64` / `macosx_11_0_arm64` compatibility tag (PEP 425/600) | "wheel name", "platform string" |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The release never ships a wheel that claims an older Linux than its binary needs (Priority: P1)

A maintainer cuts a release. One of the pinned Linux binaries was built against a newer glibc than the floor the release workflow declares. The build stops instead of publishing a `manylinux_2_39` wheel, and the message says which binary needs which glibc and what to change.

**Why this priority**: this is the failure the issue names — pip installs the wheel on a host the tag said was supported, the digest check passes, and the binary dies at exec (`SERVICE_UNHEALTHY`) with no fallback to the first-run fetch.

**Independent Test**: build the wheels from fixture pins whose linux-x64 asset needs glibc 2.42 while the build declares 2.39; the build exits 1 with `SERVICE_PLATFORM_FLOOR_EXCEEDED`, names the asset and both floors, and writes no wheel. The same fixture with a 2.39 binary builds exactly as it does today.

**Acceptance Scenarios**:

1. **Given** a pinned linux binary whose ELF version needs include `GLIBC_2.42`, and a declared floor of `2_39`, **When** the build runs, **Then** it exits 1 with `SERVICE_PLATFORM_FLOOR_EXCEEDED`, names the asset, the measured floor and the declared floor, and writes no wheel.
2. **Given** a consolidated wheel set (write service and charter service on linux-x64) where only the charter service needs the newer glibc, **When** the build runs, **Then** the refusal names the charter service's asset — the wheel's floor is the maximum over the binaries it carries.
3. **Given** binaries whose measured floor is at or below the declared floor, **When** the build runs, **Then** it succeeds and the wheel bytes are identical to today's for the same inputs (same tags, same reproducible bytes).

### User Story 2 - The release never ships a wheel that claims an older macOS than its binary needs (Priority: P1)

A maintainer's release runner moved to a newer macOS, so the pinned Apple Silicon binary records a newer `minos`. The build refuses the `macosx_11_0_arm64` wheel instead of shipping one that crashes on macOS 11.

**Why this priority**: the macOS floor is the one that is only a constant in the wheel writer today, with no build input and no check, so it is the most likely to go stale.

**Independent Test**: build from a fixture whose macos-arm64 asset records `minos 12.0` while the build declares `11_0`; the build refuses with the same stable code and names the measured floor. A `minos 11.0` (or older) asset builds the `macosx_11_0_arm64` wheel as before.

**Acceptance Scenarios**:

1. **Given** a pinned macOS binary whose `LC_BUILD_VERSION` records `minos 12.0`, and a declared floor of `11_0`, **When** the build runs, **Then** it exits 1 with `SERVICE_PLATFORM_FLOOR_EXCEEDED` and names the measured floor.
2. **Given** a maintainer who raises the declared floor to `--macos-floor 12_0`, **When** the build runs on the same pins, **Then** it succeeds and tags the wheel `macosx_12_0_arm64`.

### User Story 3 - A floor nobody could read is never assumed (Priority: P2)

A pinned asset is not the native binary its pin claims to carry (a script, a 32-bit build, a truncated download, a universal Mach-O). The build refuses it instead of silently keeping the declared floor.

**Why this priority**: the defect being fixed is an unchecked claim. Falling back to the declared floor when the binary cannot be read would keep the same hole, only narrower. P2 because it is a guard on the guard: no release is blocked today.

**Independent Test**: pin an asset that is not a readable native binary for a floored target; the build refuses with `SERVICE_PLATFORM_FLOOR_UNREADABLE` and writes no wheel. A Windows asset is not measured at all — `win_amd64` states no OS minimum.

**Acceptance Scenarios**:

1. **Given** a linux-x64 asset that is not an ELF executable, **When** the build runs, **Then** it exits 1 with `SERVICE_PLATFORM_FLOOR_UNREADABLE` and names the asset and the reason.
2. **Given** a windows-x64 asset of any shape, **When** the build runs, **Then** the floor check does not apply to it and the wheel is built as before.
3. **Given** a built wheel directory whose tag claims a floor below what its bundled binaries need, **When** `--verify` runs, **Then** it reports the wheel and exits 1.

### Edge Cases

- A wheel carries two binaries with different floors → the higher one decides; the refusal names the binary that sets it.
- An ELF with no `GLIBC_*` version needs (statically linked) → no measured floor, so the declared floor stands and nothing is refused.
- A Mach-O with only the deprecated `LC_VERSION_MIN_MACOSX` command → its version is the floor.
- A truncated or malformed header, a 32-bit ELF, a big-endian ELF, or a universal (fat) Mach-O → refused as unreadable, with the reason in the message.
- A declared floor that is not `<major>_<minor>` → refused up front, whether or not that platform is pinned (as `--glibc-floor` already is).
- A wheel whose binaries cannot be read but which passed the digest check → the digest check still decides first; the floor check only adds a refusal.
- `--verify` on a wheel set with no pinned target at all (fallback wheel only) → unchanged.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Linux floor is read from the binary | As a release maintainer, I want the Linux floor read from each pinned binary's ELF version needs so that no tag rests on a constant nobody checked. | High | Open | [build] | no |
| FR-002 | macOS floor is read from the binary | As a release maintainer, I want the macOS floor read from each pinned binary's Mach-O build-version command so that a newer runner cannot ship a stale tag. | High | Open | [build] | no |
| FR-003 | A wheel's floor is the maximum over its binaries | As a release maintainer, I want the wheel's measured floor to be the highest of the binaries it carries, so that a wheel is safe for every binary in it. | High | Open | [build] | no |
| FR-004 | Refuse a floor above the declared one | As a release maintainer, I want the build to fail with a stable code naming the asset, the measured floor and the remedy when a binary needs more than the declared floor, so that no under-claiming wheel is ever written. | High | Open | [build] | no |
| FR-005 | Refuse a floor that cannot be read | As a release maintainer, I want an asset whose floor cannot be read on a floored target to be refused, so that the check cannot silently pass. | Medium | Open | [build] | no |
| FR-006 | Windows is not measured | As a release maintainer, I want the Windows wheel untouched, because `win_amd64` states no OS minimum. | Medium | Open | [build] | no |
| FR-007 | The macOS floor is a build input | As a release maintainer, I want to declare the macOS floor on the command line beside the glibc one, with today's `11_0` as the default, so that raising it is a reviewed one-line change. | Medium | Open | [build] | no |
| FR-008 | Verify re-measures the bundled bytes | As a release maintainer, I want `--verify` to re-measure the binaries inside each wheel so that a wheel built with a too-low declared floor cannot pass verification. | High | Open | [build] | no |
| FR-009 | Both floors are validated up front | As a release maintainer, I want a malformed declared floor refused before any wheel is built, whether or not that platform is pinned. | Low | Open | [ratchet] | yes — the glibc half already behaves this way; the macOS half is the positive control on the same fixture |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Status |
|----|-------|-------------|----------|--------|
| NFR-001 | No new dependency | The reader and the build script use only the Python standard library plus the `kernel` and companion-writer modules the build already imports; `pyproject.toml` and `uv.lock` gain no dependency. | Maintainability | Open |
| NFR-002 | No new network or disk contact | Floors are read from the asset bytes the build already fetched and digest-verified; the number of asset fetches, and the cache layout, are unchanged. | Security | Open |
| NFR-003 | Header-only reads | Reading a floor parses headers and string tables only, never the whole asset: a 100 MB binary adds under 100 ms of build time per target on the release runner. | Performance | Open |
| NFR-004 | Reproducible output preserved | For identical inputs the built wheel names and bytes are unchanged: a wheel whose binaries are at or below the declared floor is byte-identical to the same build before this Mission. | Reliability | Open |

### Constraints

| ID | Title | Constraint | Category | Status |
|----|-------|------------|----------|--------|
| C-001 | The published tag stays the declared floor | The measurement guards the tag, it does not move it: this Mission ships no wheel under a different tag than today (`manylinux_2_39_*`, `macosx_11_0_arm64`, `win_amd64`). Moving a floor is a separate, reviewed release-contract change with its own changelog entry (decision `01M6BV2A16NMD5QA4VZ8B814HW`). | Technical | Open |
| C-002 | Wheel contents do not change | No file is added to or removed from the wheels or the sdist; the build-time reader is not shipped, and the packaging invariants the companion already has continue to hold. | Technical | Open |
| C-003 | Existing codes and contract kept | `SERVICE_*`/`COMPANION_*` codes stay stable, exit 1, stderr output, and the "no wheel written on failure" behaviour are unchanged; the new refusals join that set. | Technical | Open |
| C-004 | Pins are the only source | The check reads the pinned asset bytes only; it never rebuilds, re-signs or patches a binary, and never consults the build host's own glibc or macOS version. | Regulatory | Open |

### Key Entities *(include if the mission involves data)*

- **Platform floor**: a `major_minor` string (`2_39`, `11_0`) plus the kind it belongs to (glibc or macOS). Declared per platform by the build; measured per binary from the binary's own headers.
- **Wheel floor**: the maximum measured floor across the binaries one platform wheel carries, with the asset that sets it.
- **Pinned asset**: the released service binary a pin names by file name and SHA-256; the bytes the build already fetches and verifies.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A pinned binary needing a newer floor than the declared one fails the build with the stable refusal code and produces zero wheels, for both Linux and macOS fixtures — [build] · no-op passable: no
- **SC-002**: For fixtures at or below the declared floor, the wheel names and bytes are identical to the pre-change build (5 wheels: 4 platform + 1 fallback), and the reproducibility test still passes — [ratchet] · no-op passable: no
- **SC-003**: `--verify` refuses a wheel directory whose wheel tag claims a floor below what its bundled binaries need — [build] · no-op passable: no
- **SC-004**: An unreadable asset on a floored target is refused with its own stable code, while a Windows asset of the same shape builds normally — [build] · no-op passable: no
- **SC-005**: Both floors are documented build inputs: `--help` lists the macOS floor, the release workflow's comment and the changelog entry state that the tag is checked against the binaries — [build] · no-op passable: yes — paired with the negative control that a malformed macOS floor still refuses the build

## Assumptions

- The `spec-kitty-events` native builders keep producing thin, 64-bit, little-endian ELF (Linux) and thin arm64 Mach-O (macOS) images. A universal Mach-O is refused rather than guessed (see `research.md`, open question 1).
- `pins/` stays empty for this Mission, so the guard is proven on fixtures; the first real `service-v*` pin exercises it without a code change.
- The declared Linux floor stays `2_39` and the declared macOS floor stays `11_0` for the 4.0.0rc8 cycle; this Mission changes neither release claim.
- Python 3.11+ only (the same floor every other build script has).

## Out of Scope

- Lowering the Linux floor (static linking, an older builder) or the macOS floor: an events-side change, tracked by its own follow-up.
- Any runtime change in the CLI's resolution order, download, digest check or launcher behaviour.
- Reading floors for targets that state none (Windows), or for architectures no companion target covers.
- Amending ADR 2026-10-29-1: the decision this Mission records is a build-input detail of the Amendment it already carries.

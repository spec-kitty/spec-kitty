# REASONS Canvas — Companion wheel platform floor

> Mission: `companion-wheel-platform-floor-01M6BV24`
> Source: [#6948](https://github.com/spec-kitty/spec-kitty/issues/6948). [spec.md](spec.md) is authoritative; this canvas is non-governing and advisory.

## Requirements

- **Problem.** A companion platform wheel's tag states an OS minimum, but nothing read that minimum from the binary. Linux came from `--glibc-floor 2_39` in `release.yml`; macOS from the constant `macosx_11_0_arm64` in `wheel.py`. A binary built against something newer would still be tagged and installed on an older host, pass the digest check, and die at exec (`SERVICE_UNHEALTHY`) with no fallback.
- **Decision** (`01M6BV2A16NMD5QA4VZ8B814HW`). The tag keeps the declared floor; the build measures each pinned binary and refuses with `SERVICE_PLATFORM_FLOOR_EXCEEDED` when a binary needs more. Deriving the tag would move a release contract inside a build and silently narrow the hosts that can install the companion.
- **Acceptance.** Spec FR-001…FR-009; one test family per refusal and per platform; SC-001…SC-005. Proven through the pre-existing entry points (`scripts/build_services_wheel.py --out` and `--verify`) on fixture ELF and Mach-O headers, red-first.
- **Definition of done.** A linux or macOS asset above the declared floor fails the build and writes no wheel (SC-001); fixtures at or below it build byte-identical wheels (SC-002); `--verify` fails a wheel whose tag understates its bundled binaries (SC-003); an unreadable floored asset is refused while Windows is untouched (SC-004); `--help`, `release.yml` and the changelog name the floor as a checked build input (SC-005).

## Entities

- **Platform floor** — `major_minor` plus kind (glibc or macOS). Declared by the build; measured from a binary's headers.
- **Wheel floor** — the maximum measured floor over the binaries a wheel carries, with the asset that sets it.
- **Pinned asset** — the released service binary a pin names by file name and SHA-256; the bytes the build already fetches and verifies.

## Approach

- Two new readers, standard library only: ELF `PT_DYNAMIC` → `DT_VERNEED` → `Elf64_Vernaux` names (`GLIBC_x.y`), and Mach-O load commands (`LC_BUILD_VERSION` `minos`, falling back to `LC_VERSION_MIN_MACOSX`). Section headers are not required, so a stripped GraalVM image works.
- One-sided check: measured above declared refuses; measured at or below leaves the tag and the bytes alone.
- The reader is a release-tooling module under `scripts/`, not `src/kernel` (a module only `scripts/` imports fails the no-dead-modules gate) and not the companion package (which is copied into every wheel).
- Unreadable is a refusal, not a fallback: the defect being fixed is an unchecked claim.

## Structure

- `scripts/service_platform.py` — new: the target→floor-kind map, the ELF and Mach-O readers, the per-wheel maximum, the comparison.
- `scripts/build_services_wheel.py` — wire the measurement into `build` and `verify`; `--macos-floor`; the new codes in the refusal set.
- `packages/spec-kitty-services/spec_kitty_services/wheel.py` — `macos_floor` parameter, `DEFAULT_MACOS_FLOOR`, both floors validated.
- `.github/workflows/release.yml` — the floor comment tells the truth about the check.
- Tests: the existing builder test file (end to end) plus a new fixture-header module for the reader.
- Frozen and untouched: `services/`, `contracts/` (ADR `2026-10-29-1` D-9), the pins' format, the wheels' contents.

## Operations

- Research → specify → plan → tasks → red-first implement/review → accept → local consolidation → independent aggregate review → changelog/docs → draft PR → CI green → ready for review. The operator merges.

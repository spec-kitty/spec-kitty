# Implementation Plan: The companion wheel's platform floor comes from the binary

**Branch**: `issue-6948-companion-wheel-platform-floor` | **Date**: 2026-11-01 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/companion-wheel-platform-floor-01M6BV24/spec.md`

## Summary

`scripts/build_services_wheel.py` builds one platform wheel per native target and a binary-free
fallback from the release commit's pins. Each platform wheel's compatibility tag states an OS
minimum (`manylinux_2_39_x86_64`, `macosx_11_0_arm64`, `win_amd64`), but the value came from a
constant and was never checked against the binary it describes. This plan makes the build read
that minimum out of every pinned binary it bundles — the highest `GLIBC_x.y` version need in the
ELF, and the Mach-O `LC_BUILD_VERSION` `minos` — and refuse to write a wheel when a binary needs a
newer OS than the tag would claim. `--verify` repeats the measurement on the bundled bytes so a
wheel built with too low a declared floor cannot pass verification. The tag itself does not move:
the declared floor stays the release contract (decision `01M6BV2A16NMD5QA4VZ8B814HW`).

## Technical Context

**Language/Version**: Python 3.11+ (the repository floor), standard library only for the new reader
**Primary Dependencies**: none added; the build script keeps importing `kernel.service_pin`,
`kernel.service_artifacts` and the companion's own `wheel.py` (loaded by path)
**Storage**: the shared service-asset cache (`~/.cache/spec-kitty/services`, or
`SPEC_KITTY_SERVICE_ASSET_DIR`) — read-only here; pin lockfiles under `pins/` — read-only here
**Testing**: pytest; the pre-existing entry point is `scripts/build_services_wheel.py` loaded by
file path (`tests/cross_cutting/packaging/test_companion_services_wheel.py`), on fixtures that
never touch the network
**Target Platform**: the release runner (ubuntu-24.04) builds the wheels; the wheels target
linux x86_64/aarch64, Apple Silicon macOS and Windows x64
**Project Type**: single project with an in-tree companion workspace member
**Performance Goals**: the floor read is header-only; under 100 ms added per target (NFR-003)
**Constraints**: no new dependency, no new fetch, no change to wheel contents or to the published
tags in this cycle, reproducible bytes for unchanged inputs
**Scale/Scope**: one new ~200-line tooling module, one build script, one writer function, one
workflow comment, one changelog fragment, and the tests that prove them

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Note |
|------|--------|------|
| Single canonical authority | Pass | The floor kind per target gets one owner (the new module); `wheel.py` keeps the only tag authority; no second floor table. |
| Architectural alignment | Pass | Release tooling stays under `scripts/` beside the build script; nothing is added to `src/` (no-dead-modules gate) or to the shipped companion package (packaging invariants). |
| ATDD-first / red-first | Pass | Each refusal is proven through `build`/`verify` first, on a fixture that fails today (the build accepts it). |
| Terminology canon | Pass | "Platform floor", "declared floor", "measured floor" as the spec's Domain Language defines them; no "feature" wording. |
| No full heavy suites in mission | Pass | Targeted files only: the packaging test modules and the release-tooling tests; CI owns the sweeps. |
| Frozen paths (ADR 2026-10-29-1 D-9) | Pass | `services/`, `contracts/` and the frozen docs page are untouched. |
| Smallest viable diff | Pass | Two touched source files plus a new tooling module; fixtures change only where they must be real native headers. |
| Gate non-vacuity (Standing Order #5) | Pass | Every new refusal has a same-fixture positive control (the same fixtures build and verify green), and both floors carry a malformed-input case. |

Re-checked after Phase 1: no new gap. The design adds no allowlist, no baseline entry, and no
skip; the only new refusal codes join the existing `SERVICE_*` set.

## Project Structure

### Documentation (this mission)

```
kitty-specs/companion-wheel-platform-floor-01M6BV24/
├── plan.md                # This file
├── research.md            # Discovery + Phase 0 findings and decisions
├── data-model.md          # Phase 1: floors, wheel floor, pinned asset
├── quickstart.md          # Phase 1: how to run and read the guard
├── reasons-canvas.md      # SPDD canvas (advisory)
├── checklists/            # Spec quality checklist
├── tasks.md               # Phase 2 output (`/spec-kitty.tasks`)
└── tasks/                 # Phase 2 work-package prompts
```

No `contracts/` directory: this Mission introduces no interface a consumer or another repository
speaks to. The refusal codes are an extension of an existing internal set, documented in the
script's docstring and the changelog, not a contract artifact.

### Source Code (repository root)

```
scripts/
├── build_services_wheel.py          # build/verify entry point: measure, compare, refuse
└── service_platform.py              # NEW: floor kind per target; ELF and Mach-O floor readers

packages/spec-kitty-services/spec_kitty_services/
└── wheel.py                         # platform_tag(..., macos_floor=), DEFAULT_MACOS_FLOOR

.github/workflows/release.yml        # the floor comment states the check (one comment)

tests/cross_cutting/packaging/
├── test_companion_services_wheel.py # end-to-end build/verify refusals and positive controls
└── test_service_platform.py         # NEW: reader unit tests on synthetic ELF/Mach-O headers

tests/kernel/
└── service_release_fixture.py       # native fixture bytes per target (ELF / Mach-O / PE)

docs/changelog/unreleased/
└── <id>.fixed.md                    # the user-facing entry
```

**Structure Decision**: the build script is release tooling, so its helper module lives in
`scripts/` (see `research.md` D6). `wheel.py` is the single authority for tag templates, so the
macOS floor becomes a parameter there rather than a second table in the build script. Tests stay
next to the existing companion-wheel tests, and the fixture builder they already share learns to
emit real native headers.

## Complexity Tracking

*No charter violations; nothing to justify.*

## Implementation Concern Map

### IC-01 — Read a floor out of a native binary

- **Purpose**: One pure, standard-library reader that answers "what OS floor does this binary need" for the targets whose tag states one, and refuses to guess when it cannot tell.
- **Relevant requirements**: FR-001, FR-002, FR-005, FR-006, NFR-001, NFR-003, C-004
- **Affected surfaces**: `scripts/service_platform.py` (new), `tests/cross_cutting/packaging/test_service_platform.py` (new), `tests/kernel/service_release_fixture.py` (fixture headers)
- **Sequencing/depends-on**: none
- **Risks**: ELF must work on a stripped GraalVM image (program headers only, no section headers); Mach-O must handle both build-version commands; every malformed shape must fail closed with a reason, not an exception trace.

### IC-02 — Guard the tag at build and verify time

- **Purpose**: Use the reader to refuse a wheel whose binaries need more than the declared floor, name the asset and the remedy, and repeat the check in `--verify` on the bundled bytes; make the macOS floor a build input.
- **Relevant requirements**: FR-003, FR-004, FR-007, FR-008, FR-009, NFR-002, NFR-004, C-001, C-002, C-003
- **Affected surfaces**: `scripts/build_services_wheel.py`, `packages/spec-kitty-services/spec_kitty_services/wheel.py`, `.github/workflows/release.yml`, `tests/cross_cutting/packaging/test_companion_services_wheel.py`, `tests/cross_cutting/packaging/test_companion_package.py` (tag expectations)
- **Sequencing/depends-on**: IC-01
- **Risks**: the per-wheel maximum must be the maximum over *the binaries that wheel carries* (not over all pins); the refusal must happen before any wheel is written into `--out`; a wheel built today must rebuild byte-identically (same declared floor → same tag → same bytes).

### IC-03 — State the new rule where a maintainer will look

- **Purpose**: The changelog fragment and the `--help`/workflow wording say the tag is checked against the binaries, so the next person who changes a floor knows it is a reviewed release-contract change.
- **Relevant requirements**: SC-005
- **Affected surfaces**: `docs/changelog/unreleased/<id>.fixed.md`, `scripts/build_services_wheel.py` docstring and `--help`, `.github/workflows/release.yml` comment
- **Sequencing/depends-on**: IC-02 (it documents the final wording)
- **Risks**: changelog style gate (bold impact-first lead, `(#issue)`, under 1,200 characters, US spelling); the fragment name follows the PR number once the PR exists.

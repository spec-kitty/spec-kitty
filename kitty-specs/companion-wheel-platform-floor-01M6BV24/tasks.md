# Tasks: The companion wheel's platform floor comes from the binary

**Mission**: `companion-wheel-platform-floor-01M6BV24` · **Topology**: `lanes` · **Branch**: `issue-6948-companion-wheel-platform-floor` (planning base and merge target)
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), [quickstart.md](quickstart.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red tests: native fixture headers (ELF / Mach-O / PE) in the shared release fixture, and the reader's happy paths on them | WP01 | |
| T002 | `scripts/service_platform.py`: target → floor kind, and the ELF version-need reader | WP01 | |
| T003 | `scripts/service_platform.py`: the Mach-O `LC_BUILD_VERSION` / `LC_VERSION_MIN_MACOSX` reader | WP01 | [P] |
| T004 | `scripts/service_platform.py`: malformed-header refusals, per-wheel maximum, numeric comparison | WP01 | |
| T005 | Red end-to-end tests through `build` / `verify`: floor above the declared one, unreadable asset, Windows untouched, wheel whose tag understates | WP02 | |
| T006 | `scripts/build_services_wheel.py`: measure in `build`, new refusal codes, docstring and `--help` | WP02 | |
| T007 | `packages/spec-kitty-services/spec_kitty_services/wheel.py`: `macos_floor` parameter and `DEFAULT_MACOS_FLOOR`; both floors validated | WP02 | |
| T008 | `scripts/build_services_wheel.py`: `--verify` re-measures the bundled bytes | WP02 | |
| T009 | `release.yml` floor comment, changelog fragment, and the existing tag expectations the change touches | WP02 | [P] |

## Phase 1 — The reader

### WP01 — Read a platform floor out of an ELF or Mach-O binary ([prompt](tasks/WP01-platform-floor-reader.md))

- **Goal**: one standard-library module that answers "what OS floor does this binary need" for linux-x64, linux-arm64 and macos-arm64, and refuses to guess. **Priority**: P1. **Independent test**: `tests/cross_cutting/packaging/test_service_platform.py` runs alone and proves both happy paths and every refusal against synthetic headers.
- **Subtasks**:

T001 Red tests: fixture native headers and the reader's happy paths (WP01)
T002 Target → floor kind, ELF version-need reader (WP01)
T003 Mach-O build-version reader (WP01)
T004 Malformed-header refusals, per-wheel maximum, numeric comparison (WP01)

- **Dependencies**: none. **Risks**: ELF must work with no section headers (stripped GraalVM image); every malformed shape must be a named refusal, never a `struct.error` or an `IndexError`.

## Phase 2 — The guard

### WP02 — Refuse a wheel whose tag understates its binaries ([prompt](tasks/WP02-build-guard.md))

- **Goal**: the build and `--verify` use the reader to refuse an under-claiming wheel, naming the asset and the remedy; the macOS floor becomes a build input; the release workflow, help text and changelog say so. **Priority**: P1. **Independent test**: `tests/cross_cutting/packaging/test_companion_services_wheel.py` — a fixture that needs more than the declared floor exits 1 with the new code and writes no wheel, while the same fixtures at or below the floor still build byte-identically.
- **Subtasks**:

T005 Red end-to-end tests through `build` and `verify` (WP02)
T006 `build`: measure, compare, refuse; `--macos-floor`; docstring and help (WP02)
T007 Companion writer: `macos_floor` parameter (WP02)
T008 `--verify` re-measures the bundled bytes (WP02)
T009 Workflow comment, changelog fragment, touched expectations (WP02)

- **Dependencies**: WP01. **Risks**: the per-wheel maximum must not leak across targets; no wheel may be written before a refusal; existing wheel bytes and names must not change for the current declared floors.

## Coverage

| Requirement | Work package |
|-------------|--------------|
| FR-001, FR-002, FR-005, FR-006 | WP01 |
| FR-003, FR-004, FR-007, FR-008, FR-009 | WP02 |
| NFR-001, NFR-003, NFR-004, C-002, C-004 | WP01 |
| NFR-002, C-001, C-003 | WP02 |
| SC-001, SC-002, SC-003, SC-004, SC-005 | WP02 |

## Delivery order

WP01 lands the reader with its own tests; WP02 wires it into the two entry points and proves the
refusals end to end. WP02 depends on WP01, so the mission runs as one lane, in that order.

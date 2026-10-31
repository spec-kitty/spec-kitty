# Tasks: Optional companion services wheel

**Mission**: `companion-services-wheel-01M694B1` · **Topology**: `single_branch` · **Branch**: `companion-services-wheel` (planning base and merge target)
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | ADR 2026-10-29-1 Amendment 2026-10-31 (companion wheel, 12 rulings + workspace member) | WP01 | |
| T002 | CLAUDE.md clarification: a first-party uv workspace member is allowed | WP01 | [P] |
| T003 | Plan §3.4 status line points at the amendment | WP01 | [P] |
| T004 | Red tests: providers (version skew, host, missing file, happy path), wheel writer determinism + RECORD | WP02 | |
| T005 | `spec_kitty_services/wheel.py`: deterministic stdlib wheel writer + manifest | WP02 | |
| T006 | `spec_kitty_services/__init__.py`: providers with lazy kernel import | WP02 | |
| T007 | `pyproject.toml`, README and the in-tree PEP 517 backend (fallback, editable, sdist) | WP02 | |
| T008 | Red tests: build from fixture pins (4 platform + fallback), read service skipped, tampered asset fails, empty pins, size gate | WP03 | |
| T009 | `scripts/build_services_wheel.py` build path (pins → fetch_asset → wheels) | WP03 | |
| T010 | `--verify`: wheel contents == manifest == pins; size gate 95/60 MB | WP03 | |
| T011 | End-to-end: built companion "installed" and resolved through `resolution.resolve_binary` | WP03 | |
| T012 | Red tests: version lock (companion == CLI == extra pin), sdist excludes `packages/**` | WP04 | |
| T013 | Root `pyproject.toml`: `services` extra, uv workspace member + source, sdist exclude; `uv lock` | WP04 | |
| T014 | `validate_release.py` three-place version check + tests | WP04 | |
| T015 | `test_packaging_safety.py`: main wheel/sdist carry no companion file | WP04 | [P] |
| T016 | Install-slot ratchet: preferred over a warm cache | WP05 | [P] |
| T017 | Install-slot ratchet: explicit beats install; wrong digest refuses with a warm cache | WP05 | [P] |
| T018 | Install-slot ratchet: jar from the slot (with and without Java) | WP05 | [P] |
| T019 | Red tests: release.yml shape (sync step, companion jobs, publish order, environment) | WP06 | |
| T020 | `release.yml`: `sync_services.py --service all` + `--check` after the packs check | WP06 | |
| T021 | `release.yml`: `build-companion-wheels` + `publish-companion-pypi`; `publish-pypi` waits | WP06 | |
| T022 | RELEASE_CHECKLIST.md service and companion steps | WP06 | [P] |

## Phase 1 — Decision record

### WP01 — ADR amendment and governance clarifications ([prompt](tasks/WP01-adr-amendment.md))

- **Goal**: record the companion wheel decision before any code. **Priority**: P1. **Independent test**: docs lint/frontmatter gates pass; the amendment names all 12 rulings and the workspace member.
- **Subtasks**:

T001 ADR 2026-10-29-1 Amendment 2026-10-31 (WP01)
T002 CLAUDE.md clarification (WP01)
T003 Plan §3.4 status line (WP01)

- **Dependencies**: none. **Risks**: the D-9 frozen page must not be touched.

## Phase 2 — Foundation

### WP02 — Companion package and wheel writer ([prompt](tasks/WP02-companion-package.md))

- **Goal**: the `spec-kitty-services` source package: providers, manifest, deterministic wheel writer, in-tree backend. **Priority**: P1. **Independent test**: `tests/cross_cutting/packaging/test_companion_package.py`.
- **Subtasks**:

T004 Red tests for providers and the wheel writer (WP02)
T005 Wheel writer + manifest (WP02)
T006 Providers (WP02)
T007 pyproject, README, in-tree backend (WP02)

- **Dependencies**: WP01. **Risks**: RECORD hashes/format; exec bits; provider must never raise.

## Phase 3 — Stories

### WP03 — Release builder, digest and size gates ([prompt](tasks/WP03-release-builder.md))

- **Goal**: US4 and US1/US2 end to end. **Priority**: P1. **Independent test**: `tests/cross_cutting/packaging/test_companion_services_wheel.py`.
- **Subtasks**:

T008 Red tests for the builder (WP03)
T009 Build path (WP03)
T010 Verify + size gate (WP03)
T011 End-to-end resolution (WP03)

- **Dependencies**: WP02. **Risks**: no network in tests (`file://` fixtures).

### WP04 — CLI packaging wiring and version lock ([prompt](tasks/WP04-cli-packaging-wiring.md))

- **Goal**: US3 (the extra resolves everywhere) and the main-wheel purity half of FR-010. **Priority**: P1.
- **Subtasks**:

T012 Red tests for the version lock and sdist exclusion (WP04)
T013 Root pyproject + uv.lock (WP04)
T014 validate_release.py three-place check (WP04)
T015 Packaging-safety guard for companion files (WP04)

- **Dependencies**: WP02. **Risks**: `uv lock` churn; `test_pyproject_shape.py`.

### WP05 — Resolution install-slot ratchet ([prompt](tasks/WP05-resolution-ratchet.md))

- **Goal**: FR-011, pin the slot's position and digest check. **Priority**: P1.
- **Subtasks**:

T016 Preferred over a warm cache (WP05)
T017 Explicit beats install; wrong digest refuses with a warm cache (WP05)
T018 Jar from the slot (WP05)

- **Dependencies**: none. **Risks**: a failing ratchet is a real finding, not something to "fix" in the test.

## Phase 4 — Release

### WP06 — Release workflow and checklist ([prompt](tasks/WP06-release-workflow.md))

- **Goal**: FR-009, FR-012. **Priority**: P1.
- **Subtasks**:

T019 Red release.yml shape tests (WP06)
T020 sync_services steps (WP06)
T021 Companion build and publish jobs (WP06)
T022 RELEASE_CHECKLIST.md (WP06)

- **Dependencies**: WP03, WP04. **Risks**: existing release-shape tests; operator prerequisites (PyPI pending publisher, `pypi-services` environment).

## Parallelization

WP05 is independent. WP03 and WP04 can run side by side after WP02. In `single_branch` the WPs run sequentially in the repository root checkout.

## MVP

WP01 + WP02 + WP03: a buildable, verified companion. WP04 makes it installable through the extra, and WP06 ships it.

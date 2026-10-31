# Tasks: Pinned service binaries

**Mission**: `pinned-service-binaries-01M64N66` · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)
**Planning base / merge target**: `issue-6590-pinned-service-binaries`

Subtask completion is event-sourced: record it with `spec-kitty agent tasks mark-status Txxx --status done`. The rows below are references, not checkboxes.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | `ServiceTarget`, `ServiceAsset`, `ServicePin` value objects with validation | WP01 | |
| T002 | `load_service_pin` / `write_service_pin` (YAML, header comment, unknown-key and placeholder refusal) | WP01 | |
| T003 | Unit tests for the pin model (valid, each invalid shape, round trip) | WP01 | |
| T004 | `pins/README.md` (what a pin is, no real pin until the first release) | WP01 | [P] |
| T005 | `kernel.release_assets`: the single download owner (https/file, timeout, proxy/CA from env, atomic write) | WP02 | |
| T006 | `kernel.service_artifacts`: cache layout, `verify_asset`, `fetch_asset`, `resolve_cached` (re-verify, evict) | WP02 | |
| T007 | Offline asset directory (`SPEC_KITTY_SERVICE_ASSET_DIR`) lookup, digest-checked | WP02 | |
| T008 | Shared `file://` fixture-release builder for tests | WP02 | [P] |
| T009 | Unit tests: download, verify, cache eviction, partial-download safety, offline, asset dir | WP02 | |
| T010 | Architectural gate: release-asset downloads only in the owner (empty allowlist, floor, planted violation) | WP02 | |
| T011 | `specify_cli.services.errors`: `ServiceRefusal` and the codes with remedies | WP03 | |
| T012 | `specify_cli.services.host`: host target detection and JVM (major ≥ 25) detection | WP03 | |
| T013 | `specify_cli.services.resolution`: the resolution order and the pre-exec re-verify | WP03 | |
| T014 | Developer opt-in (`SPEC_KITTY_SERVICE_UNPINNED=1` plus explicit path, warning) | WP03 | |
| T015 | Acceptance tests for every tier and every refusal (US2, US5) | WP03 | |
| T016 | `tests/specify_cli/services/fake_service.py` implementing the accepted launch contract | WP04 | |
| T017 | `specify_cli.services.client`: handshake / health / shutdown over loopback with bearer token | WP04 | |
| T018 | `specify_cli.services.policies`: write-service policy (git common dir), charter stub, read never-launched | WP04 | |
| T019 | `specify_cli.services.launcher`: reuse-or-start, readiness wait, detached spawn, owner-only dir, log | WP04 | |
| T020 | Stale recovery and stop (POST /shutdown, then SIGTERM/TerminateProcess fallback) | WP04 | |
| T021 | Acceptance tests US1 (first run starts, second run reuses), races, stale, unhealthy, mismatch | WP04 | |
| T022 | `specify_cli.services.vendor`: resolve tag, fetch all assets, cross-check SHA256SUMS, requires_core, write pin | WP05 | |
| T023 | `spec-kitty service` command group: fetch, vendor (+ `--check`), status, stop | WP05 | |
| T024 | Register the command group in the CLI registrar tables (lazy import) | WP05 | |
| T025 | CLI tests (exit codes, JSON shapes, no-pin message) and vendor tests (US4) | WP05 | |
| T026 | `scripts/sync_services.py` (`--service`, `--offline`, `--check`) and `make sync-services` | WP06 | |
| T027 | `.github/actions/sync-services/action.yml` plus guard test (not wired into jobs yet) | WP06 | |
| T028 | Packaging guard: pins ship, no service binary or cache content in wheel/sdist | WP06 | |
| T029 | CI module registry: route `src/specify_cli/services/**` and its tests | WP06 | |
| T030 | Docs how-to (`docs/development/how-to/service-pins.md`), page inventory, retrieval index, CHANGELOG entry | WP06 | [P] |

## Phase 1 – Foundation

### WP01 – Service pin model (FR-001)
- **Prompt**: [tasks/WP01-service-pin-model.md](tasks/WP01-service-pin-model.md)
- **Goal**: a validated, committed record per service of which released bytes core runs. **Priority**: P1. **Independent test**: `tests/kernel/test_service_pin.py`.
- **Subtasks**:
  T001 Value objects with validation (WP01)
  T002 Load/write lockfile (WP01)
  T003 Unit tests (WP01)
  T004 pins/README.md (WP01)
- **Dependencies**: none. **Risks**: the schema must hold the optional extras without forcing them on every service.

### WP02 – Verified fetch, cache and the single download owner (FR-002, FR-003, FR-010 asset dir, NFR-003, NFR-004)
- **Prompt**: [tasks/WP02-verified-fetch-and-download-owner.md](tasks/WP02-verified-fetch-and-download-owner.md)
- **Goal**: an asset's bytes fetched once into a cache that is never trusted unverified, with one owner for remote contact. **Priority**: P1.
- **Subtasks**:
  T005 Download owner (WP02)
  T006 Cache and verify (WP02)
  T007 Offline asset directory (WP02)
  T008 Fixture-release builder (WP02)
  T009 Unit tests (WP02)
  T010 Architectural gate (WP02)
- **Dependencies**: WP01. **Risks**: partial downloads, proxies, Windows rename.

## Phase 2 – Resolve and launch

### WP03 – Binary resolution and fail-closed refusals (FR-004, FR-005, FR-011)
- **Prompt**: [tasks/WP03-resolution-and-refusals.md](tasks/WP03-resolution-and-refusals.md)
- **Goal**: deterministic choice of verified bytes, or a named refusal with a remedy. **Priority**: P1 (US2, US5).
- **Subtasks**:
  T011 Refusals (WP03)
  T012 Host and JVM detection (WP03)
  T013 Resolution order (WP03)
  T014 Unpinned opt-in (WP03)
  T015 Acceptance tests (WP03)
- **Dependencies**: WP02.

### WP04 – Launcher lifecycle (FR-006 to FR-009)
- **Prompt**: [tasks/WP04-launcher-lifecycle.md](tasks/WP04-launcher-lifecycle.md)
- **Goal**: one healthy write service per clone, started when down, reused when up, per the accepted launch contract. **Priority**: P1 (US1).
- **Subtasks**:
  T016 Fake service (WP04)
  T017 Loopback client (WP04)
  T018 Policies (WP04)
  T019 Launcher (WP04)
  T020 Stale recovery and stop (WP04)
  T021 Acceptance tests (WP04)
- **Dependencies**: WP03. **Risks**: process races, detached spawn per OS, timing in tests.

## Phase 3 – Operator surfaces and hygiene

### WP05 – Vendor and the `spec-kitty service` command group (FR-010 fetch, FR-013)
- **Prompt**: [tasks/WP05-vendor-and-service-cli.md](tasks/WP05-vendor-and-service-cli.md)
- **Goal**: one bump path and the user commands. **Priority**: P2 (US4).
- **Subtasks**:
  T022 Vendor (WP05)
  T023 Command group (WP05)
  T024 Registrar (WP05)
  T025 Tests (WP05)
- **Dependencies**: WP02, WP04.

### WP06 – Sync script, CI action, packaging guard, registry and docs (FR-012, FR-014)
- **Prompt**: [tasks/WP06-sync-ci-packaging-docs.md](tasks/WP06-sync-ci-packaging-docs.md)
- **Goal**: the same verified bytes in checkouts and CI, a pure wheel, routed CI, documented. **Priority**: P2 (US3).
- **Subtasks**:
  T026 Sync script and make target (WP06)
  T027 Composite action and guard (WP06)
  T028 Packaging guard (WP06)
  T029 Registry routing (WP06)
  T030 Docs and changelog (WP06)
- **Dependencies**: WP02, WP05.

## Parallelisation

WP01 → WP02 → WP03 → WP04 is the critical path. WP05 and WP06 follow WP04, and their file sets do not overlap. MVP: WP01 to WP04 (a user command can get a verified, running service).

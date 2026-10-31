# Implementation Plan: Pinned service binaries

**Branch**: `issue-6590-pinned-service-binaries` | **Date**: 2026-10-29 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/pinned-service-binaries-01M64N66/spec.md`

## Summary

Core gets one mechanism to consume backend service binaries released by sibling repositories. The mechanism has four parts:
- **Pin.** A lockfile per service records a `service-v*` tag, the resolved commit and a sha256 per asset.
- **Fetch.** A standard-library HTTPS download goes into a per-service, per-tag cache. One owner module performs it, and a gate keeps it there.
- **Verify.** The sha256 is checked on every resolve and immediately before execution.
- **Launch.** One fail-closed launcher starts or reuses the write service per git common dir, using the process contract that the spec-kitty-events operator accepted on 2026-10-29.

The same pieces also deliver:
- `make sync-services` and a CI composite action for checkouts and jobs;
- `spec-kitty service vendor` as the only way to bump a pin;
- `spec-kitty service fetch | status | stop` for users;
- a developer opt-in that runs an unpinned local binary.

No real pin is committed until spec-kitty-events cuts its first release. Tests drive everything against a `file://` fixture release and a fake service written in Python.

## Technical Context

**Language/Version**: Python 3.11+ (the repository's floor).
**Primary Dependencies**:
- The `kernel` layer uses the standard library only: `urllib.request`, `hashlib`, `ssl` and `subprocess`. Kernel is zero-dependency by contract (`src/kernel/pyproject.toml`).
- `specify_cli` uses the dependencies it already has: typer and rich for the CLI.
- No new third-party dependency, so no supply-chain review is triggered (DIRECTIVE_051: no dependency decision).

**Storage**:
- Files only.
- Lockfiles: `pins/<service>.source.yaml` (committed).
- Cache: `${XDG_CACHE_HOME:-~/.cache}/spec-kitty/services/<service>/<tag>/<asset>`, through `kernel.user_dirs.user_cache_dir(windows_local_appdata=False)`, like the packs.
- Runtime state of the write service: `<git-common-dir>/spec-kitty-write-service/` (`service.lock`, `endpoint.json`, `service.log`).

**Testing**:
- pytest.
- Unit tests for the pin model, verify and cache.
- An in-process `file://` fixture release, with a fixture builder that writes assets and a `SHA256SUMS`.
- A fake service script, `tests/specify_cli/services/fake_service.py`, that implements the accepted argv, the lock, endpoint publication by rename, `/handshake`, `/health` and `/shutdown` over loopback HTTP with a bearer token.
- Tests are marked `fast` where they spawn no process and `integration` where they spawn the fake service.
- One non-vacuous gate test for the download owner.

**Target Platform**: Linux, macOS and Windows; host targets linux-x64, linux-arm64, macos-arm64 and windows-x64, plus a platform-neutral jar.
**Project Type**: single (the existing `src/` layered package set).
**Performance Goals**:
- warm resolve-and-connect adds ≤150 ms p95 (NFR-001);
- cold start gives up at 15 s by default (NFR-002);
- the fake service is ready in under 2 s.

**Constraints**:
- No binary in the wheel or sdist (FR-014).
- Nothing unverified executes (NFR-003).
- `https://` and `file://` only, with a 60 s inactivity timeout (NFR-004).
- Owner-only token files (NFR-005).
- Complexity ceiling 15, ruff, ruff format and mypy clean, 90% diff coverage (NFR-007).

**Scale/Scope**: three services eventually (write, read for CI only, charter); four native targets plus a jar each; one running write service per clone.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority:** satisfied. One owner each for the pin model, the downloads and the launcher. The packs precedent is mirrored, not forked. The process contract is recorded once, in this mission's `contracts/` and spec-kitty-events' `contracts/mission-write` at cut-over, and not restated in code comments.
- **Architectural alignment / layer rules:** satisfied.
  - The primitives live in `kernel`, which has no outbound imports.
  - The launcher and CLI live in `specify_cli`.
  - `charter` is untouched.
  - No `pyproject.toml` package-set change: `src/kernel` and `src/specify_cli` already ship.
- **ATDD-first:** each user story's acceptance scenarios become acceptance tests first, red before the code.
- **Standing Order #5 (gate discipline):** the new download-owner gate starts with an empty allowlist, and has a scanned-file floor and a planted-violation self-test.
- **Terminology:** "Mission" is untouched. "sync" appears only in `make sync-services`, which mirrors `make sync-packs`. It is a fetch of pinned artifacts, not the retired sync transport; the plan never uses "sync" for any other purpose.
- **Loopback HTTP is a special case** (CLAUDE.md, Sonar). The launcher talks plain HTTP to `127.0.0.1` on purpose. A Sonar hotspot, if raised, gets a rationale; HTTPS is not forced.
- **No violations.** Complexity Tracking stays empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/pinned-service-binaries-01M64N66/
├── spec.md
├── plan.md              # this file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── service-pin.schema.md      # lockfile shape and validation rules
│   ├── launch-contract.md         # core ↔ service process contract (accepted 2026-10-29)
│   └── cli-surface.md             # spec-kitty service … and make/script/action surfaces
├── checklists/requirements.md
└── tasks/               # created by /spec-kitty.tasks
```

### Source Code (repository root)

```
src/kernel/
├── service_pin.py          # ServicePin, ServiceAsset, ServiceTarget, load/write/validate, placeholder refusal
├── service_artifacts.py    # cache layout, verify_asset, fetch_asset, resolve_cached (re-verify on read)
└── release_assets.py       # THE download owner: https/file only, timeout, proxy from env, atomic write

src/specify_cli/services/
├── __init__.py
├── errors.py               # ServiceRefusal + codes (SERVICE_BINARY_MISSING, …) with remedies
├── host.py                 # host target detection, JVM detection (java -version major)
├── resolution.py           # resolution order (explicit path, install slot, cache, jar, refusal); unpinned opt-in
├── client.py               # loopback HTTP: handshake / health / shutdown with bearer token (uses write_service_protocol shapes)
├── launcher.py             # ServiceLauncher: reuse-or-start, readiness wait, stale recovery, stop
├── policies.py             # per-service policy: write (git common dir), charter (worktree; stub), read (never launched)
└── vendor.py               # bump logic: resolve tag, fetch all assets, cross-check SHA256SUMS, write lockfile

src/specify_cli/cli/commands/service.py   # `spec-kitty service fetch|vendor|status|stop`
scripts/sync_services.py                   # --service all|<name> [--offline] [--check]
Makefile                                   # sync-services target
.github/actions/sync-services/action.yml   # cache restore + scripts/sync_services.py
pins/README.md                             # how pins work; no real pin until the first release

tests/kernel/test_service_pin.py
tests/kernel/test_service_artifacts.py
tests/kernel/test_release_assets.py
tests/specify_cli/services/            # fake_service.py, fixture_release.py, test_resolution.py, test_launcher.py, test_cli.py, test_vendor.py
tests/architectural/test_release_asset_download_owner.py
tests/ci/test_sync_services.py         # script + action guard (mirrors test_workflows_sync_packs.py)
tests/cross_cutting/packaging/test_packaging_safety.py   # extended: no service binary, pins ship
```

**Structure Decision**:
- Primitives go in `kernel`, beside `kernel.git.remote` (the git-contact owner) and `kernel.user_dirs`. A release-asset download is the HTTP sibling of git remote contact.
- The application logic goes in a new `specify_cli/services/` package, because no existing package owns process lifecycle for external binaries.
- The CLI goes in one new command module.
- CI registry: `src/specify_cli/services/**` joins an existing module row together with its test directory, so no new shard is needed. `tests/kernel` is already owned by the `kernel` row.

## Complexity Tracking

No Charter Check violations.

## Implementation Concern Map

### IC-01 — Pin model and lockfile

- **Purpose**: one validated, committed record per service of which released bytes core runs.
- **Relevant requirements**: FR-001, C-001, C-003
- **Affected surfaces**: `src/kernel/service_pin.py`, `pins/README.md`, `tests/kernel/test_service_pin.py`
- **Sequencing/depends-on**: none
- **Risks**: the schema must cover the contract-bundle, contract-tools and fixtures assets without forcing them on every service. Placeholder pins must refuse at load time, not at download time.

### IC-02 — Verified fetch, cache and the single download owner

- **Purpose**: get an asset's bytes once, from `https://` or `file://`, into a cache that is never trusted unverified, with one module owning remote contact.
- **Relevant requirements**: FR-002, FR-003, FR-010, NFR-003, NFR-004
- **Affected surfaces**: `src/kernel/release_assets.py`, `src/kernel/service_artifacts.py`, `tests/kernel/*`, `tests/architectural/test_release_asset_download_owner.py`
- **Sequencing/depends-on**: IC-01
- **Risks**:
  - Partial downloads: write to a temp file, then rename.
  - Proxies and CA bundles in corporate and agent environments: honour the standard environment variables.
  - Windows rename semantics: reuse the packs retry pattern.

### IC-03 — Binary resolution and fail-closed refusals

- **Purpose**: decide deterministically which verified bytes to run, or refuse with a named code and remedy.
- **Relevant requirements**: FR-004, FR-005, FR-011, NFR-003
- **Affected surfaces**: `src/specify_cli/services/{errors,host,resolution}.py`, tests
- **Sequencing/depends-on**: IC-02
- **Risks**:
  - JVM detection must not run `java` when a native asset exists, for speed.
  - The opt-in must never be honoured without an explicit path.
  - Each refusal message must not leak the token.

### IC-04 — Launcher lifecycle (start, reuse, health, stale recovery, stop)

- **Purpose**: one healthy write service per clone, started when down and reused when up, following the accepted process contract.
- **Relevant requirements**: FR-006, FR-007, FR-008, FR-009, NFR-001, NFR-002, NFR-005, C-006
- **Affected surfaces**: `src/specify_cli/services/{client,launcher,policies}.py`, `tests/specify_cli/services/fake_service.py`, tests
- **Sequencing/depends-on**: IC-03
- **Risks**:
  - Races between two CLI processes: the service lock decides, and the launcher reads the published endpoint.
  - Detached process spawning on Windows (creation flags) versus POSIX (`start_new_session`).
  - pid reuse: identity is checked through the handshake's `instanceId`.
  - Timing-sensitive tests: generous budgets, plus an injected clock where possible.

### IC-05 — Developer, CI and maintainer surfaces

- **Purpose**: the same verified bytes in checkouts and CI, one bump path, and user-facing commands.
- **Relevant requirements**: FR-010, FR-012, FR-013
- **Affected surfaces**: `src/specify_cli/services/vendor.py`, `src/specify_cli/cli/commands/service.py` and its registration, `scripts/sync_services.py`, `Makefile`, `.github/actions/sync-services/action.yml`, `tests/ci/test_sync_services.py`, docs how-to
- **Sequencing/depends-on**: IC-02 (sync, fetch), IC-04 (status, stop)
- **Risks**:
  - The CI action must not run until a real pin exists. It is added and guarded but wired into no job yet, because no pin exists. The wiring comes with the first real pin, which is the cut-over's job.
  - The pin gate job in CI likewise waits for a real pin.

### IC-06 — Packaging and registry hygiene

- **Purpose**: prove that the wheel and sdist carry the pins but no binary, and route the new code in CI.
- **Relevant requirements**: FR-014, NFR-007, C-004
- **Affected surfaces**: `tests/cross_cutting/packaging/test_packaging_safety.py`, `pyproject.toml` (sdist include of `pins/` only if needed), `.github/ci-module-registry.yml`, `scripts/ci/gate_selection.py` if the router needs the new roots
- **Sequencing/depends-on**: IC-01, IC-05
- **Risks**: the registry and router have several self-consistency gates (`test_module_shard_registry.py`, `test_gate_selection_authority.py`, `test_ci_module_wiring.py`), so all of them need to run.

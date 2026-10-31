---
work_package_id: WP03
title: Release builder, digest and size gates
dependencies:
- WP02
requirement_refs:
- FR-004
- FR-005
- FR-007
- FR-010
- NFR-002
- NFR-003
- C-003
- C-007
- SC-001
- SC-002
- SC-004
planning_base_branch: companion-services-wheel
merge_target_branch: companion-services-wheel
branch_strategy: Planning artifacts for this mission were generated on companion-services-wheel. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into companion-services-wheel unless the human explicitly redirects the landing branch.
subtasks:
- T008
- T009
- T010
- T011
phase: Phase 3 - Stories
history:
- at: '2026-10-31T14:15:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/build_services_wheel.py
create_intent:
- scripts/build_services_wheel.py
- tests/cross_cutting/packaging/test_companion_services_wheel.py
execution_mode: code_change
model: ''
owned_files:
- scripts/build_services_wheel.py
- tests/cross_cutting/packaging/test_companion_services_wheel.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP03 – Release builder, digest and size gates

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter
**before parsing the rest of this prompt**, and behave according to its guidance.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If the profile cannot be loaded, run `spec-kitty agent profile list` and select the best match for
`task_type: implement` on `authoritative_surface: scripts/build_services_wheel.py`.

---

## Branch Strategy

- Planning base and final merge target: `companion-services-wheel`.
- Topology `single_branch`: no lane worktree. Work in the repository root checkout on `companion-services-wheel`.
- Start with `spec-kitty agent action implement WP03 --agent claude --mission companion-services-wheel-01M694B1`.


## Objective

`scripts/build_services_wheel.py` (FR-004, FR-005, FR-007, FR-010 companion half, NFR-003, C-003, C-007): read the release commit's
`pins/`, fetch every native asset of the write and charter services through `kernel.service_artifacts.fetch_asset`, write one platform
wheel per target that has assets plus the fallback wheel, enforce the size gate, and verify written wheels (`--verify`).

## Context

- Precedent: `scripts/sync_services.py` (argparse wrapper, `PYTHONPATH=src`, imports only `kernel`, `main(argv, *, repo_root, cache_root)`).
- Fixtures: `tests/kernel/service_release_fixture.build_release(root, service=..., assets={target: bytes})` writes a `file://` release and
  returns `(pin, release_dir)`; write the pin with `kernel.service_pin.write_service_pin(pin, pin_path(repo, service))`.
- The companion's writer: `packages/spec-kitty-services/spec_kitty_services/wheel.py` (WP02). Import it by path (insert the package dir on sys.path).
- `COMPANION_SERVICES = ("charter-service", "write-service")` — the read service is skipped even when pinned (FR-005).

## Subtasks

### T008 — Red tests (`tests/cross_cutting/packaging/test_companion_services_wheel.py`, fast)

Load the script by file path (as `tests/ci/test_sync_services.py` does). Fixture: a fake repo with `pyproject.toml` (`[project] version = "4.0.0rc8"`)
and `pins/` filled from `build_release` for write-service and charter-service, all four native targets plus a jar. Tests:
1. Build writes exactly 5 wheels: 4 platform + `py3-none-any`; names `spec_kitty_services-4.0.0rc8-py3-none-<tag>.whl`.
2. Each platform wheel holds exactly `bin/<asset>` for both services of its target, byte-identical to the release assets; no jar; manifest == pins.
3. A pinned read-service is not packed (positive control: write-service from the same fixture is).
4. A corrupted asset (`corrupt={"linux-x64"}`) → exit 1, `SERVICE_BINARY_DIGEST_MISMATCH` on stderr, and **no** wheel written (build into a temp dir, move on success).
5. No pins → only the fallback wheel, exit 0.
6. Size gate: with an injected `max_bytes`/`warn_bytes` (CLI flags `--max-mb`/`--warn-mb` or keyword args), an over-cap wheel fails, a wheel over the warn line prints a warning and passes.
7. `--verify DIR`: passes on the built wheels; fails when a `bin/` member is swapped (rewrite the zip with different bytes), when a member is added, and when the manifest disagrees with the pins.
8. Determinism: two builds produce identical bytes.
9. `--glibc-floor 2_28` changes the Linux tags.

### T009 — Build path

`main(argv=None, *, repo_root=None, cache_root=None) -> int`; args `--out`, `--glibc-floor` (default `2_39`), `--offline`, `--max-mb 95`, `--warn-mb 60`, `--verify DIR`.
CLI version from `<repo>/pyproject.toml` (`tomllib`). For each target: collect `(service, asset)` from pins, `fetch_asset(pin, asset, offline=..., cache_root=...)`
→ verified path → bytes. Errors: `ServiceArtifactError` → print `code message` to stderr, exit 1; `ServicePinError` → `SERVICE_PIN_INVALID`.
Write into a `tempfile.mkdtemp(dir=out.parent)` and rename into `--out` only when every wheel passes the gate.

### T010 — Verify + size gate

`verify(dir, repo_root) -> list[str]` (problems). For every wheel: open, read manifest, check `cli_version` == repo version, `target` matches the tag,
`bin/*` set == manifest set, each member's sha256 == manifest sha256 == pin sha256, no service outside COMPANION_SERVICES, and RECORD hashes match.
The fallback must exist and hold no `bin/`. The size gate counts the wheel file size.

### T011 — End-to-end resolution

In the same test file: build from fixture pins, `pip install --target <site> --no-deps --no-index <linux-x64 wheel>`? A manylinux_2_39 wheel will not
install on an older test host. Instead **extract** the wheel into `<site>` (zip extract keeps paths), then point a fake entry point at the extracted
provider: monkeypatch `resolution._binary_providers` to return an object whose `load()` imports the provider from `<site>`; monkeypatch the CLI version
lookup and the host (`linux-x64`), the CLI pins dir (`resolution.source_checkout_root` → the fixture repo), and resolve with `resolve_binary("write-service", env={}, offline=True, cache_root=tmp)`.
Assert `source == "install"`, sha256 == pin. Positive control on the same fixture: tamper the extracted binary → `SERVICE_BINARY_DIGEST_MISMATCH`.
Also install the fallback wheel with real `pip install --target --no-deps --no-index` (it is `py3-none-any`) and assert providers return `None` — this proves pip accepts our RECORD/WHEEL.

## Validation

- `uv run --frozen pytest tests/cross_cutting/packaging/test_companion_services_wheel.py tests/cross_cutting/packaging/test_companion_package.py -q` (< 10 s, NFR-002)
- ruff check/format (`--force-exclude`), `mypy --strict scripts/build_services_wheel.py` (with `MYPYPATH=src`).
- `PYTHONPATH=src uv run --frozen python scripts/build_services_wheel.py --out /tmp/x` on the real checkout → fallback only ("no service pinned").

## Commit discipline

- The red test is its own commit **before** the implementation commit (charter ATDD-First, C-011).
- Every commit carries `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`. No AI model identifier.

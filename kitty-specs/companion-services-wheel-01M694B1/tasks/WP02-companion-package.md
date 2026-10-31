---
work_package_id: WP02
title: Companion package and wheel writer
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-003
- FR-006
- NFR-001
- C-004
- C-005
planning_base_branch: companion-services-wheel
merge_target_branch: companion-services-wheel
branch_strategy: Planning artifacts for this mission were generated on companion-services-wheel. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into companion-services-wheel unless the human explicitly redirects the landing branch.
subtasks:
- T004
- T005
- T006
- T007
phase: Phase 2 - Foundation
history:
- at: '2026-10-31T14:15:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: packages/spec-kitty-services/
create_intent:
- packages/spec-kitty-services/pyproject.toml
- packages/spec-kitty-services/README.md
- packages/spec-kitty-services/spec_kitty_services/__init__.py
- packages/spec-kitty-services/spec_kitty_services/wheel.py
- packages/spec-kitty-services/_backend/spec_kitty_services_backend.py
- tests/cross_cutting/packaging/test_companion_package.py
execution_mode: code_change
model: ''
owned_files:
- packages/spec-kitty-services/**
- tests/cross_cutting/packaging/test_companion_package.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP02 – Companion package and wheel writer

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter
**before parsing the rest of this prompt**, and behave according to its guidance.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If the profile cannot be loaded, run `spec-kitty agent profile list` and select the best match for
`task_type: implement` on `authoritative_surface: packages/spec-kitty-services/`.

---

## Branch Strategy

- Planning base and final merge target: `companion-services-wheel`.
- Topology `single_branch`: no lane worktree. Work in the repository root checkout on `companion-services-wheel`.
- Start with `spec-kitty agent action implement WP02 --agent claude --mission companion-services-wheel-01M694B1`.


## Objective

Create the `spec-kitty-services` source package (FR-002, FR-003, FR-006 tag helper, NFR-001, C-004, C-005): providers that fill the
`spec_kitty.service_binaries` slot, a deterministic stdlib wheel writer and manifest, and a stdlib in-tree PEP 517 backend.

## Context

- Consumer: `src/specify_cli/services/resolution.py` (`BINARY_PROVIDER_GROUP`, `_provided_path`, `_install`). An entry point loads to a
  zero-argument callable returning a path or `None`. Do not change resolution.
- Contracts: `kitty-specs/companion-services-wheel-01M694B1/contracts/companion-wheel.md`, `companion-manifest.schema.json`, and
  `data-model.md` (provider decision).
- Host detection authority: `kernel.service_hosts.host_target()`; target values from `kernel.service_pin.ServiceTarget`.

## Layout

```
packages/spec-kitty-services/
├── pyproject.toml          # [project] name/version (== root version), requires-python >=3.11, entry points;
│                           # [build-system] requires=[], build-backend="spec_kitty_services_backend", backend-path=["_backend"]
├── README.md
├── _backend/spec_kitty_services_backend.py   # build_wheel / build_editable / build_sdist (+ get_requires_* -> [])
└── spec_kitty_services/
    ├── __init__.py         # write_service(), charter_service(); MANIFEST_NAME, BIN_DIR
    └── wheel.py            # WheelSpec, write_wheel(), manifest helpers, PLATFORM_TAGS
```

The backend imports `spec_kitty_services.wheel` by adding the project root to `sys.path` (it is the same file, one authority).

## Subtasks

### T004 — Red tests (`tests/cross_cutting/packaging/test_companion_package.py`, `pytest.mark.fast`)

Load the package by path (it is not installed in the test env): insert `packages/spec-kitty-services` on `sys.path` via a fixture
(monkeypatch.syspath_prepend) and import `spec_kitty_services`. Tests:
1. Provider returns the binary path when manifest `cli_version` == installed CLI version (monkeypatch the version lookup),
   `target` == host (monkeypatch the host lookup), service listed, file exists. Build the package dir in `tmp_path` with
   `bin/<asset>` and `_manifest.json` (point the provider at it via a module-level `_package_dir()` seam).
2. Returns `None` on a CLI version mismatch (positive control: same fixture, matching version → path).
3. Returns `None` on a host mismatch, on a missing manifest, on a missing file, on a service not listed, and when the host lookup raises ImportError.
4. Never raises on a corrupt manifest (invalid JSON) → `None`.
5. `write_wheel` is byte-identical across two runs (NFR-001); members sorted; `RECORD` lists every member with `sha256=<urlsafe b64 no padding>,<size>`
   and itself as `RECORD,,`; `WHEEL` has `Root-Is-Purelib: false` for platform tags, `true` for `py3-none-any`, `Tag: py3-none-<plat>`;
   a `bin/*` member has unix mode 0o755 in `external_attr`; `entry_points.txt` has the `[spec_kitty.service_binaries]` group with both services.
6. `PLATFORM_TAGS` maps each native `ServiceTarget` value to the tag in FR-006 with a glibc-floor parameter (default `2_39`).
7. The in-tree backend: `build_wheel(tmp)` produces `spec_kitty_services-<ver>-py3-none-any.whl` with a manifest `target: null, services: []`
   and no `bin/` member; `build_sdist` produces a `.tar.gz`; `build_editable` produces a wheel with a `.pth` pointing at the project root.
   Call the hook functions in-process (import the backend module by path), and also once via `python -m pip wheel --no-deps --no-build-isolation`?
   **No** — keep it in-process (NFR-002: fast, no network).

Commit these red first.

### T005 — `wheel.py`

- `write_wheel(out_dir, *, version, tag, members: Mapping[str, bytes], executables: frozenset[str]) -> Path` writes
  `spec_kitty_services-<version>-<tag>.whl` with `dist-info` files (`METADATA`: Metadata-Version 2.1, Name, Version, Summary,
  Requires-Python `>=3.11`; `WHEEL`; `entry_points.txt`; `RECORD`). Fixed `date_time=(1980,1,1,0,0,0)`, `ZIP_DEFLATED`, sorted.
- `manifest_bytes(cli_version, target, services)` → canonical JSON (sorted keys, `\n` end) per the schema.
- `PLATFORM_TAGS(glibc="2_39")` or a function `platform_tag(target, glibc_floor="2_39")`.
- Normalise the version per PEP 440 for file names (use the given string; the CLI version is already normalised, e.g. `4.0.0rc8`).

### T006 — Providers (`__init__.py`)

- `write_service()` / `charter_service()` call `_provide(service)`. `_provide` reads the manifest, compares `cli_version` with
  `importlib.metadata.version("spec-kitty-cli")` (PackageNotFoundError → None), compares `target` with a lazily imported
  `kernel.service_hosts.host_target()` (any Exception → None), then returns `str(path)` when `bin/<asset>` is a regular file.
- Catch everything: a provider must never raise (resolution turns a raise into a `SERVICE_BINARY_MISSING` refusal, which would block the fetch).
  A broad `except Exception` here is justified — comment why.

### T007 — pyproject, README, backend

- `pyproject.toml` version must equal the root `pyproject.toml` version (WP04 adds the guard). Static metadata only (no `dynamic`), so uv locks it without building.
- README: what it is, that it is optional, how the CLI uses it, that the read service never ships, link to the ADR amendment.
- Backend: `build_wheel` → fallback wheel (providers + manifest with `cli_version` = own version, `target` null). `build_editable` →
  wheel with `spec_kitty_services_editable.pth` containing the project root. `build_sdist` → deterministic tar.gz of pyproject, README,
  `_backend/`, `spec_kitty_services/` with PKG-INFO. `get_requires_for_build_*` → `[]`.

## Validation

- `uv run --frozen pytest tests/cross_cutting/packaging/test_companion_package.py -q`
- `uv run --frozen ruff check packages/ tests/cross_cutting/packaging/test_companion_package.py`; `ruff format --check --force-exclude` on them.
- `uv run --frozen mypy --strict packages/spec-kitty-services/spec_kitty_services packages/spec-kitty-services/_backend`

## Definition of Done

All T004 tests green; ruff/mypy clean; no import of `kernel` at module load in `spec_kitty_services`.

## Risks

pip rejects a wheel whose RECORD hash or name normalisation is wrong — the WP03 end-to-end installs one with `pip install --target` to prove it.

## Commit discipline

- The red test is its own commit **before** the implementation commit (charter ATDD-First, C-011).
- Every commit carries `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`. No AI model identifier.

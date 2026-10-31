---
work_package_id: WP01
title: Service pin model
dependencies: []
requirement_refs:
- FR-001
- C-001
- C-003
planning_base_branch: issue-6590-pinned-service-binaries
merge_target_branch: issue-6590-pinned-service-binaries
branch_strategy: Planning artifacts for this mission were generated on issue-6590-pinned-service-binaries. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6590-pinned-service-binaries unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-pinned-service-binaries-01M64N66
base_commit: 70cb40bdea7fd1c029982c1290604acc798ea3d7
created_at: '2026-10-29T21:55:30.230467+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Foundation
history:
- at: '2026-10-29T21:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/kernel/service_pin.py
create_intent:
- src/kernel/service_pin.py
- tests/kernel/test_service_pin.py
- pins/README.md
execution_mode: code_change
model: ''
owned_files:
- src/kernel/service_pin.py
- tests/kernel/test_service_pin.py
- pins/README.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Service pin model

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). Address all feedback before completing, and record what you changed with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

- `src/kernel/service_pin.py` defines the pin lockfile model of `kitty-specs/pinned-service-binaries-01M64N66/contracts/service-pin.schema.md` and `data-model.md` exactly.
- A valid lockfile loads into frozen dataclasses. Every invalid shape raises `ServicePinError` with code `SERVICE_PIN_INVALID` and a message that names the field. A placeholder pin is refused at load time.
- `write_service_pin` round-trips byte-stably (sorted, deterministic YAML with the fixed header comment).
- FR-001 is satisfied, and non-vacuous: a placeholder and a malformed fixture are refused on the same test file as a valid fixture that loads.

## Context & Constraints

- Read first: `spec.md` (FR-001, C-001, C-003), `data-model.md`, `contracts/service-pin.schema.md`, ADR `docs/adr/4.x/2026-10-29-1-the-events-domain-and-its-java-services-live-in-spec-kitty-events.md` D-3.
- Precedent to mirror (do not import it; `kernel` must not import `charter`): `src/charter/offering/packs/pack_pin.py`. It provides the frozen dataclasses with `__post_init__` validation, the `_require_str` / `_optional_str` helpers, `load_pack_pin` and `write_pack_pin` with a header comment.
- **Layer rule:** `kernel` is the root layer and has zero third-party dependencies (`src/kernel/pyproject.toml`: `dependencies = []`). Read YAML through the existing kernel helper `kernel.yaml_io`; check what it exposes first. Do not add a dependency.
- Quality: ruff, ruff format (`--force-exclude` for single files), mypy clean, complexity ≤ 15, no new suppressions.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `issue-6590-pinned-service-binaries`
- **Merge target branch**: `issue-6590-pinned-service-binaries`

Execution worktrees are allocated per computed lane from `lanes.json`. Start with `spec-kitty agent action implement WP01 --agent claude --mission pinned-service-binaries-01M64N66`.

## Subtasks & Detailed Guidance

### Subtask T001 – Value objects with validation

- **Purpose**: one typed, validated in-memory form of a pin, so later code never re-validates.
- **Steps**:
  1. `class ServicePinError(ValueError)` with `error_code = "SERVICE_PIN_INVALID"`. The message names the offending field, never a whole value longer than 80 characters.
  2. `class ServiceTarget(enum.StrEnum)`: `LINUX_X64 = "linux-x64"`, `LINUX_ARM64 = "linux-arm64"`, `MACOS_ARM64 = "macos-arm64"`, `WINDOWS_X64 = "windows-x64"`, `JVM = "jvm"`.
  3. `@dataclass(frozen=True) class ServiceAsset: name: str; sha256: str`. Validate:
     - `name` is a plain file name: non-empty, no `/`, `\`, NUL, `..`, and not `.` or `..`;
     - `sha256` matches `^[0-9a-f]{64}$`.
  4. `@dataclass(frozen=True) class ServicePin`, with fields:
     - `service: str` (one of `write-service`, `read-service`, `charter-service`; keep the set as a module constant `KNOWN_SERVICES`);
     - `repository: str` (starts with `https://` or `file://`);
     - `tag: str` (regex `^service-v\d+\.\d+\.\d+([-.+][0-9A-Za-z.-]+)?$`; `service-v0.0.0` is the placeholder and refuses);
     - `commit: str` (40 lowercase hex; all zeros refuses);
     - `protocol_versions: tuple[int, ...]` (non-empty, positive ints);
     - `requires_core: str` (non-empty; parse with `packaging.specifiers` only if `packaging` is importable from kernel; otherwise keep it as an opaque string and leave the check to WP05's vendor; do not add a dependency);
     - `assets: Mapping[ServiceTarget, ServiceAsset]` (at least one entry; use `types.MappingProxyType` for immutability);
     - `extras: Mapping[str, ServiceAsset]` (keys in `{"contracts", "contract_tools", "fixtures"}`; may be empty).
     Asset names must be unique across `assets` and `extras`.
  5. Add `ServicePin.asset_for(target: ServiceTarget) -> ServiceAsset | None`.
- **Files**: `src/kernel/service_pin.py` (new, ~150 lines).
- **Notes**: keep each validator a small function so complexity stays low; Sonar rewards that.

### Subtask T002 – Load and write the lockfile

- **Purpose**: the file form of the pin (`pins/<service>.source.yaml`).
- **Steps**:
  1. `load_service_pin(path: Path) -> ServicePin`:
     - read the mapping through `kernel.yaml_io`; a non-mapping refuses;
     - refuse unknown top-level keys (allowed: `service`, `repository`, `tag`, `commit`, `protocol_versions`, `requires_core`, `assets`, `extras`);
     - the file stem must equal `<service>.source` (`write-service.source.yaml` → `write-service`);
     - a missing file raises `ServicePinError` with a message that the service is not pinned in this core version. Callers turn that into the user-facing "not yet pinned" refusal.
  2. `write_service_pin(pin: ServicePin, path: Path) -> None`: writes the header comment from the schema contract, then keys in the schema's order with assets sorted by target value, atomically (use `kernel.atomic`).
  3. `pin_path(repo_root: Path, service: str) -> Path` returns `repo_root / "pins" / f"{service}.source.yaml"`. Keep `PINS_DIR = "pins"` as a constant.
- **Files**: same module.

### Subtask T003 – Unit tests

- **Purpose**: pin every rule; red first.
- **Steps**: in `tests/kernel/test_service_pin.py` (mark `pytestmark = pytest.mark.fast`), with a `_valid_document()` helper:
  - valid loads, with `asset_for` hit and miss;
  - parametrized invalid cases, one per rule above: bad tag, placeholder tag, short commit, zero commit, empty protocol list, bad digest, path-like asset name, duplicate asset names, unknown key, unknown extras key, unknown target, stem mismatch, non-https repository;
  - a missing file raises with the "not pinned" wording;
  - `write` then `load` round-trips, and writing twice is byte-identical.
- **Files**: `tests/kernel/test_service_pin.py` (new, ~150 lines).

### Subtask T004 – `pins/README.md`

- **Purpose**: tell a maintainer what lives in `pins/` and that it is empty until spec-kitty-events cuts its first `service-v*` release (C-003).
- **Steps**: a short README: purpose; schema link (`kitty-specs/pinned-service-binaries-01M64N66/contracts/service-pin.schema.md` for now, and the ADR); "bump only with `spec-kitty service vendor`"; "never hand-edit a digest". It is not a docs-site page, so it needs no frontmatter. Check whether a docs lint scans the repo root `pins/`; if it does, follow that lint's rules.
- **Parallel?**: yes.

## Test Strategy

```bash
uv run --frozen pytest -q tests/kernel/test_service_pin.py
uv run --frozen ruff check src/kernel/service_pin.py tests/kernel/test_service_pin.py
uv run --frozen ruff format --check --force-exclude src/kernel/service_pin.py tests/kernel/test_service_pin.py
uv run --frozen mypy src/kernel/service_pin.py
uv run --frozen pytest -q tests/architectural/test_layer_rules.py   # kernel imports nothing outbound
```

## Risks & Mitigations

- Kernel has no YAML library of its own. If `kernel.yaml_io` wraps ruamel, it is already an allowed runtime dependency of the wheel; confirm before you rely on it, and never import `charter`.
- Over-strict tag regex: allow pre-release suffixes (`service-v0.1.0-rc1`).

## Review Guidance

- Every rule in the schema contract has a failing test, and the valid fixture passes on the same file.
- No import from `charter` or `specify_cli`; layer rules green.
- Messages never include a full digest or token-like string.

## Progress & Status

Record progress with `spec-kitty agent tasks add-history WP01 --note "..."`, and subtask completion with `spec-kitty agent tasks mark-status T001 --status done`.

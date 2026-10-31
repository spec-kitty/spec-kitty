---
work_package_id: WP03
title: Binary resolution and fail-closed refusals
dependencies:
- WP02
requirement_refs:
- FR-004
- FR-005
- FR-011
- SC-002
- SC-003
planning_base_branch: issue-6590-pinned-service-binaries
merge_target_branch: issue-6590-pinned-service-binaries
branch_strategy: Planning artifacts for this mission were generated on issue-6590-pinned-service-binaries. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6590-pinned-service-binaries unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-pinned-service-binaries-01M64N66
base_commit: 24386f27b3f17b60e3504b2ae18153fff320889e
created_at: '2026-10-29T22:58:23.834305+00:00'
subtasks:
- T011
- T012
- T013
- T014
- T015
phase: Phase 2 - Resolve and launch
history:
- at: '2026-10-29T21:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/services/
create_intent:
- src/specify_cli/services/__init__.py
- src/specify_cli/services/errors.py
- src/specify_cli/services/host.py
- src/specify_cli/services/resolution.py
- tests/specify_cli/services/__init__.py
- tests/specify_cli/services/test_resolution.py
- tests/specify_cli/services/test_host.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/services/__init__.py
- src/specify_cli/services/errors.py
- src/specify_cli/services/host.py
- src/specify_cli/services/resolution.py
- tests/specify_cli/services/__init__.py
- tests/specify_cli/services/test_resolution.py
- tests/specify_cli/services/test_host.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Binary resolution and fail-closed refusals

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` (`spec-kitty agent tasks status`) and address every item. Record your changes with `spec-kitty agent tasks add-history WP03 --note "..."`.

---

## Objectives & Success Criteria

- `resolve_binary(service, *, repo_root, …) -> ResolvedBinary` picks verified bytes in this fixed order, or raises a `ServiceRefusal` with a code and a concrete remedy (FR-004, FR-005):
  1. explicit path;
  2. install-provided slot;
  3. cached or fetched native asset for the host target;
  4. verified JVM jar with Java ≥ 25;
  5. refusal.
- Developer opt-in (FR-011): `SPEC_KITTY_SERVICE_UNPINNED=1` is honoured **only** with an explicit path, and returns `pinned=False` plus a warning string the launcher prints on every start.
- `verify_before_exec(resolved)` re-hashes the exact file to run, immediately before spawn (NFR-003, research R-3).
- Acceptance tests cover every tier and every refusal of spec User Story 2 and User Story 5.

## Context & Constraints

- Read: `spec.md` (US2, US5, FR-004, FR-005, FR-011, edge cases), `data-model.md` (ResolvedBinary, ServiceRefusal, ServiceTarget), `contracts/cli-surface.md` (environment variables), `research.md` R-3 and R-6.
- Build on WP02 (`kernel.service_artifacts`, `kernel.release_assets`) and WP01 (`kernel.service_pin`). Import their error codes; do not redefine them.
- **No Python fallback writer**, anywhere. Resolution either returns a verified binary or refuses.
- The **install-provided slot** is a hook for a future companion wheel (ADR 2026-10-29-1 D-4). Implement it as `importlib.metadata.entry_points(group="spec_kitty.service_binaries")`, where an entry point maps the service name to a callable returning a path. Nothing registers one today. The returned path must still match the pin's digest for the host target.
- `pins/<service>.source.yaml` is looked up under `repo_root` for a source checkout. For an installed wheel the pins ship as package data. The exact location is settled in WP06 (packaging): add one function, `find_pin(service) -> Path | None`, that tries the checkout path first and then `importlib.resources` for an installed `pins/` resource. Coordinate the name with WP06 through the shared constant `kernel.service_pin.PINS_DIR`.
- The CLI's error shape: subclass `specify_cli`'s `StructuredError` (see `src/specify_cli/status/write_service_protocol.py::EndpointFileError` for the pattern with `error_code`).

## Branch Strategy

- **Planning base / merge target**: `issue-6590-pinned-service-binaries`. Worktree per lane: `spec-kitty agent action implement WP03 --agent claude --mission pinned-service-binaries-01M64N66`.

## Subtasks & Detailed Guidance

### Subtask T011 – `errors.py`

- **Steps**: `class ServiceRefusalCode(enum.StrEnum)` with `BINARY_MISSING = "SERVICE_BINARY_MISSING"`, `DIGEST_MISMATCH = "SERVICE_BINARY_DIGEST_MISMATCH"`, `UNSUPPORTED_PLATFORM = "SERVICE_UNSUPPORTED_PLATFORM"`, `UNHEALTHY = "SERVICE_UNHEALTHY"`, `VERSION_MISMATCH = "SERVICE_VERSION_MISMATCH"`, `PIN_INVALID = "SERVICE_PIN_INVALID"`. Then `class ServiceRefusal(StructuredError)` with `code`, `message` and `remedy`, and `__str__` rendering `"{message}\nRemedy: {remedy}\nError code: {code}."`. Build the remedies from a single table (S1192: hoist repeated strings):
  - missing → "run `spec-kitty service fetch` while online, or set SPEC_KITTY_SERVICE_ASSET_DIR to a directory holding <asset>";
  - digest → "delete <path> and run `spec-kitty service fetch`; if it persists, the release or your mirror does not match the pin";
  - unsupported → "install a Java 25 runtime (JAVA_HOME) to use the pinned jar, or run on one of: <targets>";
  - unhealthy → "see <gcd>/spec-kitty-write-service/service.log; then `spec-kitty service stop` and retry";
  - version → "upgrade spec-kitty or stop the running service (`spec-kitty service stop`)";
  - pin invalid → "this spec-kitty version has no pin for <service> yet" (missing file) or "re-run `spec-kitty service vendor`" (malformed).
  Never include a token.

### Subtask T012 – `host.py`

- **Steps**:
  - `host_target() -> ServiceTarget | None` maps `(platform.system(), platform.machine().lower())` as follows: `Linux` + `x86_64|amd64` → linux-x64; `Linux` + `aarch64|arm64` → linux-arm64; `Darwin` + `arm64` → macos-arm64; `Windows` + `amd64|x86_64` → windows-x64; anything else → `None`. Inject the system and machine for tests through optional parameters.
  - `find_java(min_major: int = 25) -> Path | None`: try `JAVA_HOME/bin/java[.exe]` first, then `shutil.which("java")`. Run `java -version` with a 10 s timeout and parse stderr (`version "25.0.2"`, `"25"`, or `1.8.0_x`, which is major 8). Return the path only when major ≥ `min_major`. Cache the result per process.
- **Files**: `host.py` (~80 lines), `tests/specify_cli/services/test_host.py`. Use a fake `java` script in a temp dir on POSIX; skip the exec part on Windows.

### Subtask T013 – `resolution.py`

- **Steps**:
  1. `@dataclass(frozen=True) class ResolvedBinary: argv_prefix: tuple[str, ...]; path: Path; source: Literal["explicit","install","cache","jar","unpinned"]; sha256: str; pinned: bool; warning: str | None`.
  2. `resolve_binary(service: str, *, repo_root: Path | None, env: Mapping[str,str] = os.environ, offline: bool = False, cache_root: Path | None = None) -> ResolvedBinary`:
     - load the pin through `find_pin`; missing or invalid → `PIN_INVALID`;
     - **explicit**: `SPEC_KITTY_<SERVICE>_BINARY`, where the service name is uppercased with `-` → `_` (`WRITE_SERVICE`). The file must exist. Its digest must equal the host-target asset's digest or the jar's digest; with the jar's, argv is `java -jar`, which requires a Java runtime. Otherwise `DIGEST_MISMATCH`, unless the opt-in applies (T014);
     - **install**: the entry-point slot, digest-checked the same way;
     - **cache**: when `host_target()` has an asset in the pin, `fetch_asset(pin, asset, offline=offline, cache_root=cache_root)`. Map `ServiceArtifactError` codes onto refusals;
     - **jar**: when there is no host asset, or the host asset is unavailable (`SERVICE_BINARY_MISSING`) and the pin has a `jvm` asset and `find_java()` returns a path: fetch the jar and set argv `(java, "-jar", jar)`;
     - **refusal**: no host target and no usable jar → `UNSUPPORTED_PLATFORM`; host asset unavailable with no jar → `BINARY_MISSING`.
     Keep each tier in its own small function, so the dispatcher stays ≤ 15 complexity.
  3. `verify_before_exec(resolved: ResolvedBinary) -> None`: when `pinned`, re-hash `resolved.path` and raise `DIGEST_MISMATCH` if it changed. With the opt-in, do nothing.
  4. The protocol check is pin-level: when `pin.protocol_versions` does not intersect `write_service_protocol.SUPPORTED_PROTOCOL_VERSIONS`, raise `VERSION_MISMATCH` before any fetch (only for `write-service`).

### Subtask T014 – Unpinned opt-in

- **Steps**: when an explicit path exists **and** `env.get("SPEC_KITTY_SERVICE_UNPINNED") == "1"` and the digest matches no pin asset, return `ResolvedBinary(source="unpinned", pinned=False, warning="Running an UNPINNED <service> binary at <path> (SPEC_KITTY_SERVICE_UNPINNED=1). This build is not verified against the pin.")`. The opt-in without an explicit path changes nothing. Any value other than `"1"` is ignored, and a test pins that. The CLI's own tests and CI never set it; document that in the module docstring.

### Subtask T015 – Acceptance tests

- **Steps**: in `tests/specify_cli/services/test_resolution.py`, use `tests/kernel/service_release_fixture.build_release` (WP02) and a monkeypatched `host_target` and `find_java`. Cover:
  - each tier selected when only it is available (explicit, install via a monkeypatched entry point, cache, jar);
  - US2 acceptance 1: offline with an empty cache → `SERVICE_BINARY_MISSING`, and the remedy names `spec-kitty service fetch` and `SPEC_KITTY_SERVICE_ASSET_DIR`;
  - US2 acceptance 2: a corrupt asset → `SERVICE_BINARY_DIGEST_MISMATCH`, and nothing executed. Assert that no subprocess was spawned by monkeypatching `subprocess.Popen` to fail;
  - US2 acceptance 3: unknown host with no Java → `SERVICE_UNSUPPORTED_PLATFORM`; with Java 25 → the jar;
  - pin protocol `[2]` → `SERVICE_VERSION_MISMATCH`;
  - missing pin → `SERVICE_PIN_INVALID` with the "no pin yet" remedy;
  - US5: an explicit path whose digest matches nothing → `DIGEST_MISMATCH`; with the opt-in → unpinned with a warning; the opt-in without a path → normal resolution; a non-`1` value is ignored;
  - `verify_before_exec`: modify the cached file after resolve → `DIGEST_MISMATCH`.
  Mark `fast`.

## Test Strategy

```bash
uv run --frozen pytest -q tests/specify_cli/services/test_resolution.py tests/specify_cli/services/test_host.py
uv run --frozen pytest -q tests/architectural/test_layer_rules.py tests/architectural/test_release_asset_download_owner.py
uv run --frozen ruff check src/specify_cli/services tests/specify_cli/services
uv run --frozen ruff format --check --force-exclude <changed files>
uv run --frozen mypy src/specify_cli/services
```

## Risks & Mitigations

- `java -version` can be slow. It is called only on the jar path, and cached.
- A dead-symbol gate (`tests/architectural/test_no_dead_modules.py`) may flag public symbols nothing imports yet. WP04 and WP05 consume them in the same mission; if the gate runs per WP, add the usage in your own tests, and never add an allowlist entry without an issue, owner and drain date.

## Review Guidance

- The refusal tests assert that no process ever runs unverified bytes.
- The opt-in only works with an explicit path, and it warns.
- No refusal message or remedy leaks a token or a full environment dump.

## Progress & Status

`spec-kitty agent tasks add-history WP03 --note "..."`; `spec-kitty agent tasks mark-status T011 --status done`.

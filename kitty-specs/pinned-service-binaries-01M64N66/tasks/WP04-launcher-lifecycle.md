---
work_package_id: WP04
title: Launcher lifecycle
dependencies:
- WP03
requirement_refs:
- FR-006
- FR-007
- FR-008
- FR-009
- NFR-001
- NFR-002
- NFR-005
- NFR-006
- C-006
- C-007
- SC-001
planning_base_branch: issue-6590-pinned-service-binaries
merge_target_branch: issue-6590-pinned-service-binaries
branch_strategy: Planning artifacts for this mission were generated on issue-6590-pinned-service-binaries. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6590-pinned-service-binaries unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-pinned-service-binaries-01M64N66
base_commit: 6f94b75785ef97d251650da12db3fa7194e461b7
created_at: '2026-10-30T00:18:13.815768+00:00'
subtasks:
- T016
- T017
- T018
- T019
- T020
- T021
phase: Phase 2 - Resolve and launch
history:
- at: '2026-10-29T21:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/services/launcher.py
create_intent:
- src/specify_cli/services/client.py
- src/specify_cli/services/policies.py
- src/specify_cli/services/launcher.py
- tests/specify_cli/services/fake_service.py
- tests/specify_cli/services/test_launcher.py
- tests/specify_cli/services/test_client.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/services/client.py
- src/specify_cli/services/policies.py
- src/specify_cli/services/launcher.py
- tests/specify_cli/services/fake_service.py
- tests/specify_cli/services/test_launcher.py
- tests/specify_cli/services/test_client.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Launcher lifecycle

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` (`spec-kitty agent tasks status`) and address every item. Record your changes with `spec-kitty agent tasks add-history WP04 --note "..."`.

---

## Objectives & Success Criteria

- `ServiceLauncher.ensure(service, repo_root) -> WriteServiceEndpoint` returns a healthy, identity-checked endpoint:
  - it reuses a published, healthy instance (FR-006, FR-007);
  - it replaces a stale one (FR-008);
  - it starts a new one from the verified binary resolved by WP03, following the launch contract exactly;
  - after the start budget, it stops the process and refuses `SERVICE_UNHEALTHY` (NFR-002).
- `ServiceLauncher.stop(service, repo_root)` follows the contract's stop sequence (FR-009).
- The warm path costs at most 150 ms p95 (NFR-001): read the endpoint, then one handshake plus one health call, with no hashing and no spawn.
- The token is never logged or printed. The directory the launcher creates is owner-only (NFR-005).

## Context & Constraints

- **Binding contract:** `kitty-specs/pinned-service-binaries-01M64N66/contracts/launch-contract.md`, accepted by the spec-kitty-events operator on 2026-10-29. Implement it exactly. Do not invent flags.
- Reuse, do not redefine, the protocol shapes in `src/specify_cli/status/write_service_protocol.py`: `read_endpoint_file`, `endpoint_file_path`, `EndpointFileError`, `Handshake.from_wire`, `Health.from_wire`, `negotiate_protocol_version`, `repository_id`, `WRITE_PROTOCOL_HEADER`, `ENDPOINT_DIRECTORY`. Those symbols are currently priced dead-symbol debt (`category_c_write_service_client_6675` in `tests/architectural/dead_symbol_allowlist.yaml` / `_baselines.yaml`). Using them here may drain entries. Run `tests/architectural/test_no_dead_modules.py` and remove only the entries your change makes stale, as the gate's own message instructs.
- Loopback HTTP to `127.0.0.1` is intentional; do not force HTTPS (CLAUDE.md, Sonar section). Use `http.client.HTTPConnection(host, port, timeout=…)` from the standard library. `specify_cli` may use httpx, but stdlib keeps the warm path free of import cost; choose stdlib and say so in a comment.
- Git common dir: resolve it through the existing kernel helper. Grep `git_common_dir` in `src/kernel/` (for example `kernel.git_topology`) and use that resolver. Do not shell out to git yourself if a helper exists.
- Spawn (research R-5): POSIX `start_new_session=True`; Windows `creationflags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW`. Use `stdin=DEVNULL`, and send stdout and stderr to the appended `service.log`. Call `verify_before_exec(resolved)` immediately before `Popen`.

## Branch Strategy

- **Planning base / merge target**: `issue-6590-pinned-service-binaries`. `spec-kitty agent action implement WP04 --agent claude --mission pinned-service-binaries-01M64N66`.

## Subtasks & Detailed Guidance

### Subtask T016 – `fake_service.py`

- **Purpose**: a stand-in for the real `command-cli`, written to the contract, so the launcher is tested end to end.
- **Steps**: an executable Python script (with a shebang; tests run it as `[sys.executable, fake_service.py]` to stay portable) that:
  1. parses `serve --git-common-dir <abs> [--idle-timeout s]`, plus test-only behaviour switches read from environment variables such as `FAKE_SERVICE_MODE=healthy|never_ready|wrong_repo|wrong_protocol|exit_immediately|slow_start:<s>|ignore_shutdown`;
  2. creates `<gcd>/spec-kitty-write-service/` (0o700) and takes an exclusive lock on `service.lock` (`fcntl.flock` on POSIX, `msvcrt.locking` on Windows); exits 0 at once when the lock is held;
  3. binds `127.0.0.1:0` and mints a 32-byte URL-safe token and a ULID-like `instance_id`;
  4. writes `endpoint.json` (schema_version 1, host, port, token, instance_id, pid, protocol_versions, started_at) to a temp file, chmods it 0o600 and renames it into place;
  5. serves `GET /handshake` → `{"protocolVersions":[1],"serviceVersion":"fake","instanceId":…,"repositoryId": sha256(realpath(gcd))}`, `GET /health` → `{"status":"ready","instanceId":…}` and `POST /shutdown` → 202, then health reads `draining` and the process exits. Every route requires `Authorization: Bearer <token>` and returns 401 otherwise;
  6. idle timeout: exit after the idle seconds with no request;
  7. at exit, deletes `endpoint.json` only while it names its own `instance_id`.
  Mirror the real write format: read `write_service_protocol._endpoint_from` for the field names so `read_endpoint_file` accepts the file.

### Subtask T017 – `client.py`

- **Steps**: `class ServiceClient(endpoint: WriteServiceEndpoint, *, timeout: float = 2.0)` with `handshake() -> Handshake`, `health() -> Health` and `shutdown() -> None`. Each sends `Authorization: Bearer`, and `WRITE_PROTOCOL_HEADER` when the protocol requires it (check the ADR and the module). A connection error, timeout or non-2xx raises `ServiceUnreachable` (internal) without the token in the message. `test_client.py` tests it against the fake service.

### Subtask T018 – `policies.py`

- **Steps**: `@dataclass(frozen=True) class ServicePolicy: service: str; scope: Literal["git_common_dir","worktree"]; launchable: bool; start_args: Callable[[Path], list[str]]`. Define:
  - `WRITE_SERVICE` (scope `git_common_dir`, args `["serve", "--git-common-dir", str(gcd)]`);
  - `CHARTER_SERVICE` (scope `worktree`, args `["serve", "--worktree", str(path)]`, `launchable=False` until the charter seam work enables it);
  - `READ_SERVICE` (`launchable=False`; the CLI never launches it, C-007).
  `policy_for(service) -> ServicePolicy`. Launching a non-launchable policy is a programming error; raise `ValueError` naming ADR 2026-10-29-1 D-6.

### Subtask T019 – `launcher.py`

- **Steps**: `class ServiceLauncher` takes injectable seams for tests: clock, `spawn`, `resolve`, start timeout from `SPEC_KITTY_SERVICE_START_TIMEOUT` (default 15 s) and poll interval 0.05 s. `ensure(service, repo_root)`:
  1. compute the scope directory (git common dir);
  2. **try reuse**: read the endpoint file.
     - Missing → start.
     - Exposed, not loopback or malformed → re-raise `EndpointFileError` unchanged. Those are security refusals and are never auto-repaired.
     - Present → handshake: the repositoryId must equal `repository_id(gcd)` (otherwise `VERSION_MISMATCH`, "a service for another clone answered") and the protocol must negotiate (otherwise `VERSION_MISMATCH`). Then health must be `ready` with a matching `instance_id`. Unreachable → stale → start;
  3. **start**:
     - resolve (WP03);
     - create `<gcd>/spec-kitty-write-service/` with 0o700 when it is missing (never chmod an existing one);
     - append a start line (timestamp, binary path, sha256 prefix, `pinned`) to `service.log`;
     - print the resolution warning (unpinned) through the passed-in console;
     - `verify_before_exec`, then spawn;
  4. **wait for ready**: poll until the endpoint file appears and handshake plus health pass. When the spawned process exits with code 0 and a valid endpoint from another process exists, a concurrent starter won: reuse its endpoint. Once the budget is exceeded, stop the spawned process (T020) and raise `UNHEALTHY` with the log path.
  Keep the phases in separate methods, each ≤ 15 complexity.

### Subtask T020 – Stale recovery and stop

- **Steps**:
  - **Stale**: an endpoint whose pid is dead, or whose handshake fails. Start a new instance; the service's own lock decides the winner. Never delete `endpoint.json` yourself; it belongs to the service. The service deletes a stale file at its own start or exit. If a new service cannot publish because a dead process left the file behind, the contract has it overwrite by rename.
  - **Stop**: `stop(service, repo_root) -> StopOutcome` (`stopped`, `not_running`, `forced`):
    - read the endpoint, then `POST /shutdown`;
    - poll up to 10 s for the process to exit (`os.kill(pid, 0)` on POSIX; `OpenProcess` through `ctypes` on Windows, or psutil if it is already a dependency; check `pyproject`);
    - if the process is still alive **and** a handshake still reports the same `instance_id`, send SIGTERM (POSIX) or `TerminateProcess` (Windows) and return `forced`.
    Never signal a pid without confirming the instance identity first: pid reuse.

### Subtask T021 – Acceptance tests

- **Steps**: `tests/specify_cli/services/test_launcher.py`. Mark it `integration`; it spawns processes. Use the fixture release whose `linux-x64` (or the host target's) asset bytes are a tiny launcher script that execs `sys.executable fake_service.py "$@"`. Or monkeypatch `resolve` to return a `ResolvedBinary` with `argv_prefix=(sys.executable, fake_service.py)` and a pinned digest of that script; the launcher must still call `verify_before_exec`. Cover:
  - **US1-1:** an empty state starts, returns a healthy endpoint and leaves `service.log` written;
  - **US1-2:** a second `ensure` reuses; assert the spawn seam was called once;
  - **concurrency:** two threads call `ensure` at once; exactly one service process survives and both get the same `instance_id`;
  - **stale:** kill the service process, then `ensure` starts a fresh one with a new `instance_id`;
  - **unhealthy:** `FAKE_SERVICE_MODE=never_ready` with a 1 s budget → `SERVICE_UNHEALTHY`, and the spawned process is gone;
  - **mismatch:** `wrong_repo` → `SERVICE_VERSION_MISMATCH`; `wrong_protocol` → `SERVICE_VERSION_MISMATCH`;
  - **security:** a planted world-readable endpoint file → `WRITE_SERVICE_ENDPOINT_EXPOSED` (POSIX only), never connected to;
  - **stop:** after `ensure`, `stop` → `stopped`, the endpoint is gone and a later `ensure` starts anew; `ignore_shutdown` → `forced`;
  - **no token leak:** `caplog` and captured output contain no token value;
  - **NFR-001:** with an instance up, 20 warm `ensure` calls; assert p95 < 150 ms. Mark it `timing`, which the repository runs in its serial pass, so it is not flaky under xdist.
  Use short budgets and always clean up spawned processes in fixtures.

## Test Strategy

```bash
uv run --frozen pytest -q tests/specify_cli/services/test_client.py tests/specify_cli/services/test_launcher.py -m "not timing"
uv run --frozen pytest -q -n0 tests/specify_cli/services/test_launcher.py -m timing
uv run --frozen pytest -q tests/architectural/test_no_dead_modules.py tests/architectural/test_layer_rules.py
uv run --frozen ruff check src/specify_cli/services tests/specify_cli/services && uv run --frozen mypy src/specify_cli/services
```

## Risks & Mitigations

- Leaked background processes in CI: a fixture records spawned pids and kills them at teardown.
- Windows locking and spawning differ: skip POSIX-only assertions with explicit reasons. NFR-006 says Windows coverage runs in the Windows lane; mark the portable tests `windows_ci` only if the Windows lane selects by marker (check `ci-windows.yml`).
- Port binding races: the service binds port 0. The launcher never picks ports.

## Review Guidance

- Trace every exit of `ensure`: a healthy, identity-checked endpoint, or a named refusal. There is no path that returns an unverified endpoint.
- `verify_before_exec` runs immediately before every spawn.
- No signal is sent without an instance-identity check.

## Progress & Status

`spec-kitty agent tasks add-history WP04 --note "..."`; `spec-kitty agent tasks mark-status T016 --status done`.

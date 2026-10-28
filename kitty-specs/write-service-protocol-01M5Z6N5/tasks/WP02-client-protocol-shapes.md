---
work_package_id: WP02
title: Client-side protocol shapes, endpoint reader and binder
dependencies: []
requirement_refs:
- FR-015
- FR-016
- FR-017
- NFR-002
- NFR-003
- NFR-005
- C-001
- C-006
planning_base_branch: issue-6675-write-service-protocol
merge_target_branch: issue-6675-write-service-protocol
branch_strategy: Planning artifacts for this mission were generated on issue-6675-write-service-protocol. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6675-write-service-protocol unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
- T008
- T009
phase: Phase 1 - Foundation
history:
- at: '2026-10-27T18:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/write_service_protocol.py
create_intent:
- src/specify_cli/status/write_service_protocol.py
- tests/specify_cli/status/test_write_service_protocol.py
- tests/runtime/test_bind_event_bridge.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/status/write_service_protocol.py
- tests/specify_cli/status/test_write_service_protocol.py
- src/runtime/next/_internal_runtime/events.py
- tests/runtime/test_bind_event_bridge.py
- tests/architectural/dead_symbol_allowlist.yaml
- tests/architectural/test_no_dead_modules.py
- tests/architectural/_baselines.yaml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Client-side protocol shapes, endpoint reader and binder

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log and address every item before handing back.

## Objectives & Success Criteria

- Typed, standard-library-only shapes of the protocol in `specify_cli.status.write_service_protocol`
  (spec FR-015, FR-016; operator ruling `client_shape_scope`): protocol constants, the refusal code
  and reason vocabularies with the status of each code, request shapes with `to_wire()`, response
  shapes with `from_wire()`, version negotiation, the repository id, and the mapping from the port's
  `WorkPackageTransition` to a request unit.
- A fail-closed endpoint-file reader (NFR-002, NFR-003): refuses a missing, malformed,
  over-permissive, symlinked or non-loopback file, and never puts the token in an error or `repr`.
- `bind_event_bridge(*, emitter_factory, transition_port)` binds both port halves at once, all or
  nothing, beside `register_runtime_emitter_factory` (FR-017; issue comment item 1), plus a
  test-only `reset_event_bridge()`.
- No transport, no adapter bound, no CLI behaviour change (C-001).

## Context & Constraints

- The port: `src/runtime/next/event_bridge.py` (`WorkPackageTransition(write_location, rows,
  write_contract)`); the default adapter: `src/specify_cli/events/event_bridge.py`.
- The CLI write targets: `specify_cli.coordination.status_service.EventLogWriteTarget`
  (`primary_checkout_append`, `coordination_transaction_append`). Import it lazily or compare by
  value, so the module stays free of import cycles (issue comment item 2).
- Field names and the code table: `kitty-specs/write-service-protocol-01M5Z6N5/data-model.md`.
  The wire names are camelCase; the endpoint file is snake_case.
- Export convention: `__all__` lists only names another `src/` module imports, so the new module
  starts with `__all__: list[str] = []`. The dead-module gate then needs one priced entry (T009).
- ATDD-first: T005's failing tests are committed before T006-T008.

## Branch Strategy

- **Strategy**: single_branch (set by finalize-tasks)
- **Planning base branch**: issue-6675-write-service-protocol
- **Merge target branch**: issue-6675-write-service-protocol

Implementation command: `spec-kitty agent action implement WP02 --agent claude --mission write-service-protocol-01M5Z6N5`

## Subtasks & Detailed Guidance

### Subtask T005 – Failing tests

- `tests/specify_cli/status/test_write_service_protocol.py`:
  - every `WriteRefusalCode` has a status in `REFUSAL_STATUS` and every reason a code in
    `REASON_CODE`; reason URNs start with `urn:spec-kitty:write-refusal:`;
  - `TransitionUnit.to_wire()` gives `{"wpId", "rows", "context"}` with rows in order; an empty
    `rows` raises; `TransitionBatch` refuses 0 and more than 64 units;
  - `transition_unit_from(transition, checkout_root=..., repository_root=...)` maps
    `write_location` to a checkout-relative `missionDirectory`, the checkout to a
    repository-relative `checkout` (`.` for the root), the contract target to `writeSurface`
    (`primary_checkout_append` when the contract is `None`), and refuses a write location outside
    the checkout;
  - `DurabilityAck.from_wire` / `BatchDurabilityAck.from_wire` / `Handshake.from_wire` /
    `Health.from_wire` / `WriteRefusal.from_wire` accept the data-model shapes and raise
    `ProtocolShapeError` on a missing or mistyped field and on an unknown refusal code;
  - `negotiate_protocol_version((1, 2))` → `1` with `SUPPORTED_PROTOCOL_VERSIONS == (1,)`; no
    common major raises `ProtocolShapeError`;
  - `repository_id(path)` is the lowercase hex SHA-256 of the resolved path's string and is
    stable for a path and its symlink;
  - endpoint reader: a well-formed `0600` file in a `0700` directory reads; each refusal
    (`missing`, invalid JSON, wrong `schema_version`, `host` other than `127.0.0.1`, port out of
    range, short token, empty `protocol_versions`, file mode with a group/other bit, directory
    mode with a group/other bit, a symlinked file) raises `EndpointFileError` with the matching
    code; the token string never appears in `str(error)` or `repr(endpoint)`. Mark the POSIX
    mode tests `skipif(os.name == "nt")`.
- `tests/runtime/test_bind_event_bridge.py`: binds both halves; a conflicting second binder
  raises and leaves both halves unchanged (all or nothing); `reset_event_bridge()` clears both.
  Reset in a fixture so open-core's "binds no port" tests stay green.

### Subtask T006 – Protocol shapes

- File: `src/specify_cli/status/write_service_protocol.py`, standard library only.
- Constants: `WRITE_PROTOCOL_HEADER = "Spec-Kitty-Write-Protocol"`,
  `SUPPORTED_PROTOCOL_VERSIONS = (1,)`, `REASON_URN_PREFIX`, `MAX_BATCH_UNITS = 64`.
- `WriteRefusalCode(StrEnum)`: the 28 codes of the data model, verbatim. `REFUSAL_STATUS`:
  a `MappingProxyType` code → HTTP status. `PROTOCOL_ONLY_CODES`: the frozenset of minted codes.
- `WriteRefusalReason(StrEnum)`: the 15 reasons, with `.urn`; `REASON_CODE` reason → code.
- Frozen dataclasses: `RequestContext`, `TransitionUnit`, `TransitionBatch`, `AnnotationRequest`
  (each `to_wire()`), `DurabilityAck`, `BatchDurabilityAck`, `Handshake`, `Health`, `WriteRefusal`
  (each `from_wire()` classmethod), `ProtocolShapeError(ValueError)`.
- Keep each function at complexity ≤ 15; hoist repeated literals to constants (Sonar S1192).

### Subtask T007 – Endpoint reader

- `ENDPOINT_DIRECTORY = "spec-kitty-write-service"`, `ENDPOINT_FILE = "endpoint.json"`,
  `endpoint_file_path(git_common_dir)`, `WriteServiceEndpoint` (token field `repr=False`),
  `EndpointRefusalCode(StrEnum)` (`WRITE_SERVICE_ENDPOINT_MISSING`, `_MALFORMED`, `_EXPOSED`,
  `_NOT_LOOPBACK`), `EndpointFileError(code, message)`, `read_endpoint_file(path)`.
- `lstat` the file (refuse a symlink), check `st_mode & 0o077 == 0` for the file and its directory
  on POSIX, then read at most 64 KiB and parse. Windows: no mode check (owner-only ACL is the
  service's duty, documented in the ADR); the shape checks still apply.

### Subtask T008 – The binder

- In `src/runtime/next/_internal_runtime/events.py`, beside `register_runtime_emitter_factory`:
  `bind_event_bridge(*, emitter_factory, transition_port)` checks both halves for a conflict first
  and binds only when neither conflicts; `reset_event_bridge()` resets both. Add
  `bind_event_bridge` to `__all__`.

### Subtask T009 – Priced allowlist entries

- `tests/architectural/test_no_dead_modules.py`: allowlist `specify_cli.status.write_service_protocol`
  in the grandfathered-orphan category with a `# TODO(triage):` comment naming the exit (#6195 binds
  the client adapter).
- `tests/architectural/dead_symbol_allowlist.yaml`: add `bind_event_bridge` under
  `category_c_eventbridge_port_seam_6675` and update its rationale: it burns down when the client
  adapter binds at the #6195 cut-over. Raise the cap in `_baselines.yaml` by exactly the entries
  added, with a `# justification:` line.

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q tests/specify_cli/status/test_write_service_protocol.py tests/runtime/test_bind_event_bridge.py tests/specify_cli/events/test_event_bridge.py tests/architectural/test_runtime_emitter_seam.py tests/architectural/test_no_dead_modules.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_dead_symbol_allowlist_contract.py tests/architectural/test_layer_rules.py
uv run --frozen ruff check <files>; uv run --frozen ruff format --check --force-exclude <files>; uv run --frozen mypy <src files>
```

## Risks & Mitigations

- Import cycle: never import `specify_cli.coordination` at module level in the new module.
- Layer rules: `specify_cli` may import `runtime`, not the reverse; the binder stays in `runtime`.

## Review Guidance

- RED commit first; no transport; the token never reaches a message or `repr`; allowlist entries
  name #6195 as the exit.

## Progress & Status

Recorded through the status event log.

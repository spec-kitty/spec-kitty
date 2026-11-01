---
work_package_id: WP01
title: Call the write service under the contract's /api/v1 prefix
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-002
- C-001
- C-002
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6910-write-service-api-v1-prefix
merge_target_branch: issue-6910-write-service-api-v1-prefix
branch_strategy: Planning artifacts for this mission were generated on issue-6910-write-service-api-v1-prefix. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6910-write-service-api-v1-prefix unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Transport
history:
- at: '2026-11-01T15:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/services/
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/services/client.py
- src/specify_cli/services/launcher.py
- src/specify_cli/status/write_service_protocol.py
- tests/specify_cli/services/fake_service.py
- tests/specify_cli/services/test_client.py
- tests/contract/test_mission_write_contract.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Call the write service under the contract's /api/v1 prefix

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter before
parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

- `contracts/mission-write/openapi.yaml` declares `servers: [{url: /api/v1}]`; the client must
  therefore call `GET /api/v1/handshake`, `GET /api/v1/health` and `POST /api/v1/shutdown`.
- One prefix constant is the only place `/api/v1` appears in `src/`; every client path is derived
  from it.
- The launch-contract stand-in service answers exactly the contract's prefixed routes, so the
  pre-fix client fails against it (red-first proof) and the post-fix client passes.
- A contract test pins every path the client can send to `<contract server url>/<declared path>`,
  and its positive control shows a bare or doubled path is reported as non-conforming.
- A changelog entry under `[Unreleased]` names the user-visible impact.

Success: FR-001 … FR-004; NFR-001, NFR-002; C-001, C-002; SC-001 … SC-003.

## Context & Constraints

- Read `kitty-specs/write-service-api-v1-prefix-01M6BTXH/spec.md` and `research.md` first; the
  grounding evidence (contract lines, ruling, why the stand-in shadowed the drift) is there.
- `src/specify_cli/services/client.py` sends `/handshake` (line ~96), `/health` (~109) and
  `/shutdown` (~121); its module docstring repeats those bare paths.
- `src/specify_cli/status/write_service_protocol.py` is the CLI's typed view of
  `contracts/mission-write`; it already owns the protocol constants (`WRITE_PROTOCOL_HEADER`,
  `SUPPORTED_PROTOCOL_VERSIONS`, the endpoint-file constants). The path constants belong there.
- `tests/specify_cli/services/fake_service.py` is the stand-in service written to the launch
  contract; `tests/specify_cli/services/test_client.py` also keys a garbage handler on
  `self.path == "/handshake"`. `tests/specify_cli/services/test_launcher.py` and
  `test_service_cli.py` drive the same stand-in and must keep passing untouched.
- `tests/contract/test_mission_write_contract.py` already resolves the contract module into a
  `tree` fixture (`tree["servers"]`, `tree["paths"]`) and holds every contract-vs-client parity
  check. The pin goes there; do not create a second contract loader.
- Do **not** edit `contracts/mission-write/**`: the contract is the authority and the client
  conforms. ADR `2026-10-27-1` D-4 documents the operations relative to the server url.
- Do **not** add names to `write_service_protocol.__all__`: its members are a priced allowlist
  (`category_c_write_service_client_6675`) that burns down at #6195. Module-level constants
  imported by `services/client.py` are live for `test_no_dead_symbols` without `__all__`.
- Do **not** change request/response shapes, the refusal vocabulary, the endpoint file format,
  the launcher's behaviour, or bind the transition writes (#6195).

## Branch Strategy

- **Strategy**: planning artifacts were generated on `issue-6910-write-service-api-v1-prefix`;
  completed changes merge back into it. Execution worktrees are allocated per computed lane from
  `lanes.json`.
- **Planning base branch**: `issue-6910-write-service-api-v1-prefix`
- **Merge target branch**: `issue-6910-write-service-api-v1-prefix`

## Subtasks & Detailed Guidance

### T001 – Red first: the stand-in serves only the contract's routes

- **Purpose**: make the double obey the contract it claims to follow, and observe the unchanged
  client fail for the reason the real service would give.
- **Steps**: in `tests/specify_cli/services/fake_service.py`, serve `GET /api/v1/handshake`,
  `GET /api/v1/health`, `POST /api/v1/shutdown` and 404 everything else; the `ignore_shutdown`
  mode's mention of `/shutdown` in the docstring moves with it. In
  `tests/specify_cli/services/test_client.py`, key `_GarbageHandler.do_GET` on
  `"/api/v1/handshake"` so the "body outside the contract" case still reaches the handler.
- **Files**: `tests/specify_cli/services/fake_service.py`, `tests/specify_cli/services/test_client.py`.
- **Notes**: run `uv run --frozen pytest tests/specify_cli/services/test_client.py -q` here and
  record the failure: `ServiceUnreachable` mentioning `GET /handshake answered 404`. That output
  is the red-first evidence for the PR body. Do not fix the client in this subtask.

### T002 – One prefix, derived paths, and the client sends them

- **Purpose**: the contract's server url becomes the single source of truth.
- **Steps**: in `src/specify_cli/status/write_service_protocol.py` add, next to the other protocol
  constants, `API_PREFIX = "/api/v1"` and the three operation paths derived from it
  (`HANDSHAKE_PATH`, `HEALTH_PATH`, `SHUTDOWN_PATH`); comment that `API_PREFIX` equals the
  contract's `servers[0].url`. In `src/specify_cli/services/client.py`, import and use them in
  `handshake`, `health` and `shutdown` instead of the bare literals.
- **Files**: `src/specify_cli/status/write_service_protocol.py`, `src/specify_cli/services/client.py`.
- **Notes**: keep the failure messages useful — they interpolate the path, so
  `GET /api/v1/handshake answered 404` reads correctly. No new import beyond names already
  available through the `specify_cli.status` facade (or the module itself): the warm path must not
  gain a third-party import (NFR-001).

### T003 – The contract path pin

- **Purpose**: the drift cannot return. The client and the contract now agree *by construction* in
  production; the test proves it in CI.
- **Steps**: in `tests/contract/test_mission_write_contract.py` add a small helper that, given the
  resolved `tree` and a path, returns the reason the path does not conform (empty when it does):
  the path must be `tree["servers"][0]["url"] + <a declared path>` exactly. Then a test that
  asserts the helper is empty for each of `wsp.HANDSHAKE_PATH`, `wsp.HEALTH_PATH`,
  `wsp.SHUTDOWN_PATH`, that `wsp.API_PREFIX == tree["servers"][0]["url"]`, and that the set of
  paths the client can send is exactly the three `Service`-tagged contract paths (so a new client
  operation without a contract path fails). Add the positive control: the same helper reports a
  bare `/handshake` and a doubled `/api/v1/api/v1/health` as non-conforming.
- **Files**: `tests/contract/test_mission_write_contract.py`.
- **Notes**: the helper and its control must be one function (`architectural-gate-non-vacuity`);
  comparing with `startswith` alone would let the doubled prefix pass.

### T004 – Say the prefix where the code talks about the service

- **Purpose**: a reader of the module or its docstrings must not be told the wrong path.
- **Steps**: update the `src/specify_cli/services/client.py` module docstring and the three method
  docstrings; the `src/specify_cli/services/launcher.py` module docstring's ready/stop bullets;
  and the `tests/specify_cli/services/fake_service.py` header, to name `/api/v1/<operation>`.
- **Files**: `src/specify_cli/services/client.py`, `src/specify_cli/services/launcher.py`,
  `tests/specify_cli/services/fake_service.py`.
- **Notes**: docstrings only — no behaviour change in `launcher.py`. Keep the existing statements
  about the token, the protocol header and the no-chaining guarantee intact.

### T005 – Changelog

- **Purpose**: the fix is visible to operators.
- **Steps**: add an `[Unreleased]` entry in `docs/changelog/CHANGELOG.md` (root `CHANGELOG.md` is a
  symlink to it): bold impact-first lead with `(#6910)`, then before and after, under 1,200
  characters. Match the surrounding entries' section (`### Fixed` or the file's current
  convention — read the top of the file first).
- **Files**: `docs/changelog/CHANGELOG.md`.
- **Notes**: the impact statement is "the launcher can reach the resident write service again /
  for the first time", not "changed a string".

### T006 – Targeted tests, lint, types, self-review

- **Purpose**: prove the change and leave a record for the PR body.
- **Steps**: run the commands under **Test Strategy**; then re-read the diff for: a second
  `/api/v1` literal; a stale bare path in a docstring or test; the pin's positive control still
  calling the same helper; `git diff` limited to `owned_files`.
- **Files**: none (verification).
- **Notes**: never run a full heavy suite locally (`NO_FULL_HEAVY_SUITES_IN_MISSION`); CI owns
  that. Record exact commands and counts.

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/services/test_client.py -q
uv run --frozen pytest tests/specify_cli/services -q
uv run --frozen pytest tests/contract/test_mission_write_contract.py -q
uv run --frozen pytest tests/architectural/test_no_dead_symbols.py -q
uv run --frozen ruff check src/specify_cli/services src/specify_cli/status/write_service_protocol.py tests/specify_cli/services tests/contract/test_mission_write_contract.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/services/client.py src/specify_cli/services/launcher.py src/specify_cli/status/write_service_protocol.py tests/specify_cli/services/fake_service.py tests/specify_cli/services/test_client.py tests/contract/test_mission_write_contract.py
uv run --frozen mypy src/specify_cli/services/client.py src/specify_cli/status/write_service_protocol.py
```

Red-first evidence: the T001 run of `tests/specify_cli/services/test_client.py` against the
prefixed stand-in, with the pre-fix client, failing on the 404. Record it verbatim (counts and the
failure line) in the PR body.

## Risks & Mitigations

- **A pin that checks a prefix, not a path**: `/api/v1/api/v1/health` would pass. T003's control
  covers the doubled and the bare case with the same helper.
- **The stand-in is quietly loosened** (accepting both bare and prefixed routes): that would hide
  the defect the mission exists to fix. Serve only the prefixed routes.
- **A new dead symbol**: the constants must be imported by `services/client.py`, and `__all__`
  must not grow. T006 runs the gate.
- **False red from the shared machine**: if a gate fails outside this diff, reproduce on pristine
  `origin/main` before attributing it, and report it (`Pre-existing Failure Reporting Rule`).

## Review Guidance

- Does any code path still send a bare path, or does any docstring still claim one?
- Is `/api/v1` written once in `src/`, and is that constant equal to the contract's `servers` url
  as the contract test asserts?
- Does the stand-in service serve *only* the prefixed routes, and do the launcher/CLI test modules
  that use it still pass untouched?
- Is `contracts/mission-write/**` unmodified?
- Is the changelog entry impact-first, with `(#6910)`, under 1,200 characters?

## Progress & Status

Progress, history and status live in the status event log — never in this file.

- `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- `spec-kitty agent tasks move-task WP01 --to <status>`
- `spec-kitty agent tasks status`

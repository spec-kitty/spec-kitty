# Implementation Plan: Write service API prefix (`/api/v1`)

**Branch**: `issue-6910-write-service-api-v1-prefix` | **Date**: 2026-11-01 | **Spec**: `kitty-specs/write-service-api-v1-prefix-01M6BTXH/spec.md`
**Input**: Mission specification from `kitty-specs/write-service-api-v1-prefix-01M6BTXH/spec.md`

## Summary

The launcher's loopback client sends `/handshake`, `/health` and `/shutdown`; the
write-service contract (`contracts/mission-write/openapi.yaml`) declares
`servers: [{url: /api/v1}]`, so the real service answers on `/api/v1/*`. The fix defines
the prefix once in the client's typed contract view
(`specify_cli.status.write_service_protocol`), derives the three operation paths from it,
imports them in `specify_cli.services.client`, aligns the launch-contract stand-in service
with the same routes, and adds a contract test that pins every path the client can send to
`<contract server url>/<declared path>` with a positive control that a bare path fails.

Red first: the stand-in service moves to the prefixed routes and the unchanged client is
observed to fail with the 404 the real service would answer, then the client changes.

## Technical Context

**Language/Version**: Python 3.11 (repo `.python-version`, `uv sync --frozen --all-extras`)
**Primary Dependencies**: standard library only for the client (`http.client`, `json`); `pytest`, `pyyaml`, `jsonschema` for the tests
**Storage**: N/A (the client speaks loopback HTTP to the resident write service)
**Testing**: `uv run pytest` on the services and contract tiers; markers `integration` (client transport) and `contract`
**Target Platform**: POSIX and Windows (the file already carries one `windows_ci` smoke test)
**Project Type**: single project (Python package `src/specify_cli`)
**Performance Goals**: no change to the warm path — path strings stay module-level constants, no new import in `services/client.py`
**Constraints**: the contract is authoritative; no shapes, refusal vocabulary, endpoint file format or launcher behaviour changes; no full heavy suite locally (`NO_FULL_HEAVY_SUITES_IN_MISSION`)
**Scale/Scope**: 4 source files touched, 3 of them tests/stand-in; ~20 changed lines plus docstrings

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority**: `contracts/mission-write/openapi.yaml` is the authority for
  the path prefix; the client conforms. ✅
- **Locality of change (DIRECTIVE_024) / smallest viable diff**: changes stay in the client,
  the protocol view, the contract test and its stand-in service. ✅
- **ATDD-first / DIRECTIVE_034**: the failing test runs through the pre-existing entry point
  (`ServiceClient` against the stand-in service) before the fix. ✅
- **`__all__` convention (C-007)**: the protocol module's `__all__` is unchanged; the new
  path constants are public module-level constants with a cross-file `src/` importer
  (`services/client.py`), so `test_no_dead_symbols` stays green. ✅
- **Pre-existing Failure Reporting Rule**: any red outside this diff is reported, not hidden. ✅
- **External contracts stay external**: no edit to `contracts/mission-write/**`; the client
  is made to match it. ✅

## Project Structure

### Documentation (this mission)

```
kitty-specs/write-service-api-v1-prefix-01M6BTXH/
├── spec.md
├── research.md          # Phase 0 (discovery + grounding)
├── reasons-canvas.md
├── plan.md              # this file
├── tasks.md             # Phase 2
└── decisions/           # Decision Moments (none opened; see research.md)
```

### Source Code (repository root)

```
src/specify_cli/
├── status/write_service_protocol.py   # API_PREFIX + the three operation paths
└── services/client.py                 # sends the constants; docstrings name /api/v1

tests/
├── contract/test_mission_write_contract.py   # the path pin + positive control
└── specify_cli/services/
    ├── fake_service.py   # stand-in serves /api/v1/*, docstring states it
    └── test_client.py    # garbage handler keyed on the prefixed path
```

**Structure Decision**: single project; the existing package layout is kept, no new module.
The path constants live beside the other contract constants in the protocol module (its
docstring already calls it "the CLI's typed view" of `contracts/mission-write`).

## Complexity Tracking

No charter violations.

## Implementation Concern Map

### IC-01 — Prefixed client paths and the single prefix constant

- **Purpose**: make the client address the service exactly as the contract declares, with
  the prefix defined once so a future operation cannot escape it.
- **Relevant requirements**: FR-001, FR-002, NFR-001, C-001, C-002
- **Affected surfaces**: `src/specify_cli/status/write_service_protocol.py`,
  `src/specify_cli/services/client.py`
- **Sequencing/depends-on**: none
- **Risks**: adding a symbol to the protocol module without a cross-file `src/` importer
  would trip `test_no_dead_symbols`; the constants are imported by the client, so they are
  live. Keep `__all__` untouched to avoid the priced allowlist.

### IC-02 — Red-first proof and the contract path pin

- **Purpose**: make the stand-in service obey the contract so the old client fails, then
  keep the client honest with a contract test.
- **Relevant requirements**: FR-003, FR-004, SC-001, SC-002, SC-003, NFR-002
- **Affected surfaces**: `tests/specify_cli/services/fake_service.py`,
  `tests/specify_cli/services/test_client.py`,
  `tests/contract/test_mission_write_contract.py`
- **Sequencing/depends-on**: IC-01 (the pin imports the constants)
- **Risks**: the pin must compare whole paths, not prefixes, so a trailing-slash or doubled
  prefix fails; the positive control must exercise the same helper the real assertion uses,
  or it proves nothing (`architectural-gate-non-vacuity`).

# Work Packages: Write service API prefix (`/api/v1`)

**Inputs**: Design documents from `kitty-specs/write-service-api-v1-prefix-01M6BTXH/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md, reasons-canvas.md
**Issue**: [#6910](https://github.com/spec-kitty/spec-kitty/issues/6910)

**Tests**: required. This is a transport defect: the failing test runs red-first through the
pre-existing entry point (`ServiceClient` against the launch-contract stand-in service) before
the client changes, and a contract test keeps the paths pinned to the contract afterwards.

**Organization**: one work package. The whole change is one coherent slice (client paths, the
one prefix constant, the stand-in service that must match the contract, the pin, and the
changelog); splitting it would put the red-first proof and the fix in different review units.

**Prompt Files**: `/tasks/WP01-api-v1-client-paths.md`.

## Path Conventions

- Source: `src/specify_cli/…`; tests: `tests/…`; changelog: `docs/changelog/CHANGELOG.md`
  (root `CHANGELOG.md` is a symlink to it). `contracts/mission-write/**` is authoritative and is
  **not** edited by this mission.

---

## Work Package WP01: Call the write service under the contract's /api/v1 prefix (Priority: P0)

**Goal**: the launcher's loopback client addresses the write service exactly as
`contracts/mission-write/openapi.yaml` declares, the prefix is defined once, and a contract test
fails on any future path drift.
**Independent Test**: start the stand-in service (which serves only `/api/v1/*`), drive
`handshake`, `health` and `shutdown` through `ServiceClient` — all three succeed and the process
exits 0; then run the contract test and confirm that a bare `/handshake` is reported as
non-conforming while the three real paths pass.
**Prompt**: `/tasks/WP01-api-v1-client-paths.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002, C-001, C-002, SC-001, SC-002, SC-003

### Included Subtasks

T001 Red-first: serve only the contract's `/api/v1/*` routes from the stand-in service and observe the unchanged client fail with the service's 404
T002 Add `API_PREFIX` and the three operation path constants to `specify_cli.status.write_service_protocol`; send them from `specify_cli.services.client`
T003 Pin every client path to the resolved contract (`servers[0].url` + declared paths) with a positive control that a bare or doubled path fails
T004 State the prefix in the client, launcher and stand-in docstrings (no behaviour change)
T005 Changelog `[Unreleased]` entry for #6910
T006 Run the targeted tiers (services, contract), ruff and mypy; record the self-review

### Implementation Notes

- One prefix, one authority: `API_PREFIX = "/api/v1"` equals `servers[0].url` in the contract, and
  every client path is derived from it. Do not add a second literal.
- The new constants are public module-level constants with a cross-file `src/` importer
  (`services/client.py`), so `tests/architectural/test_no_dead_symbols.py` stays green. Leave
  `write_service_protocol.__all__` untouched (its members are a priced allowlist for #6195).
- The stand-in service is test infrastructure that claims to follow the launch contract; moving it
  to the prefixed routes makes the double **stricter**, never looser. It is part of the fix.
- Do not touch request/response shapes, the refusal vocabulary, the endpoint file format, the
  launcher's behaviour or the #6195 EventBridge binding.

### Parallel Opportunities

None: one file changes at a time in a single coherent slice.

### Risks

- A pin that checks `startswith(prefix)` passes a doubled prefix; compare the whole path.
- A positive control that re-implements the assertion proves nothing; it must call the same
  helper as the real test (`architectural-gate-non-vacuity`).
- The `windows_ci` smoke test in `test_client.py` shares the stand-in; keep it in the change so it
  cannot be left addressing the old routes.

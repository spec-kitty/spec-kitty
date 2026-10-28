# Implementation Plan: Mission Write API: CLI to write-service protocol

**Branch**: `issue-6675-write-service-protocol` | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/write-service-protocol-01M5Z6N5/spec.md`

## Summary

Add a contract module `contracts/mission-write/` (OpenAPI 3.1, `1.0.0-SNAPSHOT`) for the loopback
write service of ADR 2026-10-22-1. It defines six operations, a native bearer scheme and a refusal
vocabulary whose codes are today's CLI codes. A parity inventory and its test prove the codes
match the CLI source. The contract layout check gets a narrow amendment that admits root
`components.securitySchemes`. Typed client-side shapes and one composition-root binder are added
to the CLI, with no transport. ADR 2026-10-27-1 records the protocol and amends ADR 2026-10-22-1's
transport question and append-semantics clause.

## Engineering Alignment

The operator's rulings of 2026-10-25 (#6675) and 2026-10-27 (Decision Moments of this Mission)
settle every design choice below. Unruled protocol behaviour is a provisional proposal
(`x-provisional`), never a silent decision.

- **Service authoritative.** The contract describes refusals the service returns. A CLI
  pre-check is advisory, and the contract never says a client may skip a request because of it.
- **Durability.** One `O_APPEND` write of full JSON lines, `fsync` before the `201`. A batch is one
  write and one `fsync`, whole or nothing. Commit and cut join the unit at migration step 4; until
  then `statusCommit` is null.
- **Refusals.** The shared `Problem` (unchanged) with a `code` constant per refusal and a
  status fixed by the code. Guard refusals add a reason URN in `type`.
- **Identity and versions.** The integer protocol major travels in the `Spec-Kitty-Write-Protocol`
  header on every write. The handshake returns the supported majors and the instance id the
  endpoint file names.

## Technical Context

**Language/Version**: OpenAPI 3.1.0 (contract); Python 3.11+ (contract tools, client shapes, tests)
**Primary Dependencies**: the existing contract toolchain (`contracts/tools/*.py`, openapi-generator 7.25.0 under Gradle 8.14.5, vacuum 0.30.6, oasdiff 1.32.1); PyYAML and jsonschema for tests (already locked). No new dependency.
**Storage**: N/A (contract only). The endpoint file format is defined, not written.
**Testing**: pytest under `tests/contract/` (contract and parity tests), `tests/specify_cli/status/` (client shapes), `tests/runtime/` (binder); the contract checks as bare scripts; `make test-fast`.
**Target Platform**: Linux, macOS and Windows clients of a loopback service.
**Project Type**: single (repository tree).
**Performance Goals**: the new tests add under 10 s (NFR-004).
**Constraints**: C-001 to C-007 of the spec; `_shared/` untouched; no `-SNAPSHOT` release.
**Scale/Scope**: 6 path items, about 20 schemas, about 12 examples, 1 layout-check rule, 1 Python module, 1 binder, 1 ADR.

**Supply chain (DIRECTIVE_051)**: no dependency is added, upgraded or removed. The pinned
contract tools are reused as pinned. No adversarial supply-chain pass is needed.

## Charter Check

- **Single canonical authority**: refusal codes are reused, not re-minted; the event envelope
  stays owned by spec-kitty-events #92; `_shared/Problem` is reused. Pass.
- **Architectural alignment**: the module follows `contracts/README.md` conventions; the client
  shapes live under `specify_cli.status` (issue comment item 2: an adapter there avoids the
  status → events → coordination cycle). The binder sits beside `register_runtime_emitter_factory`.
  Pass.
- **ATDD-first**: each work package commits its failing acceptance test first. Pass by plan.
- **Architectural gate discipline (SO-5)**: two allowlist additions are priced debt with the
  #6195 exit (operator ruling `dead_gate_handling`). Recorded under Complexity Tracking.
- **Terminology**: Mission, status lane (`statusLane` in contract fields); no `feature` alias is
  introduced. The CLI's `feature_dir` is never echoed into the contract.
- **Credential handling (DIRECTIVE_050)**: no token value in an example, a refusal or an error
  text; the endpoint reader's errors never include the token.

## Project Structure

### Documentation (this mission)

```
kitty-specs/write-service-protocol-01M5Z6N5/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/README.md   # points at the real module, contracts/mission-write/
└── tasks.md              # /spec-kitty.tasks
```

### Source Code (repository root)

```
contracts/
├── README.md                                  # + "Security schemes" rule
├── mission-write/                             # NEW module
│   ├── openapi.yaml  CHANGELOG.md
│   ├── paths/  schemas/  parameters/  responses/  examples/
├── tools/layout_check.py                      # admit root components.securitySchemes only
└── tools/fixtures/
    ├── layout_check/{clean_security_scheme,v_components_beyond_security_schemes}/
    └── example_check/required_examples.json   # + "mission-write"
src/
├── specify_cli/status/write_service_protocol.py   # NEW typed shapes + endpoint reader
└── runtime/next/_internal_runtime/events.py       # + bind_event_bridge / reset_event_bridge
tests/
├── contract/test_mission_write_contract.py         # NEW contract acceptance + parity
├── contract/fixtures/mission_write_refusal_parity.yaml
├── contract/test_layout_check.py                   # + security-scheme cases
├── specify_cli/status/test_write_service_protocol.py
├── runtime/test_bind_event_bridge.py
├── architectural/dead_symbol_allowlist.yaml + test_no_dead_modules.py allowlist
docs/adr/4.x/2026-10-27-1-...md, docs/adr/4.x/index.md, docs/changelog/CHANGELOG.md
```

**Structure Decision**: single repository tree; the contract lives where the repository keeps
contracts (`contracts/<module>/`), the client shapes beside the status transition doors.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Dead-module allowlist entry for `specify_cli.status.write_service_protocol` | Operator chose typed shapes in `src/` now; their caller is the client adapter, bound at the #6195 cut-over | Shapes in `tests/` only was offered and declined |
| `bind_event_bridge` added to `category_c_eventbridge_port_seam_6675` | One binder for both halves (issue comment item 1); open-core binds none by design | Binding a do-nothing adapter to manufacture a caller is the anti-pattern the gate names |
| `layout_check` admits root `components.securitySchemes` | The bearer scheme must be native so generated clients send it (operator ruling) | Prose plus an `x-` extension was offered and declined |

## Implementation Concern Map

### IC-01 — Contract layout admits security schemes

- **Purpose**: let a module declare a native security scheme without opening the root to bundled components.
- **Relevant requirements**: FR-007, FR-008
- **Affected surfaces**: `contracts/tools/layout_check.py`, `contracts/tools/fixtures/layout_check/`, `tests/contract/test_layout_check.py`, `contracts/README.md`
- **Sequencing/depends-on**: none
- **Risks**: the generator's validation, the resolver and the Java view must accept the scheme; a fixture proves `components.schemas` beside it is still refused.

### IC-02 — The `mission-write` contract module and its parity inventory

- **Purpose**: the six operations, schemas, examples and changelog, plus the inventory and test that prove refusal-code parity.
- **Relevant requirements**: FR-001 to FR-006, FR-009 to FR-014, FR-018
- **Affected surfaces**: `contracts/mission-write/**`, `contracts/tools/fixtures/example_check/required_examples.json`, `tests/contract/test_mission_write_contract.py`, `tests/contract/fixtures/mission_write_refusal_parity.yaml`
- **Sequencing/depends-on**: IC-01
- **Risks**: citations must resolve to tracked code; enum-case lint forbids UPPER_SNAKE enums (use `oneOf` of `const`); leak scan forbids host paths and token-shaped values in examples; the five-path floor.

### IC-03 — Client-side shapes and the binder

- **Purpose**: typed request, response, refusal and endpoint shapes whose serialized examples validate against the contract, and one binder for both port halves.
- **Relevant requirements**: FR-015, FR-016, FR-017, NFR-002, NFR-003
- **Affected surfaces**: `src/specify_cli/status/write_service_protocol.py`, `src/runtime/next/_internal_runtime/events.py`, allowlists, their tests
- **Sequencing/depends-on**: IC-02
- **Risks**: the dead-module and dead-symbol gates (priced entries); the runtime import-cycle rule (`runtime.next.event_bridge` stays standard-library only).

### IC-04 — Decision record and documentation

- **Purpose**: record the protocol and amend ADR 2026-10-22-1; changelog entry.
- **Relevant requirements**: FR-019
- **Affected surfaces**: `docs/adr/4.x/2026-10-27-1-*.md`, `docs/adr/4.x/index.md`, `docs/adr/4.x/2026-10-22-1-*.md` (amendment pointer), `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-02
- **Risks**: the ADR index format and any ADR gate tests.

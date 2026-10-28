# Tasks: Mission Write API: CLI to write-service protocol

**Mission**: `write-service-protocol-01M5Z6N5` · **Branch**: `issue-6675-write-service-protocol` (planning base and merge target)
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [data-model.md](data-model.md), [research.md](research.md), [quickstart.md](quickstart.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Failing layout-check tests for a root security scheme (accepted) and other root components (refused) | WP01 | |
| T002 | Amend `layout_check.check_bundles` to admit only `components.securitySchemes` | WP01 | |
| T003 | Prove the resolver, bundle and generator validation keep the scheme (scratch module) | WP01 | |
| T004 | `contracts/README.md` "Security schemes" rule | WP01 | [P] |
| T005 | Failing tests for the client shapes, endpoint reader and binder | WP02 | |
| T006 | `specify_cli/status/write_service_protocol.py`: versions, codes, reasons, request/response shapes | WP02 | |
| T007 | Endpoint file reader with permission, loopback and shape refusals | WP02 | |
| T008 | `bind_event_bridge` / `reset_event_bridge` beside `register_runtime_emitter_factory` | WP02 | [P] |
| T009 | Priced dead-module and dead-symbol allowlist entries (exit #6195) | WP02 | |
| T010 | Failing contract acceptance and parity tests | WP03 | |
| T011 | Module root, path files, parameters and responses | WP03 | |
| T012 | Request and response schemas with citations | WP03 | |
| T013 | `WriteRefusal` vocabulary and the parity inventory fixture | WP03 | |
| T014 | Examples, `required_examples.json` entry and `CHANGELOG.md` (Provisional section) | WP03 | |
| T015 | Cross-validate the client shapes' serialized examples against the bundle | WP03 | |
| T016 | Run the whole contract check suite, Gradle validation included | WP03 | |
| T017 | ADR 2026-10-27-1: the write-service protocol | WP04 | |
| T018 | ADR index and the amendment pointer in ADR 2026-10-22-1 | WP04 | [P] |
| T019 | `docs/changelog/CHANGELOG.md` `[Unreleased]` entry | WP04 | [P] |

## Phase 1 — Foundation

### WP01 — Contract layout admits a root security scheme

**Goal**: a module can declare `components.securitySchemes` in its root document; any other root component is still a bundle (`TRACKED_BUNDLE`). **Priority**: P1. **Prompt**: [tasks/WP01-layout-security-schemes.md](tasks/WP01-layout-security-schemes.md)
**Independent test**: `tests/contract/test_layout_check.py` accepts a scheme-only root and refuses `components.schemas` beside it.

T001 Failing layout-check tests for a root security scheme (accepted) and other root components (refused) (WP01)
T002 Amend `layout_check.check_bundles` to admit only `components.securitySchemes` (WP01)
T003 Prove the resolver, bundle and generator validation keep the scheme (scratch module) (WP01)
T004 `contracts/README.md` "Security schemes" rule (WP01)

Dependencies: none. Risk: the generator or the Java view rejects the scheme; T003 finds out before WP03 depends on it.

### WP02 — Client-side protocol shapes, endpoint reader and binder

**Goal**: typed shapes of the protocol in the CLI, a fail-closed endpoint reader and one binder for both port halves; no transport. **Priority**: P1. **Prompt**: [tasks/WP02-client-protocol-shapes.md](tasks/WP02-client-protocol-shapes.md)
**Independent test**: `tests/specify_cli/status/test_write_service_protocol.py` and `tests/runtime/test_bind_event_bridge.py`.

T005 Failing tests for the client shapes, endpoint reader and binder (WP02)
T006 `specify_cli/status/write_service_protocol.py`: versions, codes, reasons, request/response shapes (WP02)
T007 Endpoint file reader with permission, loopback and shape refusals (WP02)
T008 `bind_event_bridge` / `reset_event_bridge` beside `register_runtime_emitter_factory` (WP02)
T009 Priced dead-module and dead-symbol allowlist entries (exit #6195) (WP02)

Dependencies: none (it can run beside WP01). Risk: import cycles (`runtime.next.event_bridge` stays standard-library only).

## Phase 2 — The contract

### WP03 — The `mission-write` contract module and refusal parity

**Goal**: the six operations, schemas, examples, changelog and the parity inventory, all passing every contract gate. **Priority**: P1. **Prompt**: [tasks/WP03-mission-write-contract.md](tasks/WP03-mission-write-contract.md)
**Independent test**: `tests/contract/test_mission_write_contract.py` plus every `contracts/tools/*.py` check over `contracts/`.

T010 Failing contract acceptance and parity tests (WP03)
T011 Module root, path files, parameters and responses (WP03)
T012 Request and response schemas with citations (WP03)
T013 `WriteRefusal` vocabulary and the parity inventory fixture (WP03)
T014 Examples, `required_examples.json` entry and `CHANGELOG.md` (Provisional section) (WP03)
T015 Cross-validate the client shapes' serialized examples against the bundle (WP03)
T016 Run the whole contract check suite, Gradle validation included (WP03)

Dependencies: WP01 (the scheme), WP02 (citations and cross-validation name its symbols).

## Phase 3 — Record

### WP04 — Decision record and changelog

**Goal**: ADR 2026-10-27-1 records the protocol and amends ADR 2026-10-22-1; the changelog names the change. **Priority**: P2. **Prompt**: [tasks/WP04-adr-and-changelog.md](tasks/WP04-adr-and-changelog.md)
**Independent test**: the ADR gate tests over `docs/adr/` pass; the ADR names every operator ruling and every provisional default.

T017 ADR 2026-10-27-1: the write-service protocol (WP04)
T018 ADR index and the amendment pointer in ADR 2026-10-22-1 (WP04)
T019 `docs/changelog/CHANGELOG.md` `[Unreleased]` entry (WP04)

Dependencies: WP03.

## Parallel opportunities and MVP

WP01 and WP02 are independent. WP03 needs both; WP04 needs WP03. The MVP is WP01 plus WP03 (a
validated contract); WP02 adds the client shapes and WP04 the record.

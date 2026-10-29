# Tasks: Charter CLI typed errors and JSON

**Mission**: `charter-cli-typed-errors-json-01M5ZC9Z` · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)
**Planning base / merge target**: `issue-6557-charter-cli-typed-errors-json`

Three work packages in a dependency chain. Activate/deactivate and status share no source file, but the
JSON enumeration gate (`tests/architectural/test_json_contract_enumeration.py`) is touched by both code WPs,
so WP02 follows WP01 (WP02 carries a recorded out-of-map edit to the gate for its `charter status` row).
Docs and CHANGELOG follow both.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Golden-text ratchet for activate/deactivate (direct + cascade outcomes) captured on the base | WP01 | |
| T002 | Tidy-first: extract `_activation_report.py` (report types) and build-then-render in activate/deactivate, byte-identical text | WP01 | |
| T003 | Failing acceptance tests for `--json` (success payloads, cascade report, refusals, exit parity) | WP01 | |
| T004 | Local error codes + `render_coded_error` for every activate/deactivate refusal | WP01 | |
| T005 | `--json` on positional activate and on deactivate: captured console, one payload | WP01 | |
| T006 | Snapshot tests of the payloads; enumeration gate: `charter activate` → ADOPTED, add `charter deactivate` ADOPTED | WP01 | |
| T007 | Failing tests for #6557 (unparseable / list-rooted / empty charter; text + JSON) | WP02 | |
| T008 | Status: soundness gate before the bundle check; canonical envelope + local codes for every error | WP02 | |
| T009 | Update existing status error tests to the canonical envelope (operator decision) | WP02 | |
| T010 | Failing tests for the activation block (ledger, legacy, required in_force) | WP02 | |
| T011 | `_collect_activation_status` + `activation` block in the status payload | WP02 | |
| T012 | Snapshot test of the block; enumeration gate: `charter status` → ADOPTED (out-of-map, recorded) | WP02 | |
| T013 | Document payloads, block and local codes in `docs/api/charter-commands.md` | WP03 | [P] |
| T014 | CHANGELOG `[Unreleased]` entry (incl. breaking status error envelope) | WP03 | [P] |
| T015 | Cross-check docs against snapshots and quickstart run | WP03 | |

## Phase 1 — Activate / deactivate

### WP01 – Activate/deactivate: report extraction and `--json` (#6525 local slice)

**Prompt**: [tasks/WP01-activate-deactivate-json.md](tasks/WP01-activate-deactivate-json.md)
**Goal**: positional `charter activate` and `charter deactivate` emit a versioned JSON change report with a
cascade report, and coded canonical errors; human output unchanged except `Error (<CODE>):` refusal lines.
**Priority**: P2 (US2) · **Requirements**: FR-004, FR-005, FR-006, FR-007, FR-008, FR-011, FR-012, NFR-001, NFR-003, NFR-004, C-001, C-005
**Independent test**: `pytest tests/specify_cli/cli/commands/charter/test_activation_json_6525.py tests/specify_cli/cli/commands/charter/test_activation_text_golden.py`

Included subtasks:

T001 Golden-text ratchet (WP01)
T002 Tidy-first report extraction (WP01)
T003 Failing JSON acceptance tests (WP01)
T004 Local codes + coded rendering (WP01)
T005 `--json` wiring (WP01)
T006 Snapshots + enumeration gate (WP01)

Sketch: golden text first (green on base) → refactor commit (golden still green) → red JSON tests commit →
implementation commits → snapshots + gate.
Dependencies: none. Risks: cascade output ordering drift (golden test guards it); `console.capture()` swallowing a refusal (render refusals outside the capture).

## Phase 2 — Status

### WP02 – Status: typed broken-charter refusal, canonical envelope, activation block (#6557, #6526 local slice)

**Prompt**: [tasks/WP02-status-typed-refusal-activation-block.md](tasks/WP02-status-typed-refusal-activation-block.md)
**Goal**: `charter status` refuses an unsound charter with `ACTIVE_CHARTER_CONFIG_INVALID`; all its errors use
the canonical envelope with local codes; `--json` carries the `activation` block.
**Priority**: P1 (US1) + P3 (US3) · **Requirements**: FR-001, FR-002, FR-003, FR-004, FR-009, FR-010, FR-011, FR-012, NFR-001, NFR-002, NFR-003, NFR-004, C-002, C-003, C-004, C-005, C-006
**Independent test**: `pytest tests/specify_cli/cli/commands/charter/test_status_broken_charter_6557.py tests/specify_cli/cli/commands/charter/test_status_activation_block_6526.py`

Included subtasks:

T007 Failing #6557 tests (WP02)
T008 Gate + envelope + codes in status (WP02)
T009 Update existing status error tests (WP02)
T010 Failing activation-block tests (WP02)
T011 Activation collector + payload (WP02)
T012 Snapshot + gate reclassification (WP02)

Dependencies: WP01 (shared enumeration gate file). Risks: existing consumers of the legacy status error envelope (operator accepted; CHANGELOG in WP03); activation read cost (NFR-002).

## Phase 3 — Docs

### WP03 – Documentation and CHANGELOG

**Prompt**: [tasks/WP03-docs-changelog.md](tasks/WP03-docs-changelog.md)
**Goal**: document the local schemas and codes, and announce the change (breaking status error envelope).
**Priority**: P3 · **Requirements**: FR-012, C-001, C-002, C-006
**Independent test**: docs examples match the WP01/WP02 snapshot files; quickstart runs as written.

Included subtasks:

T013 Document payloads/block/codes (WP03)
T014 CHANGELOG entry (WP03)
T015 Cross-check docs vs snapshots (WP03)

Dependencies: WP01, WP02.

## MVP

WP02's #6557 half (T007–T009) is the smallest shippable fix; WP01 is independent of it in substance.

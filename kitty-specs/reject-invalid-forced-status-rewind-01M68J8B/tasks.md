# Tasks: Reject invalid forced status rewinds before append

**Mission**: `reject-invalid-forced-status-rewind-01M68J8B` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)
**Branch**: planning base and merge target `main`

Three sequential work packages. WP01 is the MVP: on its own it closes #6514 for every
generic write door. WP02 pins the parity and the neighbouring ratchets. WP03 ships the
operator-facing position.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first CLI acceptance test: pointerless forced rewind through `agent status emit` | WP01 | |
| T002 | `REVIEW_REF_REQUIRED_EDGES` + `requires_review_ref()` in `status/wp_state.py` | WP01 | |
| T003 | `check_transition` enforces it force-insurmountably; keep the non-force message | WP01 | |
| T004 | `validate_event_schema` reads the shared predicate instead of its inline rule | WP01 | |
| T005 | Unit pins: force-insurmountable, whitespace-only, legal pointer, untouched edges | WP01 | |
| T006 | Red-first door-parity test: `orchestrator-api wp transition` refuses identically | WP02 | |
| T007 | Ratchet: `move-task`'s forced `for_review → in_progress` rewind still records | WP02 | |
| T008 | Ratchet: the other forced edges (`done`, `canceled`, `planned`, `for_review → planned`, `in_review`) unchanged | WP02 | |
| T009 | `docs/architecture/status-model.md`: guard row, refusal, append-only recovery position | WP03 | |
| T010 | `docs/changelog/CHANGELOG.md` `[Unreleased]` entry with `(#6514)` | WP03 | |
| T011 | Docs freshness + terminology gates | WP03 | [P] |

## WP01 — One requirement, enforced before the append (#6514)

**Prompt**: [tasks/WP01-shared-review-ref-requirement.md](tasks/WP01-shared-review-ref-requirement.md)
**Goal**: the `for_review → in_progress` `review_ref` requirement has one owning definition, and the write path enforces it before any append so a refusal leaves zero partial state. **Priority**: P1. **Independent test**: `pytest tests/status/test_forced_rewind_requires_review_ref.py`.
**Requirements**: FR-001, FR-002, FR-003, FR-005, FR-006, SC-001, SC-002, SC-003, SC-006, NFR-001, NFR-002, NFR-003, C-001, C-003.
**Dependencies**: none.

T001 Red-first CLI acceptance test (WP01)
T002 `REVIEW_REF_REQUIRED_EDGES` + `requires_review_ref()` (WP01)
T003 `check_transition` enforcement + message (WP01)
T004 `validate_event_schema` reads the shared predicate (WP01)
T005 Unit pins for the FSM edge set (WP01)

**Sketch**: red CLI test commit → predicate → `check_transition` ordering → auditor delegation → unit pins. **Risks**: changing the force-free refusal text; putting the check inside `guard_for` where force would bypass it.

## WP02 — Parity across the doors and the neighbouring contracts

**Prompt**: [tasks/WP02-door-parity-and-ratchets.md](tasks/WP02-door-parity-and-ratchets.md)
**Goal**: the second generic door refuses identically, and every conforming or unrelated forced edge is provably unchanged. **Priority**: P2. **Independent test**: `pytest tests/status/test_forced_rewind_door_parity.py`.
**Requirements**: FR-004, FR-007, FR-008, FR-009, SC-003, SC-004, SC-005, C-003.
**Dependencies**: WP01.

T006 Red-first door-parity test (WP02)
T007 Ratchet: `move-task` forced rewind (WP02)
T008 Ratchet: the other forced edges (WP02)

**Sketch**: red orchestrator-api test → confirm WP01 already makes it green (no per-door edit) → ratchets. **Risks**: a per-door patch that a future door bypasses; editing `tasks_transition_core.py` when it already conforms.

## WP03 — The operator-facing position

**Prompt**: [tasks/WP03-docs-and-changelog.md](tasks/WP03-docs-and-changelog.md)
**Goal**: the status reference states the force-insurmountable requirement and, honestly, what an operator may do about rows written before the fix. **Priority**: P3. **Independent test**: `uv run python -m scripts.docs.check_docs_freshness --ci` and a grep assertion on the page.
**Requirements**: FR-010, SC-006, C-002, C-004.
**Dependencies**: WP01.

T009 `docs/architecture/status-model.md` (WP03)
T010 changelog entry (WP03)
T011 Docs freshness + terminology gates (WP03)

**Sketch**: guard-table row → refusal paragraph → recovery position → changelog. **Risks**: documenting a repair the tool does not ship; regenerating the whole CLI reference (shared machine state, other agents rebuild it concurrently).

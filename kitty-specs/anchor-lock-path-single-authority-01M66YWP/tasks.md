# Tasks: One kernel helper for anchor-keyed lock paths

**Mission**: `anchor-lock-path-single-authority-01M66YWP` · **Issue**: #6727 · **Topology**: `coord`
**Planning/base branch**: `issue-6727-anchor-lock-paths` · **Merge target**: `issue-6727-anchor-lock-paths`

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first contract tests for `kernel.locks.anchored_lock_path` (module absent → red) | WP01 | |
| T002 | `anchored_lock_path` + `__all__` export in `src/kernel/locks.py` | WP01 | |
| T003 | Validation tests: unknown algorithm and out-of-range digest length raise `ValueError` | WP01 | |
| T004 | Fast-path and probe tests: `common_dir` runs no git probe; `probe_dir` is what is probed | WP01 | |
| T005 | Cross-family digest parity test (one anchor, `event-logs` vs `charter-synthesis`) | WP01 | |
| T006 | Red-first no-fourth-copy gate: `tests/architectural/test_anchor_lock_path_single_owner.py` | WP02 | |
| T007 | `event_log_lock_path` routed through the helper, fallback and refusal unchanged | WP02 | |
| T008 | `synthesis_lock_path` routed through the helper, fallback and refusal unchanged | WP02 | |
| T009 | `_checkout_claim_lock_path` routed through the helper with its degraded common dir | WP02 | |
| T010 | Docstrings: the two non-anchor-keyed status lock builders say why they do not use it | WP02 | |
| T011 | Docs: `event-ledger-writers-and-readers.md` and `lock-interop-spike.md` name the owner | WP02 | |

## WP01 — The helper and its pinned contract (P1)

**Goal**: one implementation of the anchored lock-path rule exists, with its behaviour fixed by
value before any caller moves (FR-001, FR-005, NFR-003, NFR-004, C-004).
**Independent test**: `tests/kernel/test_lock_paths.py` fails on the base commit (no
`kernel.locks.anchored_lock_path`) and passes after; the literal expected paths are computed
independently of the helper.
**Prompt**: [tasks/WP01-helper-and-contract.md](tasks/WP01-helper-and-contract.md)

T001 Red-first contract tests for `kernel.locks.anchored_lock_path` (WP01)
T002 `anchored_lock_path` + `__all__` export in `src/kernel/locks.py` (WP01)
T003 Validation tests: bad algorithm and digest length (WP01)
T004 Fast-path and probe tests (WP01)
T005 Cross-family digest parity test (WP01)

**Dependencies**: none. **Risks**: a parameter no caller uses (dead knob); a changed
`resolve`/`normcase`/digest order; the sha1 path needing `usedforsecurity=False`.

## WP02 — Route the three families, and gate the fourth copy (P1)

**Goal**: the event-log, charter synthesis and Mission checkout-claim locks call the helper and
produce byte-identical paths, and a reintroduced copy fails an architectural gate (FR-002,
FR-003, FR-004, FR-006, FR-007, FR-008, NFR-001, NFR-002, C-001, C-002, C-003).
**Independent test**: the four existing family suites are green with zero edits, and adding one
hand-rolled digest-and-join back into a family module turns the gate red.
**Prompt**: [tasks/WP02-route-families-and-gate.md](tasks/WP02-route-families-and-gate.md)

T006 Red-first no-fourth-copy gate (WP02)
T007 `event_log_lock_path` routed (WP02)
T008 `synthesis_lock_path` routed (WP02)
T009 `_checkout_claim_lock_path` routed (WP02)
T010 Docstrings for the non-anchor-keyed status locks (WP02)
T011 Docs name the owner (WP02)

**Dependencies**: WP01 (the helper and its contract). **Risks**: the status family's degrade must
keep never raising; `_is_checkout_claim_lock_key` pattern-matches the lock name; the gate must
not fire on the fixed-name `review/` and `design/` lock files.

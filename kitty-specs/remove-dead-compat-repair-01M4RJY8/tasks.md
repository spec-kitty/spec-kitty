# Work Packages: Remove dead #2985 compatibility-repair machinery (#6095)

**Inputs**: `kitty-specs/remove-dead-compat-repair-01M4RJY8/` — spec.md, plan.md, research/code-grounding.md, traces/
**Prerequisites**: spec.md, plan.md

**Tests**: behaviour-preserving removal. Per the tidy-first carve-out (Charter SO #2 /
`RECONCILE_CHANGE_SCOPE_TENSIONS`), the preserved contract is the already-green
end-state/idempotency coverage and gate greenness, not a new red-first test (ATDD-First
tension flagged in `traces/design-decisions.md` and the PR). Each WP records its exact test
commands + counts.

**Organization**: subtasks (`Txxx`) roll up into work packages (`WPxx`). Each WP has its own
prompt in `tasks/`. Single-branch topology: WPs run sequentially in the repository root checkout.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Remove `_plan_compatibility_repairs` + the repair-only helpers (`_runtime_repair_delta`, `_repair_scalar_value`, `_compatibility_repair_at`, `_repair_id`, `_stream_without_compatibility_repairs`, `_misaligned_seed_wps`) and `COMPATIBILITY_REPAIR_ACTOR` | WP01 | |
| T002 | Remove `_verify_compatibility_repairs`; fold out its call in `verify_backfill` keeping `_verify_expected_seed_events` + `_verify_claim_slot_witnesses` | WP01 | |
| T003 | Fold out the `_plan_compatibility_repairs` call in `_backfill_runtime_state_locked` (seeds flow straight to `seeded_count`) | WP01 | |
| T004 | Simplify `_is_migration_actor` (drop repair branch) and `_wp_events` (drop `include_seeds`); reword `_seed_row_mismatch` docstring; keep `_legacy_contract_carriers`/`_matches_legacy_contract`/`_LegacyCarrier` | WP01 | |
| T005 | mypy --strict + ruff on the changed file; `grep` confirms zero removed-symbol refs in `src/` | WP01 | |
| T006 | Delete the vacuous repair-assertion block in `test_birth_cutover.py`, keep every end-state/idempotency assertion | WP02 | |
| T007 | Prune the repair-actor-referencing machinery/notes in `test_backfill_runtime_state.py`, keep end-state assertions; `grep` confirms zero removed-symbol refs in `tests/` | WP02 | [P] |
| T008 | Run `tests/migration/` + `tests/unit/migration/` green | WP02 | |
| T009 | Run `test_no_dead_symbols.py` + `test_no_dead_modules.py` by name; re-point `_baselines.yaml`/other implicated gate honestly (shrink only, no loosening, no new allowlist) | WP03 | |
| T010 | Run `make test-fast`; record all commands + counts | WP03 | |

---

## Work Package WP01: Remove the repair machinery from src (Priority: P1)

**Goal**: The globally-unreachable #2985 compatibility-repair path no longer exists in
`backfill_runtime_state.py`; the module imports cleanly, is mypy/ruff clean, and no removed
symbol is referenced in `src/`. Behaviour for every real input is unchanged (planner always
returned `([], [])`).
**Independent Test**: `grep -rn` for the removed symbols in `src/` returns nothing; `mypy`
+ `ruff` clean; `python -c "import specify_cli.migration.backfill_runtime_state"` succeeds.
**Prompt**: `tasks/WP01-remove-repair-machinery.md`
**Requirement Refs**: FR-001, FR-002, FR-003, NFR-001, NFR-002, SC-001

### Included Subtasks

T001 Remove planner + repair-only helpers + actor (WP01)
T002 Remove `_verify_compatibility_repairs`; fold out of `verify_backfill` (WP01)
T003 Fold out of `_backfill_runtime_state_locked` (WP01)
T004 Simplify `_is_migration_actor`/`_wp_events`; keep live carriers (WP01)
T005 mypy/ruff/grep gate (WP01)

### Dependencies

- None.

---

## Work Package WP02: Prune repair-only tests, keep end-state coverage (Priority: P1)

**Goal**: Only the tests that exist solely to exercise the repair are removed; every
end-state / lane / slot / idempotency / cutover-correctness assertion is kept; no test
references a removed symbol; the owning test dirs pass.
**Independent Test**: `grep -rn` for removed symbols in `tests/` returns nothing;
`tests/migration/` + `tests/unit/migration/` pass.
**Prompt**: `tasks/WP02-prune-repair-tests.md`
**Requirement Refs**: FR-004, C-003, SC-001, SC-002

### Included Subtasks

T006 Drop the vacuous birth-cutover repair block (WP02)
T007 Prune repair-actor machinery/notes in the unit test (WP02)
T008 Run the owning test dirs green (WP02)

### Dependencies

- WP01.

---

## Work Package WP03: Prove the gates stay green honestly (Priority: P1)

**Goal**: The dead-symbol and no-dead-modules gates and any implicated baseline pass with
the symbols gone and with no loosening / no new allowlist entry; `make test-fast` is green.
**Independent Test**: `test_no_dead_symbols.py` + `test_no_dead_modules.py` pass by name;
`make test-fast` passes.
**Prompt**: `tasks/WP03-gates-green.md`
**Requirement Refs**: FR-005, C-002, SC-003

### Included Subtasks

T009 Dead-symbol / no-dead-modules gates + honest baseline re-point (WP03)
T010 `make test-fast` + record commands/counts (WP03)

### Dependencies

- WP01, WP02.

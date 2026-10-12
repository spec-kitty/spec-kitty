# Mission Specification: Remove dead #2985 compatibility-repair machinery (#6095)

**Mission Branch**: `issue-6095-dead-compat-repair`
**Created**: 2026-10-12
**Status**: Draft
**Input**: Tracker issue #6095 — "Dead code: the #2985 compatibility-repair path is globally unreachable under the 10.4.4 reducer" (priority:P3).

## Intent Summary (confirmed)

Since `spec-kitty-events` 10.4.4 (adopted in #6084, with #6058 folding old-seed claim
slots in the reducer), the #2985 compatibility-repair machinery in
`src/specify_cli/migration/backfill_runtime_state.py` can no longer mint a repair for any
input — empirically `repairs == []` for every repairable seed shape (grounding note
`research/code-grounding.md`). This mission removes that now-unreachable machinery and the
tests that exist only to exercise it, as a tidy-first, behaviour-preserving structural
change (Charter Standing Order 2, `DIRECTIVE_025`). It is **not** a bugfix: no input that
reaches the backfill today changes behaviour.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The backfill carries no dead repair path (Priority: P1, #6095)

As a maintainer of the runtime-state backfill, I want the globally-unreachable
compatibility-repair machinery gone so that the module carries only live code and the
dead-symbol / no-dead-modules architectural gates pass honestly.

**Why this priority**: The whole mission. The repair path mints nothing under 10.4.4, so it
is pure dead weight that misleads readers and future maintainers.

**Independent Test**: After removal, `grep -rn "COMPATIBILITY_REPAIR_ACTOR\|_plan_compatibility_repairs\|_verify_compatibility_repairs\|_runtime_repair_delta\|_compatibility_repair_at\|_misaligned_seed_wps\|_stream_without_compatibility_repairs" src/` returns nothing; the module imports cleanly and is mypy-clean.

**Acceptance Scenarios**:

1. **Given** events 10.4.4, **When** the module is imported and `grep`-ed, **Then** no removed repair symbol is referenced anywhere in `src/`.
2. **Given** the removal, **When** `mypy` and `ruff` run on the changed files, **Then** they pass with zero issues.

---

### User Story 2 - Backfill + cutover behaviour is unchanged (Priority: P1)

As an operator running a birth-cutover / runtime-state backfill, I want the end-state,
lane, runtime-slot and idempotency behaviour to be byte-for-byte unchanged by this cleanup.

**Why this priority**: Behaviour preservation is the contract of a tidy-first removal.

**Independent Test**: `tests/migration/test_birth_cutover.py` and
`tests/unit/migration/test_backfill_runtime_state.py` keep their end-state / lane / slot /
idempotency / cutover-correctness assertions and stay green before and after the removal.

**Acceptance Scenarios**:

1. **Given** the birth-cutover mixed mission, **When** `cutover_mission` runs, **Then** every WP lane, `shell_pid`, `agent`, `shell_pid_created_at` and the second-cutover byte-identical idempotency assertion hold exactly as before.
2. **Given** `verify_backfill`, **When** it runs, **Then** its live seed-presence and claim-slot parity guards still fail-closed on data loss (unchanged).

---

### User Story 3 - Only the repair-exercising tests are removed (Priority: P2)

As a reviewer, I want only the tests that exist solely to exercise the repair removed, with
every still-meaningful assertion kept, so coverage of real behaviour does not regress.

**Why this priority**: Over-deleting tests would silently drop live coverage.

**Independent Test**: No test references a removed symbol; the surviving birth-cutover and
backfill tests still pin the real behaviour and pass.

**Acceptance Scenarios**:

1. **Given** the test suite, **When** `grep` for removed symbols runs over `tests/`, **Then** no test references a removed symbol.
2. **Given** `tests/migration/` and `tests/unit/migration/`, **When** run, **Then** they pass.

### Edge Cases

- A WP still *flagged* misaligned (old-shape seed): verify still tolerates it via the live
  `_legacy_contract_carriers` path — behaviour unchanged; nothing is minted (there never was).
- A genuinely tampered seed: still a hard mismatch in `_verify_expected_seed_events` — the
  fail-closed guard is untouched.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Remove repair planner/minter + helpers | As a maintainer, I want `_plan_compatibility_repairs`, `_runtime_repair_delta`, `_repair_scalar_value`, `_compatibility_repair_at`, `_repair_id`, `_stream_without_compatibility_repairs`, `_misaligned_seed_wps` and `COMPATIBILITY_REPAIR_ACTOR` gone so the dead path no longer exists. | High | Open | [folded] | no — paired with the import-clean + grep-zero control |
| FR-002 | Fold out the two live call sites without behaviour change | As an operator, I want `_backfill_runtime_state_locked` and `verify_backfill` to stop calling the removed planner/verifier while seeding + verifying identically. | High | Open | [folded] | no — birth-cutover end-state + verify parity tests are the positive control |
| FR-003 | Keep live seed-tolerance + parity guards | As a reviewer, I want `_legacy_contract_carriers`, `_matches_legacy_contract`, `_LegacyCarrier`, `_verify_expected_seed_events`, `_verify_claim_slot_witnesses` and the simplified `_is_migration_actor` / `_wp_events` preserved. | High | Open | [folded] | no — verify fail-closed tests pin them |
| FR-004 | Prune only repair-exercising tests | As a reviewer, I want the vacuous birth-cutover repair block and the retired-note repair-actor machinery removed, every end-state assertion kept. | Medium | Open | [folded] | no — surviving tests must still pass |
| FR-005 | Gates pass honestly | As a maintainer, I want the dead-symbol / no-dead-modules gates and any implicated baseline to pass with the symbols gone and no loosening / no new allowlist entry. | High | Open | [ratchet] | no — the named gate files are the control |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Type + lint clean | Changed files pass `mypy --strict` and `ruff` with zero issues; complexity ≤ 15. | Quality | High | Open |
| NFR-002 | No reducer / events change | No change to `spec-kitty-events` or the Lamport reducer. | Architecture | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Events pinned at 10.4.4 | Removal is valid only while events resolves to 10.4.4 (verified). | Technical | High | Open |
| C-002 | No new ratchet/size gates | Operator ruling: re-point ratchets, never loosen, add no new size/length gate and no allowlist entry. | Technical | High | Open |
| C-003 | Immutable history untouched | Historical mission artifacts, red-first baselines and immutable snapshots referencing the old repair test name are left exactly as they are. | Technical | High | Open |

### Key Entities

- **Compatibility repair row**: the `COMPATIBILITY_REPAIR_ACTOR`-tagged event the removed
  path minted. Globally unreachable under 10.4.4; nothing on disk depends on one.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: No removed repair symbol is referenced in `src/` or `tests/` after the change (grep returns zero). — [folded] · no-op passable: no
- **SC-002**: `tests/migration/` and `tests/unit/migration/` pass, retaining every end-state / lane / slot / idempotency / cutover-correctness assertion. — [folded] · no-op passable: no
- **SC-003**: `tests/architectural/test_no_dead_symbols.py` and `tests/architectural/test_no_dead_modules.py` pass with the symbols gone and no loosening / no new allowlist entry. — [ratchet] · no-op passable: no

## Out of Scope / Cross-references

- The reducer and `spec-kitty-events` (external contract) — untouched.
- `#6071`/`#6073` consolidation regressions (lane_planning_data_loss, skip-lanes,
  coord-topology) — unrelated bugfix, not this mission.
- `Closes #6095`.

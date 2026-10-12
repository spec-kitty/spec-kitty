# Implementation Plan: Remove dead #2985 compatibility-repair machinery (#6095)

**Branch**: `issue-6095-dead-compat-repair` | **Date**: 2026-10-12 | **Spec**: `./spec.md`
**Input**: Mission specification from `kitty-specs/remove-dead-compat-repair-01M4RJY8/spec.md`

## Summary

Delete the globally-unreachable #2985 compatibility-repair path from
`src/specify_cli/migration/backfill_runtime_state.py` and the tests that exist only to
exercise it, following the dead-reference chain so nothing dangles. Behaviour-preserving:
the planner always returns `([], [])` under events 10.4.4 (grounded in
`research/code-grounding.md`), so folding out its two live call sites changes no output for
any real input. Keep the live seed-tolerance and fail-closed parity guards. Keep every gate
green by removing the dead symbols, never by loosening.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `spec-kitty-events` 10.4.4 (external contract, untouched)
**Storage**: append-only `status.events.jsonl` (unchanged)
**Testing**: pytest; `tests/migration/`, `tests/unit/migration/`, named architectural gate files
**Project Type**: single (CLI library)
**Constraints**: mypy --strict clean, ruff clean, complexity ≤ 15; no reducer/events change; events pinned 10.4.4 (C-001)
**Scale/Scope**: one module (~2512 lines) + two test files + gate re-point; ~9 symbols removed, 2 simplified, 2 call sites folded

## Charter Check

*GATE: Must pass before research. Re-check after design.*

- **Standing Order 2 (tidy-first / `DIRECTIVE_025`)**: PASS — this is the tidy-first,
  behaviour-preserving removal itself; no functional change rides along.
- **Standing Order 5 + Burn-down Policy (`DIRECTIVE_043`, ADR 2026-09-30-1)**: PASS by
  construction — dead symbols are removed so the dead-symbol gate passes honestly; any
  `_baselines.yaml` count is re-pointed (shrink WARNS, never FAILS), no loosening, no new
  allowlist entry, no new size/ratchet gate (C-002, operator ruling).
- **Standing Order 3 (tracer files)**: PASS — three tracer files seeded under `traces/`.
- **Canonical sources (`DIRECTIVE_044`)**: PASS — canonical CLI + templates used.
- **Shared Package Boundary**: PASS — `spec-kitty-events` untouched.
- **ATDD-First (C-011)**: flagged tension — a behaviour-preserving deletion has no new
  red-first test; the preserved contract is the already-green end-state/idempotency coverage
  plus gate greenness (tidy-first carve-out, `RECONCILE_CHANGE_SCOPE_TENSIONS`). Recorded in
  `traces/design-decisions.md` and surfaced in the PR.

## Project Structure

### Documentation (this mission)

```
kitty-specs/remove-dead-compat-repair-01M4RJY8/
├── spec.md
├── plan.md                      # this file
├── research/code-grounding.md   # proof-of-death + dead-reference chain
├── traces/                      # tooling-friction, approach, design-decisions
└── tasks.md                     # next phase
```

### Source Code (repository root)

```
src/specify_cli/migration/
└── backfill_runtime_state.py    # the only src file changed

tests/
├── migration/test_birth_cutover.py              # keep end-state; drop vacuous repair block
├── unit/migration/test_backfill_runtime_state.py # keep end-state; drop repair-actor machinery/notes
└── architectural/
    ├── test_no_dead_symbols.py                  # must pass with symbols gone
    ├── test_no_dead_modules.py                  # must pass (module keeps live callers)
    └── _baselines.yaml                          # re-point only if a count moves (shrink)
```

**Structure Decision**: Single project. One production file changes; two test files pruned;
architectural gates verified by name (never the bare directory, per `NO_FULL_HEAVY_SUITES_IN_MISSION`).

## Complexity Tracking

No Charter Check violations — none to justify. (The removal reduces module complexity.)

## Implementation Concern Map

### IC-01 — Remove the repair planner/minter and its exclusive helpers

- **Purpose**: Delete `_plan_compatibility_repairs` and every helper whose only callers are
  repair code, so the dead minting path no longer exists.
- **Relevant requirements**: FR-001, FR-002.
- **Affected surfaces**: `backfill_runtime_state.py` — `_plan_compatibility_repairs`,
  `_verify_compatibility_repairs`, `_misaligned_seed_wps`, `_runtime_repair_delta`,
  `_repair_scalar_value`, `_compatibility_repair_at`, `_repair_id`,
  `_stream_without_compatibility_repairs`, `COMPATIBILITY_REPAIR_ACTOR`; fold the call sites
  in `_backfill_runtime_state_locked` and `verify_backfill`; simplify `_is_migration_actor`
  and `_wp_events`.
- **Sequencing/depends-on**: none (first).
- **Risks**: must NOT remove `_legacy_contract_carriers`/`_matches_legacy_contract`/`_LegacyCarrier`
  (live via `_verify_expected_seed_events`) or any `_verify_claim_slot_witnesses` parity guard.

### IC-02 — Prune repair-only tests, keep end-state coverage

- **Purpose**: Remove only the assertions/tests that exercise the repair; keep every
  end-state / lane / slot / idempotency / cutover-correctness assertion.
- **Relevant requirements**: FR-004.
- **Affected surfaces**: `tests/migration/test_birth_cutover.py` (vacuous repair block),
  `tests/unit/migration/test_backfill_runtime_state.py` (repair-actor notes/machinery).
- **Sequencing/depends-on**: IC-01.
- **Risks**: over-deletion dropping live coverage; immutable historical snapshots must be left.

### IC-03 — Prove the gates stay green honestly

- **Purpose**: The dead-symbol / no-dead-modules gates and any implicated baseline pass with
  the symbols gone and no loosening.
- **Relevant requirements**: FR-005, SC-003.
- **Affected surfaces**: `tests/architectural/test_no_dead_symbols.py`,
  `test_no_dead_modules.py`, `_baselines.yaml`, and any other gate the grounding implicates.
- **Sequencing/depends-on**: IC-01, IC-02.
- **Risks**: a stale baseline count; re-point (shrink) honestly, never add an allowlist entry.

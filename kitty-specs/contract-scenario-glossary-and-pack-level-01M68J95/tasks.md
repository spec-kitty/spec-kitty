# Tasks: Contract Scenario glossary entry and the Pack Level "tier" wording

**Mission**: contract-scenario-glossary-and-pack-level-01M68J95
**Planning/base branch**: issue-6439-contract-scenario-glossary-and-pack-level · **Merge target**: issue-6439-contract-scenario-glossary-and-pack-level

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Author the guard module's entry slicer and positive controls | WP01 | |
| T002 | Assert the pack-level wording contract in both entries | WP01 | |
| T003 | Assert the Contract Scenario entry's required rows and guard | WP01 | |
| T004 | Observe the module red on the pre-fix tree and record the output | WP01 | |
| T005 | Lint and format the new module | WP01 | |
| T006 | Correct the Pack Level entry in `docs/context/governance.md` | WP02 | |
| T007 | Correct the same claim in the Charter Pack entry | WP02 | |
| T008 | Add the Contract Scenario entry beside Charter Pack | WP02 | |
| T009 | Regenerate the docs index and confirm the inventory is a no-op | WP02 | |
| T010 | Add the `[Unreleased]` changelog entry | WP02 | |
| T011 | Run the docs gates and record the results | WP02 | |

## WP01 — Red-first guard for both glossary claims

**Goal**: one docs-scoped test module that fails on the pre-fix tree for both halves of #6439 (the missing term and the "tier" wording) and passes once WP02 lands.
**Priority**: P1. **Independent test**: `pytest tests/docs/test_context_glossary_contract_scenario_and_pack_level.py -q` is red before WP02 (four failing assertions: missing entry, missing rows, "tier" in Pack Level, "tier" in Charter Pack) and green after.
**Prompt**: [tasks/WP01-glossary-wording-guard.md](tasks/WP01-glossary-wording-guard.md)

T001 Author the guard module's entry slicer and positive controls (WP01)
T002 Assert the pack-level wording contract in both entries (WP01)
T003 Assert the Contract Scenario entry's required rows and guard (WP01)
T004 Observe the module red on the pre-fix tree and record the output (WP01)
T005 Lint and format the new module (WP01)

**Implementation sketch**: T001 (slicer + fixtures + positive controls) → T002 (tier probes) → T003 (entry probes) → T004 (run red, save the output for the PR body) → T005 (`ruff check`, `ruff format --check`).
**Dependencies**: none. **Parallel opportunities**: none (one file).
**Risks**: a naive `tier` probe reds on `kernel.pack_tiers` — strip inline code spans first; an absence probe with no positive control can pass by reading nothing — assert the entry body and the authority name are present on the same fixture.

## WP02 — Correct the two entries, regenerate the index, add the changelog

**Goal**: `docs/context/` defines Contract Scenario beside Charter Pack, neither the Pack Level nor the Charter Pack entry calls a pack's level a "tier", the docs index is fresh, and the changelog records the change.
**Priority**: P1. **Independent test**: the WP01 module goes green; `check_docs_freshness --ci` reports `errors=0`; `make docs-lint` passes.
**Prompt**: [tasks/WP02-correct-entries-and-docs.md](tasks/WP02-correct-entries-and-docs.md)

T006 Correct the Pack Level entry in `docs/context/governance.md` (WP02)
T007 Correct the same claim in the Charter Pack entry (WP02)
T008 Add the Contract Scenario entry beside Charter Pack (WP02)
T009 Regenerate the docs index and confirm the inventory is a no-op (WP02)
T010 Add the `[Unreleased]` changelog entry (WP02)
T011 Run the docs gates and record the results (WP02)

**Implementation sketch**: T006 → T007 → T008 (three prose edits; T008 uses the wording fixed in `data-model.md`) → T009 (regenerate index, check inventory) → T010 (changelog) → T011 (gates).
**Dependencies**: WP01 (red-first: the guard must exist and be observed red before the prose changes).
**Parallel opportunities**: T006 and T008 touch different pages and could run in parallel; T009/T010 must follow the prose edits.
**Risks**: sweeping "tier" into Organization Tier or the Three-layer DRG entry (C-003); losing `kernel.pack_tiers` or the #6403 `PACK_LEVEL_MISSING` wording; regenerating the whole docs surface instead of the one index file.

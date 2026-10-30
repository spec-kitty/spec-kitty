# Tasks: Repoint the red-main references to the RED_MAIN_RELEASE_DISCIPLINE directive

**Mission**: `issue-6693-red-main-refs-to-directive-01M66YZX` · **Branch**: `issue-6693-red-main-refs-to-directive` (planning base and merge target)
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [occurrence_map.yaml](occurrence_map.yaml)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Vendor both pins to open-packs `72cb7dbc` and `make sync-packs` | WP01 | |
| T002 | Record the six red tests the bumped pin produces (red evidence, before any fix) | WP01 | |
| T003 | Repoint the curated `DIRECTIVE_030` edge to `directive:RED_MAIN_RELEASE_DISCIPLINE` | WP01 | |
| T004 | Prove regeneration is byte-identical to the shipped built-in graph | WP01 | |
| T005 | Repoint `test_single_owner_edges.py` (test-first-bug-fixing requires edge) | WP02 | |
| T006 | Repoint `test_extractor_projection.py` commentary and pinned inventories | WP02 | |
| T007 | Repoint `test_testing_doctrine_single_owner.py` expected reference set | WP02 | |
| T008 | Repoint `test_org_pack_chain_delivery.py` internal-pack refines edges | WP02 | |
| T009 | Repoint the `minimal_org_pack_2` fixture refines edge | WP02 | [P] |
| T010 | Write the red ledger-resolution guard test (fails on the un-repointed ledger) | WP03 | |
| T011 | Deactivate the procedure, activate the directive, drop the stale deny entry | WP03 | |
| T012 | Refresh the two standing-order pointers in `.kittify/charter/charter.md` | WP03 | [P] |
| T013 | Verify doctor/consistency-check/context report clean on the repointed ledger | WP03 | |
| T014 | `docs/changelog/CHANGELOG.md` `[Unreleased]` entry | WP03 | [P] |

## Phase 1 — Foundation

### WP01 — Vendor the pin and repoint the curated DRG edge

**Goal**: both packs are fetched from open-packs `72cb7dbc`, and graph regeneration mints no orphan `procedure:red-main-release-discipline` node. **Priority**: P1. **Prompt**: [tasks/WP01-vendor-pin-and-curated-edge.md](tasks/WP01-vendor-pin-and-curated-edge.md)
**Independent test**: `tests/charter_offering/drg/migration/test_extractor_projection.py::TestDRGZeroDelta` (both tests) passes at the bumped pin.

T001 Vendor both pins to open-packs `72cb7dbc` and `make sync-packs` (WP01)
T002 Record the six red tests the bumped pin produces (red evidence, before any fix) (WP01)
T003 Repoint the curated `DIRECTIVE_030` edge to `directive:RED_MAIN_RELEASE_DISCIPLINE` (WP01)
T004 Prove regeneration is byte-identical to the shipped built-in graph (WP01)

Dependencies: none. Risk: the four org-pack/pack-chain tests stay red in WP01 by design — they are WP02's subject; WP01 must not "fix" them by editing fetched content.

### WP02 — Repoint the five tests and the org-pack fixture

**Goal**: every test assertion and fixture edge names the directive the packs ship, with no assertion weakened and no count fudged. **Priority**: P1. **Prompt**: [tasks/WP02-repoint-tests-and-fixture.md](tasks/WP02-repoint-tests-and-fixture.md)
**Independent test**: the four test files named in the issue run green at the bumped pin.

T005 Repoint `test_single_owner_edges.py` (test-first-bug-fixing requires edge) (WP02)
T006 Repoint `test_extractor_projection.py` commentary and pinned inventories (WP02)
T007 Repoint `test_testing_doctrine_single_owner.py` expected reference set (WP02)
T008 Repoint `test_org_pack_chain_delivery.py` internal-pack refines edges (WP02)
T009 Repoint the `minimal_org_pack_2` fixture refines edge (WP02)

Dependencies: WP01. Risk: `test_extractor_projection.py` pins node/edge totals; update them only if the shipped graph actually changed, never to make a count pass.

## Phase 2 — The repository's own governance surface

### WP03 — Repoint the charter ledger, guard it, and record the change

**Goal**: this repository's own governed commands resolve cleanly against the new packs, a fast test guards that invariant, and the changelog tells consumers what to do. **Priority**: P1. **Prompt**: [tasks/WP03-charter-ledger-guard-and-changelog.md](tasks/WP03-charter-ledger-guard-and-changelog.md)
**Independent test**: `spec-kitty charter context --action implement` reports no catalog miss, `spec-kitty doctor charter-packs` reports no activation-ledger warning, and the new guard test passes.

T010 Write the red ledger-resolution guard test (fails on the un-repointed ledger) (WP03)
T011 Deactivate the procedure, activate the directive, drop the stale deny entry (WP03)
T012 Refresh the two standing-order pointers in `.kittify/charter/charter.md` (WP03)
T013 Verify doctor/consistency-check/context report clean on the repointed ledger (WP03)
T014 `docs/changelog/CHANGELOG.md` `[Unreleased]` entry (WP03)

Dependencies: WP01. Risk: the ledger write must go through the CLI seam (no hand-edited `charter.yaml`); the guard test must be fast-tier and network-free.

## Requirements coverage

| Requirement | WP |
|-------------|----|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP02 |
| FR-004 | WP03 |
| FR-005 | WP03 |
| FR-006 | WP03 |
| NFR-001 | WP01 |
| NFR-002 | WP01, WP02, WP03 |
| NFR-003 | WP01 |
| C-001 | WP01 |
| C-002 | WP02, WP03 |
| C-003 | WP01 |
| SC-001 | WP01, WP02 |
| SC-002 | WP03 |
| SC-003 | WP01 |
| SC-004 | WP02, WP03 |

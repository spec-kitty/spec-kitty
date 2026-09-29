# Work Packages: Test suite quality (#5353)

**Inputs**: `kitty-specs/test-suite-quality-p0-01M3NYXQ/spec.md`, `plan.md`

## Work Package WP01: Fix vacuous guards (Priority: P1) 🎯 MVP

**Goal**: Each R1 HIGH guard fails on a planted break and passes on the real product.
**Independent Test**: planted-break red proof per guard, recorded in `research/red-proofs.md`.
**Prompt**: `/tasks/WP01-fix-vacuous-guards.md`
**Requirement Refs**: FR-001, FR-002, FR-006

### Included Subtasks

T001 Fix `tests/acceptance/test_post_consolidation.py:292` forbidden-import set (add `consolidation`) with planted-import proof
T002 Fix `tests/charter/test_context_bootstrap_markers.py:382` no-leak assertion (assert absence of directive canon)
T003 Fix `tests/architectural/test_execution_context_parity.py` injection proofs (:479, :768, :1167) so they run the real ratchet
T004 Fix `tests/zeitgeist_client/test_drain_capability.py:174` so drain gating is the only reason for `None`
T005 Fix `tests/specify_cli/live_work/test_drain_live_work.py:184,:232` (clear `SPEC_KITTY_NO_MOMENT_HANDLERS`)
T006 Fix `tests/specify_cli/cli/commands/test_upgrade_command.py:870` (assert no nag in output)
T007 Record red-then-green proofs in `research/red-proofs.md`

### Dependencies

- None.

---

## Work Package WP02: Unstub gates in legacy harnesses (Priority: P2)

**Goal**: Safety gates run for real in the consolidate/teardown/acceptance harnesses covered by the R2 H findings.
**Independent Test**: removing the gate from production turns a real-git test red.
**Prompt**: `/tasks/WP02-unstub-gates.md`
**Requirement Refs**: FR-002, FR-003

### Included Subtasks

T008 Rework `tests/integration/test_post_merge_unrelated_untracked.py:159,:249` (real assertions; drop stubs added by 4f74543d/39328909)
T009 Rework `tests/cli/commands/test_merge_status_commit.py:203,:322,:460` onto real-git or delete with named covering guard
T010 Rework `tests/specify_cli/acceptance/test_acceptance_cores.py:491` to exercise `locked_reread_splice_and_write` for real
T011 Record proofs in `research/red-proofs.md`

### Dependencies

- None.

---

## Work Package WP03: Retire dev-assist scaffolding (Priority: P3)

**Goal**: Delete redundant scaffolding, each retirement naming a green covering guard.
**Independent Test**: covering guards run green after each deletion.
**Prompt**: `/tasks/WP03-retire-scaffolding.md`
**Requirement Refs**: FR-004, FR-005

### Included Subtasks

T012 Retire `tests/missions/test_resolution_convergence.py` (audit #1)
T013 Retire `tests/unit/test_symbol_identity_spike.py` + `_symbol_identity.py`, re-point note at `_symbol_key.py` (audit #6)
T014 Retire `tests/coordination/test_surface_authority_goldens.py` (audit #7)
T015 Retire `tests/architectural/test_charter_owner_map_executed.py` (audit #8)
T016 Retire `tests/adversarial/test_infrastructure.py` and unused fixtures (audit #10)
T017 Record keep/retire/split verdicts and covering guards in `research/retirement-ledger.md`

### Dependencies

- None.

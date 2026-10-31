# Tasks — Charter Activation Shard Routing (#6336)

**Mission**: `charter-activation-shard-routing-01M68ZRA`
**Input**: [plan.md](./plan.md), [spec.md](./spec.md), [data-model.md](./data-model.md), [research.md](./research.md)
**Branch**: `issue-6336-charter-activation-shard-routing`

Two work packages. WP01 declares the new router group and its module fan-out (the
part that closes the #6333 hole for the activation store and the internal-pack
pin). WP02 routes the activation ledger's kernel floor to the charter shard and
lands the changelog. Both WPs touch the same three data files sequentially
(WP02 depends on WP01), which is why `owned_files` overlap by design.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Write the red-first routing pins for the activation store and the internal-pack pin (FR-002/FR-003/FR-009) and record the red run | WP01 | |
| T002 | Declare the `charter_activation` filter group in `.github/workflows/ci-router.yml` and its `changes.outputs` row (FR-001) | WP01 | |
| T003 | Add `ACTIVATION_STORE_MODULE_FANOUT` to `scripts/ci/gate_selection.py`, export it and union it in `select_modules` (FR-002/FR-003/FR-007) | WP01 | |
| T004 | Register the new group in `_DELIBERATELY_UNGATED_FILTER_GROUPS` (`tests/architectural/test_workflow_coherence.py`) | WP01 | |
| T005 | Extend the fan-out wiring pin in `tests/architectural/test_gate_selection_authority.py` | WP01 | |
| T006 | Re-run the CI-integrity gate set for WP01 and record results | WP01 | |
| T007 | Add the red-first pins for the ledger floor and the ledger reader (FR-004/FR-005) and record the red run | WP02 | |
| T008 | Add `src/kernel/activation_ledger_store.py` to the `charter` scrub group roots (`tests/release/ci_retirement_scrub.json`) (FR-004) | WP02 | |
| T009 | Transcribe that root into the registry's `charter` row (`.github/ci-module-registry.yml`) (FR-008) | WP02 | |
| T010 | Transcribe that glob into the router's `charter` filter (`.github/workflows/ci-router.yml`) (FR-008) | WP02 | |
| T011 | Add the `[Unreleased]` changelog entry under `docs/changelog/CHANGELOG.md` (C-006) | WP02 | |
| T012 | Re-run the full targeted gate set for the mission and record the results | WP02 | |

---

## WP01 — Activation-store router group and charter module fan-out

**Prompt**: [tasks/WP01-activation-store-router-group.md](./tasks/WP01-activation-store-router-group.md)
**Goal**: a `.kittify/charter/charter.yaml`, `.kittify/charter/activation.yaml` or
`packs/internal.source.yaml` diff selects the `charter` registry module, through a
new NON-src `charter_activation` routing group that is transcribed into the
router's filter block and `changes.outputs`, fanned out by the single
gate-selection authority, and registered (not waived) in the two guard registries.
**Priority**: P1 (this is the #6336 acceptance criterion)
**Independent test**: `select_modules([".kittify/charter/charter.yaml"]) == {"charter"}`
and the CI-integrity gates stay green.
**Subtasks**: T001, T002, T003, T004, T005, T006
**Depends on**: nothing
**Risks**: (a) putting a `src/` glob in the new group would make it src-backed and
drag it into the fail-closed union + the "every src group is job-gated" guard — do
not; (b) a `.kittify`/pin group derives an empty consumer-census set, so it must
not join `GROUP_MODULE_FANOUT`/`FANOUT_GROUPS`.

## WP02 — Ledger floor joins the charter group; changelog

**Prompt**: [tasks/WP02-ledger-floor-charter-group.md](./tasks/WP02-ledger-floor-charter-group.md)
**Goal**: `src/kernel/activation_ledger_store.py` selects the `charter` module (in
addition to its existing `kernel`/`core_misc`/`unit` selection) by joining the
`charter` scrub group's roots, transcribed verbatim into the registry row and the
router filter; plus the changelog entry and the final verification sweep.
**Priority**: P2
**Independent test**: `select_modules(["src/kernel/activation_ledger_store.py"]) ⊇
{"charter", "kernel"}` and the transcription/registry guards stay green.
**Subtasks**: T007, T008, T009, T010, T011, T012
**Depends on**: WP01 (the new test module and the fan-out table exist there)
**Risks**: the scrub root, the registry root and the router glob must be edited in
one change or the verbatim transcription guards red; `packs/internal/**` must never
be used as a glob.

---

## Dependency Graph

```
WP01 ──► WP02
```

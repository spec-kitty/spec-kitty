---
description: "Work package task list for CI charter/dossier routing (issue #6125)"
---

# Work Packages: CI router selects charter + dossier for mission-manifest edits

**Inputs**: Design documents from `/kitty-specs/ci-router-charter-dossier-routing-01M4SW1A/`
**Prerequisites**: plan.md (required), spec.md (user stories), research/code-grounding.md

**Tests**: This mission is test-led (ATDD). WP01 is the acceptance gate.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work package is independently deliverable and testable.

**Prompt Files**: Each work package references a matching prompt file in `/tasks/`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: CI authorities under `.github/`, `tests/release/`, gate tests under `tests/architectural/`.

---

## Work Package WP01: Red-first router-parity gate (Priority: P1) 🎯

**Goal**: Pin the #6125 contract with a non-vacuous ATDD gate — a mission-manifest diff must
select the `charter` AND `dossier` modules via the real `select_modules` authority. Proven RED on
`origin/main`, GREEN after WP02.
**Independent Test**: `pytest tests/architectural/test_manifest_edit_routes_charter_and_dossier.py`
— RED on `origin/main`, GREEN on the mission's final commit.
**Prompt**: `/tasks/WP01-red-first-parity-gate.md`
**Requirement Refs**: FR-001, SC-001

### Included Subtasks

T001 Add `tests/architectural/test_manifest_edit_routes_charter_and_dossier.py` asserting, through
`scripts.ci.gate_selection.select_modules`, that each of the four
`packs/built-in/missions/*/expected-artifacts.yaml` paths selects a superset of
`{"charter", "dossier"}`, plus a non-vacuity/self-break guard and the file-specific-glob guard
(`packs/built-in/missions/foo.md` still selects zero code shards).
T002 Prove the test RED on `origin/main` and record the evidence (command + output) in the mission
tracer and the PR.

### Implementation Notes

- Import the authority (`from scripts.ci.gate_selection import select_modules, select_gates`); never
  re-encode a hand map.
- Mark `pytestmark = pytest.mark.architectural` to match the sibling router/registry gates.

### Dependencies

- None (lands first, RED).

### Risks & Mitigations

- Vacuous gate → include a self-break assertion and prove RED on base.

---

## Work Package WP02: Charter leg + dossier module + measured timings (Priority: P1) 🎯 MVP

**Goal**: Make a mission-manifest edit select `charter` + `dossier`, and give `tests/dossier` +
`tests/specify_cli/dossier` a real per-PR module, keeping the registry/scrub/router verbatim in
lockstep; capture real measured shard timings. Turns WP01 green.
**Independent Test**: The named CI gate suites + WP01 parity gate + `tests/dossier` +
`tests/specify_cli/dossier` all pass; `select_modules(manifest) ⊇ {charter, dossier}` and
`select_modules(src/specify_cli/dossier/**)` includes `dossier` without forcing run-all.
**Prompt**: `/tasks/WP02-charter-dossier-routing.md`
**Requirement Refs**: FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003

### Included Subtasks

T003 **Charter leg** (one commit): append the file-specific glob
`packs/built-in/missions/**/expected-artifacts.yaml` to the `charter` group's `roots` in
`tests/release/ci_retirement_scrub.json` and `.github/ci-module-registry.yml`, and to the `charter`
filter group in `.github/workflows/ci-router.yml` — ordered-equal in all three (verbatim guard).
T004 **Dossier scrub + registry** (one commit): add a `dossier` group to
`tests/release/ci_retirement_scrub.json` (`roots: [src/specify_cli/dossier/**,
packs/built-in/missions/**/expected-artifacts.yaml]`, `cov_targets: [specify_cli.dossier]`,
`census_evidence`); add the matching `dossier` registry row (roots/cov_targets verbatim,
`tier: standard`, `test_dirs: [tests/dossier, tests/specify_cli/dossier]`, provisional
`shard_count`); remove `tests/dossier` and `tests/specify_cli/dossier` from
`out_of_matrix_test_dirs`.
T005 **Dossier router wiring** (same commit as T004): add the `dossier` filter group (verbatim the
scrub roots), the `dossier` `changes.outputs` line, the `dossier` entry in the `unmatched` loop, and
`needs.changes.outputs.dossier == 'true'` in the heavy-battery `if:`.
T006 **Measured timings** (one commit): run
`python scripts/ci/capture_shard_timings.py --module dossier --write` (real serial capture) and set
the registry `shard_count` to the measured value (skew ≤20%).

### Implementation Notes

- Order within the WP: T003 (charter) → T004+T005 (dossier wiring) → T006 (timings; needs the row to
  exist first). Each of T003 and T004/T005 is a distinct, independently-reviewable commit.
- Keep the glob file-specific so the corpus golden (`foo.md`) stays green.

### Dependencies

- Depends on WP01 (turns the parity gate green).

### Risks & Mitigations

- Verbatim guard list-equality → ordered-append in all three authorities.
- Claim-once guard → remove the two dirs from `out_of_matrix_test_dirs` in the same change.
- Shard-timings strict check → measured capture, never guessed.

---

## Dependency & Execution Summary

- **Sequence**: WP01 (RED gate) → WP02 (routing change, GREEN).
- **MVP Scope**: Both WPs; the mission is incomplete until WP01 is green.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP02 |
| FR-003 | WP02 |
| FR-004 | WP02 |
| FR-005 | WP02 |
| NFR-001 | WP02 |
| NFR-002 | WP02 |
| NFR-003 | WP02 |
| C-001 | WP02 |
| C-002 | WP01, WP02 |
| C-003 | WP02 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Add red-first parity gate | WP01 | P1 | No |
| T002 | Prove RED on origin/main | WP01 | P1 | No |
| T003 | Charter leg (manifest glob, 3 authorities) | WP02 | P1 | No |
| T004 | Dossier scrub + registry row + out-of-matrix release | WP02 | P1 | No |
| T005 | Dossier router wiring | WP02 | P1 | No |
| T006 | Measured shard timings | WP02 | P1 | No |

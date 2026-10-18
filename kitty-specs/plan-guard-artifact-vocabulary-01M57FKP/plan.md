# Implementation Plan: Fix plan-mission guard/manifest artifact-vocabulary mismatch

**Branch**: `fix/plan-guard-artifact-vocabulary` | **Date**: 2026-10-18 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/plan-guard-artifact-vocabulary-01M57FKP/spec.md`

## Summary

A built-in `plan` mission cannot pass `specify`: the plan guard chain checks `spec.md`/`research.md`/
`plan.md` (what the plan step contracts produce) but `plan/expected-artifacts.yaml` declares
`goals.md`/`research.md`/`plan.md` under phase step-keys `goals`/`research`/`draft`, so a committed
`spec.md` is never gathered (reads missing) and `guard_failure_paths` is empty. The fix reconciles the
**manifest** to the runtime action vocabulary (`specify/research/plan/review`) on **both axes** —
re-key `goals`/`draft`→`specify`/`plan` **and** re-path `goals.md`→`spec.md` — leaving the guard
untouched; reconciles the two descriptive `mission.yaml` copies; adds the secondary `guard_failure_paths`
regression, a cross-family parity test routed through the **real** `gather_artifact_presence`, and a
vocabulary-coherence CI guard; and corrects the now-false manifest header comment.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `charter.activation.manifest_loader.load_manifest`, `charter.offering.missions.step_projection.project_artifact_name_set`, the runtime guard/gather surfaces (`runtime_bridge_cores`, `runtime_bridge_io`), `specify_cli.runtime.resolver` (`required_artifacts_for`, `resolve_configured_artifact_name`), `ruamel.yaml`
**Storage**: pack YAML files on disk (`packs/built-in/missions/plan/expected-artifacts.yaml`, two `mission.yaml` copies); no database
**Testing**: `pytest` — `tests/runtime/`, `tests/runtime/next/`, `tests/next/`, `tests/specify_cli/runtime/`, `tests/dossier/`, specific `tests/architectural/` gate files; baseline `make test-fast`. No `make test-full`; no `.github/ci-shard-timings.json` regen.
**Target Platform**: Linux/macOS/Windows CLI
**Project Type**: single (CLI package + built-in packs)
**Performance Goals**: none (correctness fix; no hot-path change)
**Constraints**: do NOT touch `_evaluate_plan_guards` (C-001); one canonical vocabulary = runtime action ids (C-002); keep `MISSION_GOALS` (C-003); defect #2 out of scope, verify at gather/guard structural level (C-004); manifest stays `extra="forbid"` valid (NFR-002); no non-plan-family regression (NFR-001)
**Scale/Scope**: one manifest + two mission.yaml copies + 1 doc, 3 new/updated tests, 1 CI guard, ~4 change-together test-mirror updates

## Charter Check

*GATE: Must pass before Phase 0. Re-check after Phase 1.*

- **Single canonical authority** — PASS by design: the runtime step-contract action ids become the one
  vocabulary; the manifest and both `mission.yaml` copies derive from it (C-002). No second authority
  re-introduced.
- **Architectural alignment / layer direction** — PASS: fix is pack-data + runtime read-side; the guard
  layer is untouched; no import-direction change.
- **ATDD-first / red-first** — PASS: FR-001/FR-003/FR-004/FR-005 land red-first (gather/guard structural
  level) before the manifest change; the parity test routes through the REAL `gather_artifact_presence`
  (non-vacuity — synthetic `present_artifacts=` is why the bug hid).
- **Tiered rigour** — runtime guard-vocabulary + release-gating pack contract → high rigour: parity +
  coherence corpus guards, byte-compat characterization preserved for non-plan families.
- **Campsite/terminology** — reconcile the stale comment and the descriptive `mission.yaml`; do NOT
  expand scope to remove `MISSION_GOALS` (flagged follow-up).

No violations to justify.

## Key Design Decisions

- **D1 — Manifest-side fix (Option A), both axes.** Truth flows step-contract → guard → manifest. Three
  of four surfaces (contracts, guard, runtime dispatch) already agree on `specify/research/plan`; only
  the manifest disagrees, on two axes. Re-path `goals.md`→`spec.md` (clears the block: `spec.md` enters
  `_presence_filenames_for('plan')`) **and** re-key `goals`→`specify`, `draft`→`plan` (restores
  `guard_failure_paths`: `required_artifacts_for('specify','plan')` is step-keyed, returns `[]` while
  the key is `goals`). A path-only rename fixes only symptom (a). Reject Option B (retag the guard): the
  guard dispatches on action id `specify`, and the step contract writes `spec.md`, so a guard checking
  `goals.md` would recreate the block in the opposite direction.
- **D2 — `mission.yaml` is descriptive-only (confirmed).** Grep shows the only `required_*` reader is
  `step_projection.py` over `expected-artifacts.yaml`; nothing reads `mission.yaml`'s `artifacts.required`
  / `workflow.phases` on the gather/guard path. Reconcile both copies for coherence; non-load-bearing.
- **D3 — Parity test must use the real gatherer.** Every existing plan guard test injected
  `present_artifacts` synthetically, bypassing the manifest-sourced presence set — which is exactly why
  the bug passed all of them. The new parity test builds an on-disk artifact-present fixture and routes
  through the real `gather_artifact_presence`.
- **D4 — Coherence CI guard is the highest-value hardening.** No check today asserts a built-in type's
  manifest step-keys match its runtime step-contract action ids; that absence let the three-vocabulary
  drift ship. Add it in `tests/architectural/`.
- **D5 — `extra="forbid"` discipline.** Only step-keys, `path_pattern`s, and comments change in the
  manifest; `schema_version`/`manifest_version`/field shapes preserved (NFR-002).

## Project Structure

### Documentation (this mission)
```
kitty-specs/plan-guard-artifact-vocabulary-01M57FKP/
├── plan.md            # this file
├── research.md        # Phase 0
├── data-model.md      # Phase 1
├── quickstart.md      # Phase 1
├── contracts/         # Phase 1 (behavioural contracts)
└── tasks.md           # Phase 2 (/spec-kitty.tasks)
```

### Source / packs (repository root)
```
packs/built-in/missions/plan/expected-artifacts.yaml     # IC-01: re-key + re-path + header comment
packs/built-in/missions/plan/mission.yaml                # IC-02: descriptive reconcile
src/specify_cli/missions/plan/mission.yaml               # IC-02: duplicate descriptive reconcile
src/runtime/next/runtime_bridge_cores.py                 # NOT MODIFIED (guard is correct, C-001)
tests/next/test_guard_failure_paths_3883.py              # IC-03: plan guard_failure_paths regression
tests/runtime/next/test_cli_guard_family.py              # IC-04: cross-family parity via real gather
tests/architectural/<new or existing corpus guard>       # IC-05: vocabulary-coherence CI guard
tests/specify_cli/runtime/test_configured_artifact_name.py  # change-together mirror update
tests/dossier/test_manifest.py                           # change-together mirror update
src/charter/offering/skills/spec-kitty-mission-system/references/mission-comparison-matrix.md  # doc
```

**Structure Decision**: Single CLI package + built-in packs. The fix is pack-data + runtime read-side +
tests; the guard code is explicitly untouched.

## Complexity Tracking

*No Charter Check violations — section intentionally empty.*

## Implementation Concern Map

> Concerns are NOT work packages. `/spec-kitty.tasks` translates these into WPs.

### IC-01 — Reconcile the plan expected-artifacts manifest (P0 core)
- **Purpose**: Re-key `required_by_step` `goals`/`draft`→`specify`/`plan` and re-path `goals.md`→`spec.md` so a present `spec.md` reads present and `required_artifacts_for('specify','plan')` resolves `{spec.md}`; fix the stale header comment.
- **Relevant requirements**: FR-001, FR-002, NFR-002, SC-001, SC-004
- **Affected surfaces**: `packs/built-in/missions/plan/expected-artifacts.yaml`; red-first tests exercising `_presence_filenames_for`/`required_artifacts_for`/`_evaluate_plan_guards`/`gather_artifact_presence` for the plan family.
- **Sequencing/depends-on**: none (the core; everything else verifies or hardens it).
- **Risks**: keep schema valid; verify `test_bridge_parity.py::test_coverage_floor_is_met` does not re-trip (the WP04 note warns a step-scoped presence design over-blocked plan); update the change-together mirrors (`test_configured_artifact_name.py` row + ten-tags map, `test_manifest.py` step ids/goals.md row) as intentional contract updates.

### IC-02 — Reconcile the two descriptive `mission.yaml` copies
- **Purpose**: Align `required:`/`workflow.phases` in both `mission.yaml` copies to the action vocabulary (no `goals.md` phantom) for coherence; non-load-bearing.
- **Relevant requirements**: FR-006, C-002
- **Affected surfaces**: `packs/built-in/missions/plan/mission.yaml`, `src/specify_cli/missions/plan/mission.yaml`; the doc matrix.
- **Sequencing/depends-on**: none (independent of IC-01; descriptive).
- **Risks**: confirmed no runtime consumer of these fields (D2) — keep it coherence-only; do not let it become a second authority.

### IC-03 — Secondary: plan missing-artifact block names its path
- **Purpose**: Regression test that a genuine plan `specify` missing-artifact block carries a non-empty `guard_failure_paths` (restored by IC-01's step-key rename).
- **Relevant requirements**: FR-003, SC-002
- **Affected surfaces**: `tests/next/test_guard_failure_paths_3883.py`.
- **Sequencing/depends-on**: logically rides IC-01 (the path is only restored once the key is `specify`).
- **Risks**: assert against the real `guard_failure_artifact_paths` + plan family, not a synthetic stub.

### IC-04 — Cross-family parity test through the real gatherer
- **Purpose**: Dispatch each registered guard family (software-dev/research/documentation/plan) through the REAL `gather_artifact_presence` against an artifact-present on-disk fixture, asserting no spurious block — the structural invariant that was missing.
- **Relevant requirements**: FR-004, SC-003
- **Affected surfaces**: `tests/runtime/next/test_cli_guard_family.py`.
- **Sequencing/depends-on**: red-first before IC-01 (plan arm red pre-fix, green post-fix).
- **Risks**: MUST go through the real gatherer, not `present_artifacts=`; build a minimal on-disk fixture per family.

### IC-05 — Vocabulary-coherence CI/corpus guard (hardening)
- **Purpose**: Fail CI when a shipped built-in mission type's manifest step-keys diverge from its runtime step-contract action ids (or it is missing step contracts).
- **Relevant requirements**: FR-005, SC-003
- **Affected surfaces**: `tests/architectural/` (beside the workflow-coherence corpus guards).
- **Sequencing/depends-on**: red-first before IC-01 (red against the pre-fix plan divergence, green after).
- **Risks**: scope the guard to built-in types; ensure it reads both the manifest step-keys and the runtime step-contract action ids from their canonical loaders, not hardcoded lists.

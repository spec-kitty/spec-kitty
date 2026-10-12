# Implementation Plan: Derive the mission-state audit's CI trigger list from what the audit executes

**Branch**: `issue-6090-audit-trigger-derivation` | **Date**: 2026-10-12 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/audit-trigger-derivation-01M4RKRD/spec.md`
**Grounding**: [research/code-grounding.md](./research/code-grounding.md)

## Summary

Close the drift/defect class behind #6058: the modules the `mission_state` audit
touches are hand-copied in two places (`ci-router.yml` globs and
`tests/ci/test_mission_state_audit_routing.py::AUDIT_INPUT_PATHS`). Replace the
test-side hand copy with a non-vacuous, self-mutation-proven test that *derives*
the executed-module set from an in-process `run_audit` on a small git fixture and
asserts each executed `src/` module is matched by the `mission_state` group via the
single routing authority (`scripts/ci/gate_selection.load_router`/`select_gates`).
Grounding shows all 33 modules the audit executes over the real corpus are already
matched by the existing globs, so **no `ci-router.yml` edit is required** — this is
add-the-test + remove-the-hand-copy, with no runtime/product behaviour change.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: pytest (`fast` marker), PyYAML, `scripts/ci/gate_selection.py` (router authority), `specify_cli.audit.run_audit`, `specify_cli.status` reducer
**Storage**: N/A (read-only audit over a `tmp_path` git fixture)
**Testing**: `tests/ci/test_mission_state_audit_routing.py` (the conventional home); run by name + `make test-fast`
**Target Platform**: Linux/macOS/Windows CI runners
**Project Type**: single (CLI/library)
**Performance Goals**: derived test < 2s (in-process audit over a 1-mission fixture ≈ 0.01s)
**Constraints**: mypy --strict clean; ruff + ruff format clean on changed files; complexity ≤ 15; no `# noqa`/suppressions; no new ratchet/allowlist gate; deterministic (order-independent) capture
**Scale/Scope**: one test module touched; one hand-copied constant removed; two consumer tests re-pointed

## Charter Check

*GATE: Must pass before and after design.*

- **Standing Order 5 (architectural-gate discipline, DIRECTIVE_043, `architectural-gate-non-vacuity`)**: the new check is NON-VACUOUS and self-mutation-proven — it FAILS when the audit executes a module outside the `mission_state` globs (planted break) and PASSES on the real set; it carries a same-fixture positive control (the derived set is asserted non-empty and to contain known audit anchors). No allowlist is introduced, so no `_baselines.yaml` entry is needed. PASS.
- **Standing Order 6 (`canonical-source-unification`)**: removes the hand-copied `AUDIT_INPUT_PATHS` mirror; one derived source of truth. PASS.
- **ATDD-first (C-011)**: the derivation test is the acceptance test, committed first; its red-first proof is the witnessed self-mutation (RED under a planted out-of-glob module and under a dropped glob), recorded but not committed. PASS.
- **Terminology Canon (Mission not Feature)**: no new `feature*` identifiers; fixture events key on `mission_id`. PASS.
- **No full heavy-suite runs / NO_FULL_HEAVY_SUITES_IN_MISSION**: run the touched CI-routing tests by name + `make test-fast`; never the bare `tests/architectural/`. PASS.
- **Git/workflow (DIRECTIVE_045)**: PR to `main`, operator merges; no model identifier in commits/PR. PASS.

No violations → Complexity Tracking empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/audit-trigger-derivation-01M4RKRD/
├── spec.md                      # requirements (committed)
├── plan.md                      # this file
├── research/code-grounding.md   # grounding (committed first)
├── checklists/requirements.md   # spec quality checklist
└── tasks/                       # work packages (/spec-kitty.tasks output)
```

### Source Code (repository root)

```
tests/ci/
└── test_mission_state_audit_routing.py   # EDIT: add derived non-vacuity test;
                                           #       remove AUDIT_INPUT_PATHS;
                                           #       re-point its two consumers

# READ-ONLY authorities the test reuses (not edited):
scripts/ci/gate_selection.py              # load_router / select_gates (routing authority)
src/specify_cli/audit/                     # run_audit (in-process audit entry)
src/specify_cli/status/reducer.py          # materialize_* (fixture status.json)
.github/workflows/ci-router.yml            # mission_state globs (READ; not edited — 33/33 covered)
```

**Structure Decision**: Single project. The only edited file is
`tests/ci/test_mission_state_audit_routing.py`. If a derived module were found
outside the globs (it is not, today), the fix would be a new `**/`-prefixed glob in
`ci-router.yml` — gated behind the workflow-scope caveat and, if the push were
refused, delivered as a documented diff in the PR body (C-002).

## Complexity Tracking

*No Charter Check violations — none to justify.*

## Implementation Concern Map

### IC-01 — Deterministic in-process executed-module capture + coverage assertion

- **Purpose**: Derive the `src/` modules the audit executes (warm, function-call-scoped `sys.setprofile` over an in-process `run_audit` on a small committed git fixture) and assert each is matched by the `mission_state` group via `load_router`/`select_gates`, with a same-fixture positive control.
- **Relevant requirements**: FR-001, FR-002, FR-005, NFR-001, NFR-002, C-004.
- **Affected surfaces**: `tests/ci/test_mission_state_audit_routing.py` (new fixture + test); reuses `scripts/ci/gate_selection.py`, `specify_cli.audit`, `specify_cli.status`.
- **Sequencing/depends-on**: none (first).
- **Risks**: capture order-sensitivity (mitigated by warm-up + function-call frames only); fixture must drive the normal audit path (modern `mission_id` events + reducer-generated `status.json`).

### IC-02 — Remove the hand copy and re-point consumers (unification)

- **Purpose**: Delete `AUDIT_INPUT_PATHS` and route `test_audit_inputs_match_the_group_directly` / `test_the_reducer_bump_commit_selects_the_audit_job` off the derived executed-module set plus a small explicit non-executed-input list (manifests, workflow, renderer) that the audit does not execute in-process.
- **Relevant requirements**: FR-003, FR-004.
- **Affected surfaces**: `tests/ci/test_mission_state_audit_routing.py`.
- **Sequencing/depends-on**: IC-01 (the derived set must exist before the hand copy is removed).
- **Risks**: the manifest/workflow/renderer inputs are not derivable from an in-process run; they must stay an explicit, asserted list so the #6058 manifest-alignment guard is preserved.

## Phasing

One work package. ATDD order inside the WP:

1. **Red-first**: add the derived non-vacuity test (IC-01). Witness it RED by planting an out-of-glob executed module and by dropping a covering glob; record both commands/outputs; do **not** commit the break. Commit the test (green on real code).
2. **Unification**: remove `AUDIT_INPUT_PATHS` and re-point its consumers onto the derived set + explicit non-executed-input list (IC-02).
3. Validate: run the touched routing tests by name + sibling CI-router guards + `make test-fast`; ruff/format/mypy/complexity clean on the changed file.

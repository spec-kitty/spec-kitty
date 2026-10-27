# Implementation Plan: Doctor flags org-pack nodes whose body_path escapes the pack

**Branch**: `issue-6418-doctor-body-path-containment` | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/doctor-body-path-containment-01M5ZD3C/spec.md`

## Summary

`doctor charter-packs` derives its exit code from `org_drg["errors"]`, but neither of its org-layer halves (the JSON collector `_collect_org_layer_data` and the human renderer `_render_org_layer_section`) looks at an authored fragment node's `body_path`. A new charter-layer predicate runs the existing containment primitive `resolve_relative_path_within_root` on each authored node's `body_path`, against that pack's effective root. Both doctor halves call it. Escapes go to `org_drg.errors` (the exit code flips to 1), to a new always-present `org_drg.body_path_escapes` list, and to a verdict line in the human section. The gating scenario PR-CHARTER-SHARING-004 then loses `@wip @defect:6418`.

Engineering alignment: the operator's brief and the three specify Decision Moments settle every design choice (JSON shape, node scope, doctor-only scope), so no planning question remained open.

## Technical Context

**Language/Version**: Python 3.11+ (repository floor)
**Primary Dependencies**: none added. Existing: pydantic (fragment model), typer/rich (doctor CLI)
**Storage**: files: org pack trees on disk, read-only; no node body is ever opened (NFR-001)
**Testing**: pytest. Red-first unit tests for the predicate (`tests/charter_offering/drg/`), collector/renderer/CLI tests (`tests/specify_cli/cli/commands/test_doctor_charter_packs_org_layer.py`), and the gating JVM scenario (CI's scenario lane; not run locally unless Java is needed)
**Target Platform**: Linux/macOS/Windows CLI; the primitive already rules on Windows-form paths on every OS
**Project Type**: single (the `src/` layered packages)
**Performance Goals**: one registry read plus one path resolution per authored node with a `body_path`; negligible next to the existing merge
**Constraints**: complexity ≤ 15 per function; no new `noqa` or `type: ignore`; diff-cover ≥ 90%; no change to the layer chain, the facades' identity tables or `pyproject.toml`
**Scale/Scope**: 3 source files, about 120 lines of product code; tests; scenario tag, PROMISES.md and changelog

## Charter Check

| Gate | Verdict |
|---|---|
| Single canonical authority (DIRECTIVE_044) | PASS: reuses `resolve_relative_path_within_root`; one predicate feeds both doctor halves |
| Architectural alignment (DIRECTIVE_001, ADR 2026-10-16-1 + Amend. 2026-10-19) | PASS: the predicate is in-core `charter.offering.drg`; the registry-aware wrapper sits beside `load_org_drg` in `charter.activation.drg_activation`, which `specify_cli` already imports. Nothing is extracted |
| Pack tiers | PASS: no `packs/` edit |
| ATDD-first / red-first (DIRECTIVE_041/034) | PASS: the entry-point reproduction is recorded in research; tests are written red before the fix |
| Terminology canon | PASS: Mission/pack vocabulary; the terminology guard runs pre-push |
| Tidy-first (Standing Order #2) | PASS: the check is an extracted helper; the touched functions stay ≤ 15 |
| Supply chain (DIRECTIVE_051) | N/A: no dependency change |
| Reviewer ≠ implementer (Standing Order #8) | PASS: the WP review runs under a different profile than the implementation |

Post-design re-check: unchanged, all PASS.

## Project Structure

### Documentation (this mission)

```
kitty-specs/doctor-body-path-containment-01M5ZD3C/
├── spec.md
├── plan.md
├── research.md            # decisions (extends research/phase0-grounding.md)
├── research/              # Phase 0 grounding + tracer files
├── data-model.md
├── quickstart.md
└── tasks.md               # /spec-kitty.tasks output
```

`contracts/` is waived: there is no new interface beyond the additive `--json` key, which `data-model.md` documents. `meta.json` records `contracts: none`.

### Source Code (repository root)

```
src/charter/offering/drg/org_pack_loader.py      # + BodyPathEscape, find_body_path_escapes(fragment, pack_root)
src/charter/activation/drg_activation.py         # + find_org_body_path_escapes(repo_root, fragments)
src/specify_cli/cli/commands/_charter_pack_collect.py   # collector: body_path_escapes key + errors
src/specify_cli/cli/commands/_profile_health_render.py  # renderer: "body_path escapes:" verdict line
tests/charter_offering/drg/test_org_body_path_escapes.py          # new
tests/specify_cli/cli/commands/test_doctor_charter_packs_org_layer.py  # extended
tests/scenarios/charter/share-governance-safely/share-governance-safely.feature  # drop @wip/@defect:6418
tests/scenarios/charter/PROMISES.md              # PR-CHARTER-SHARING-004 → bound
docs/changelog/CHANGELOG.md                      # [Unreleased] entry
```

**Structure Decision**: the containment rule stays in the charter layer, where the primitive and the fragment model live. The registry/pack-root join lives where `load_org_drg` already performs it, and the doctor stays a presenter.

## Implementation Concern Map

### IC-01 — Charter predicate for fragment-node containment

- **Purpose**: one function decides which authored fragment nodes escape their pack, by delegating to the shared primitive.
- **Relevant requirements**: FR-001, FR-005, NFR-001, C-001, C-004
- **Affected surfaces**: `charter/offering/drg/org_pack_loader.py`, `charter/activation/drg_activation.py`
- **Sequencing/depends-on**: none
- **Risks**: authored-vs-discovered relies on the node subclass (see the `authored_nodes` docstring), so it must be called on the fragment `load_org_drg` returned, never a copy. A registry fault is raised to the caller, not swallowed.

### IC-02 — Doctor surfaces (JSON + human)

- **Purpose**: both halves of `doctor charter-packs` report the escapes, and the exit code flips.
- **Relevant requirements**: FR-002, FR-003, FR-004, NFR-002, NFR-003
- **Affected surfaces**: `_charter_pack_collect.py::_collect_org_layer_data`, `_profile_health_render.py::_render_org_layer_section`
- **Sequencing/depends-on**: IC-01
- **Risks**: `_collect_org_layer_data` sits near the complexity ceiling, so the check goes in its own helper. It runs right after a successful load, independent of whether the merge succeeds: an escape is a pack fault, not a graph fault. A crash in the check is recorded as an error (a check that could not run is not a pass).

### IC-03 — Gating promise and release notes

- **Purpose**: PR-CHARTER-SHARING-004 gates again; the changelog records the fix.
- **Relevant requirements**: FR-006
- **Affected surfaces**: the scenario feature file, `tests/scenarios/charter/PROMISES.md`, `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-02
- **Risks**: the scenario runs only in the JVM lane, so the local proof is the Python CLI test on the same fixture shape.

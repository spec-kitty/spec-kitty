# Implementation Plan: Mission-type capability contract for custom types

**Branch**: `kitty/mission-mission-type-capability-contract-01M54BVT` | **Date**: 2026-10-17 | **Spec**: `./spec.md`
**Input**: Mission specification from `kitty-specs/mission-type-capability-contract-01M54BVT/spec.md`

## Summary

Converge the remaining `software-dev`-literal lifecycle/rigour gates (#6315) onto an
explicit capability contract on the resolved charter-offering mission-type object,
per the operator's Option-B decision. Introduce two capabilities now — **`wp_driven`**
and **`requires_substantive_spec`** — exposed through `charter.offering.api`, and route
the WP-advance guard (site 1) and the substantive-spec prerequisite (site 4) through
them. Fix the defect where a custom WP-driven family hits `UnregisteredMissionFamilyError`
in the pure guard core and the WP-advance guard is silently skipped. Move slice-1's
charter-local runtime-shape parser into `kernel`. Leave the non-WP pre-check (site 2)
software-dev-literal by design; scope out template precedence (site 5). Defer
`code_producing` and its gate to #6327 / #6328.

**Single-authority design.** The `wp_driven` derivation **rule** (`implement ∈ step ids`)
and the runtime-shape step-id **parser** both live in `kernel` — the one layer both
`charter` and `runtime` import (verified: `charter.offering.missions.glossary_hook` and
`runtime.next.run_index` already `from kernel import …`). Charter's `ResolvedMissionType`
exposes `wp_driven` for CLI/external consumers; the runtime I/O seam derives the same
bool from the frozen DAG via the same kernel rule and carries it into the pure cores
snapshot. They agree by construction and are parity-tested. `requires_substantive_spec`
is a spec-content fact derived in charter from whether a substantive-spec field
declaration resolves for the type (the existing `_substantive` seam); it is not a DAG fact.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: ruamel.yaml (kernel yaml IO); no new deps.
**Storage**: filesystem (pack roots, `mission_template_frozen.yaml`, mission-type YAML).
**Testing**: pytest — `tests/kernel/`, `tests/charter/` + `tests/charter_offering/`, `tests/runtime/`, `tests/specify_cli/cli/commands/`.
**Project Type**: single
**Constraints**: enforced layer chain `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli`; the shared rule/parser go in `kernel`; the pure guard core (`runtime_bridge_cores`) stays stdlib-only and learns `wp_driven` as a plain bool on its snapshot. Capability fields are additive to `charter.offering.api` (NFR-002). Byte-identical for the 4 built-in families.
**Scale/Scope**: ~3 layers, 1 new kernel module, a charter DTO facet, 2 gate consumers, 1 cores-routing fix, ~5 WPs.

## Charter Check

- **Single canonical authority (C-001):** capabilities are a facet of the existing `ResolvedMissionType`; the derivation rule + parser are single-sourced in `kernel`. No competing resolver.
- **Public-surface discipline (NFR-002):** capability fields additive to `charter.offering.api`; if the charter offering contract carries an explicit version, bump it with the change and land the machine contract + any docs together (escalate the versioning mechanics if a bump is required — operator decision class).
- **ATDD-first / test economy (`DIRECTIVE_041`):** one focused red-first test per behaviour; built-in golden-parity suites are the ratchet.
- **Scope fence (C-003):** `code_producing` (#6327), its gate (#6328), and template precedence (`io.py:665`) are out.

## Project Structure

```
src/kernel/mission_runtime_shape.py        # NEW: runtime-shape step-id reader + wp_driven rule (IC-01)
src/charter/offering/missions/mission_step_repository.py  # delete charter-local dup, shim to kernel (IC-01)
src/charter/activation/mission_type_profiles.py           # ResolvedMissionType capability facet (IC-02)
src/charter/offering/... (api surface)                    # expose capabilities (IC-02)
src/runtime/next/runtime_bridge_io.py       # derive wp_driven from frozen DAG via kernel rule; snapshot fact (IC-03)
src/runtime/next/runtime_bridge_composition.py  # site 1: wp_driven guard (IC-03)
src/runtime/next/runtime_bridge_cores.py    # route wp_driven families through WP-iteration guard, not Unregistered (IC-03)
src/specify_cli/cli/commands/agent/mission_check_prerequisites.py  # site 4 via requires_substantive_spec (IC-04)
```

## Complexity Tracking

| Deviation | Need | Why simpler insufficient |
|-----------|------|--------------------------|
| New `kernel` module for the shared rule + parser | charter + runtime both need it and the layer chain forbids charter→runtime | A charter-local duplicate (slice-1 interim) is exactly the debt #6315 pays down |
| `wp_driven` carried as a bool on the cores snapshot | the pure stdlib-only guard core cannot read disk or import charter | computing it in the I/O seam and passing a bool preserves the pure-leaf boundary |

## Implementation Concern Map

### IC-01 — Shared runtime-shape parser + `wp_driven` rule in `kernel` (FR-006, C-004, SC-004)
- **Purpose**: one canonical runtime-shape step-id reader and one `wp_driven` derivation rule (`implement ∈ step ids`), imported by both charter and runtime.
- **Surfaces**: `src/kernel/mission_runtime_shape.py` (new); `src/charter/offering/missions/mission_step_repository.py` (delete `_runtime_shape_step_ids`, shim `resolve_runtime_shape_steps` to the kernel reader); `tests/kernel/`, re-pointed parity test in `tests/charter_offering/missions/test_mission_type_repository.py`.
- **Depends-on**: none. **Risks**: preserve slice-1's exact fail-closed contract (any non-mapping / missing id+title → `[]`); runtime's richer `load_mission_template_file` is NOT replaced — parity test re-pointed to `kernel`↔`runtime`.

### IC-02 — Capability facets on `ResolvedMissionType` via `charter.offering.api` (FR-001, FR-002, NFR-002, C-001, C-002, SC-002)
- **Purpose**: expose `wp_driven` (via the kernel rule over the resolved step ids) and `requires_substantive_spec` (via the substantive-spec field-declaration seam) on the resolved mission-type object and its public surface.
- **Surfaces**: `src/charter/activation/mission_type_profiles.py` (+ the offering API re-export); `tests/charter*/`.
- **Depends-on**: IC-01 (the kernel rule). **Risks**: additive only; built-ins resolve correct values with no authoring change; conservative default when undeclared.

### IC-03 — Site 1: WP-advance guard keyed on `wp_driven` + cores routing fix (FR-003, FR-004, NFR-001, SC-001)
- **Purpose**: the implement/review WP-advance guard fires for any `wp_driven` mission; a `wp_driven` custom family's implement/review guards route through `_evaluate_wp_iteration_guard` (fail-closed) instead of raising/​swallowing `UnregisteredMissionFamilyError`.
- **Surfaces**: `src/runtime/next/runtime_bridge_io.py` (derive `wp_driven` from the frozen DAG via the kernel rule; carry the bool on the snapshot), `runtime_bridge_composition.py:496`, `runtime_bridge_cores.py` (guard routing); `tests/runtime/`.
- **Depends-on**: IC-01. **Risks**: must stay byte-identical for `software-dev` and keep `plan` non-WP-driven (key on `implement`, not `review`); the cores leaf learns only a bool.

### IC-04 — Site 4: substantive-spec prerequisite keyed on `requires_substantive_spec` (FR-005, NFR-001, SC-002)
- **Purpose**: the resume prerequisite runs `is_substantive` for any `requires_substantive_spec` type, not the `{software-dev,research}` literal; documentation/plan still bypass.
- **Surfaces**: `src/specify_cli/cli/commands/agent/mission_check_prerequisites.py:429`; `tests/specify_cli/cli/commands/`.
- **Depends-on**: IC-02 (reads the capability). **Risks**: must not flip documentation/plan to require FR rows.

### IC-05 — Deliberate non-change (site 2) + scope-out note (site 5) (FR-007, C-003)
- **Purpose**: assert `runtime_bridge.py:878` stays software-dev-literal with a custom non-WP step still blocking via composition Phase 3; record site 5 (template precedence) as out of scope.
- **Surfaces**: a focused runtime test; `docs/changelog/CHANGELOG.md`.
- **Depends-on**: none. **Risks**: none (test + doc).

---
description: "Work packages for the mission-type capability contract (#6315)"
---

# Work Packages: Mission-type capability contract for custom types

**Inputs**: `kitty-specs/mission-type-capability-contract-01M54BVT/{spec.md,plan.md}`
**Tests**: Red-first per WP (ATDD); `DIRECTIVE_041` test economy; built-in golden-parity suites are the ratchet.
**Organization**: WP01 → {WP02 → WP04, WP03}; WP05 independent. Sibling-disjoint owned files.

## Path Conventions
- **Single project**: `src/`, `tests/`

---

## Work Package WP01: Shared runtime-shape parser + `wp_driven` rule in `kernel` (Priority: P0)

**Goal**: One canonical runtime-shape step-id reader and one `wp_driven` derivation rule (`implement ∈ step ids`) in `kernel`, consumed by both charter and runtime; delete slice-1's charter-local duplicate.
**Independent Test**: kernel reader fails closed on malformed shapes exactly as slice 1 pinned; `kernel`↔`runtime` parity on step ids; charter resolves custom types unchanged through the shim.
**Prompt**: `/tasks/WP01-kernel-shared-parser-and-rule.md`
**Requirement Refs**: FR-006, C-004, SC-004, NFR-003

### Included Subtasks
T001 New `src/kernel/mission_runtime_shape.py`: `read_runtime_shape_step_ids(path) -> list[str]` (slice-1 fail-closed contract) + `step_ids_declare_wp_iteration(step_ids) -> bool` (`"implement" in step_ids`).
T002 Shim `charter.offering.missions.mission_step_repository.resolve_runtime_shape_steps` to the kernel reader; delete the local `_runtime_shape_step_ids`.
T003 [P] kernel unit test for the fail-closed reader + the wp_driven rule; re-point the charter↔runtime parity test to `kernel`↔`runtime`.

### Dependencies
- None.

---

## Work Package WP02: Capability facets on the resolved mission type (Priority: P0)

**Goal**: Expose `wp_driven` (via the kernel rule over the resolved step ids) and `requires_substantive_spec` (authored on the mission-type definition; built-in defaults software-dev/research = true, documentation/plan = false; custom default false) on `ResolvedMissionType` and the `charter.offering.api` public surface.
**Independent Test**: each built-in resolves the expected capability values; a custom type that declares `requires_substantive_spec: true` resolves true; additive surface (no existing field changed).
**Prompt**: `/tasks/WP02-charter-capability-facets.md`
**Requirement Refs**: FR-001, FR-002, NFR-002, C-001, C-002

### Included Subtasks
T004 Add `wp_driven` + `requires_substantive_spec` to `ResolvedMissionType` (`mission_type_profiles.py`); derive `wp_driven` via the kernel rule over the resolved action_sequence/steps; read `requires_substantive_spec` from the mission-type definition with built-in defaults.
T005 Expose both on the `charter.offering.api` surface (additive).
T006 [P] Tests for all four built-ins' capability values + a custom declared-true case + additive-surface assertion.

### Dependencies
- WP01 (kernel rule).

---

## Work Package WP03: Site 1 — WP-advance guard on `wp_driven` + cores routing fix (Priority: P0)

**Goal**: The implement/review WP-advance guard fires for any `wp_driven` mission; a `wp_driven` custom family's implement/review guards route through `_evaluate_wp_iteration_guard` (fail-closed) instead of raising/​swallowing `UnregisteredMissionFamilyError`.
**Independent Test**: a custom `wp_driven` mission holds at implement with a WP pending (was: silently advanced); `software-dev` byte-identical; `plan` stays non-WP-driven.
**Prompt**: `/tasks/WP03-runtime-wp-driven-guard.md`
**Requirement Refs**: FR-003, FR-004, NFR-001, SC-001

### Included Subtasks
T007 `runtime_bridge_io.py`: derive `wp_driven` from the frozen DAG via the kernel rule; carry it as a bool fact on the `gather_artifact_presence` snapshot.
T008 `runtime_bridge_composition.py:496`: set `wp_advance_ready` for any `wp_driven` mission (not literal software-dev).
T009 `runtime_bridge_cores.py`: route a `wp_driven`-flagged family's implement/review through `_evaluate_wp_iteration_guard` instead of raising `UnregisteredMissionFamilyError`.
T010 [P] Red-first: custom `wp_driven` mission blocks advance with a WP pending + no-op controls (software-dev parity, plan non-WP-driven).

### Dependencies
- WP01 (kernel rule).

---

## Work Package WP04: Site 4 — substantive-spec prerequisite on the capability (Priority: P1)

**Goal**: The resume substantive-spec prerequisite runs for any `requires_substantive_spec` mission type (read from the capability), not the `{software-dev,research}` literal; documentation/plan still bypass.
**Independent Test**: a custom `requires_substantive_spec` type's thin committed spec fails the probe; documentation/plan committed specs pass.
**Prompt**: `/tasks/WP04-substantive-spec-capability-gate.md`
**Requirement Refs**: FR-005, NFR-001, SC-002

### Included Subtasks
T011 `mission_check_prerequisites.py:429`: replace the `{software-dev,research}` literal with the `requires_substantive_spec` capability from the resolved mission type; keep `is_substantive` in specify_cli.
T012 [P] Red-first: custom substantive type's thin spec fails; documentation/plan pass (regression controls).

### Dependencies
- WP02 (reads the capability).

---

## Work Package WP05: Site-2 deliberate non-change + site-5 scope-out (Priority: P2)

**Goal**: Assert `runtime_bridge.py:878` stays software-dev-literal with a custom non-WP step still blocking via composition-dispatch Phase 3 (not this pre-check); record site 5 (template precedence) as out of scope in the changelog.
**Independent Test**: the witness test goes green; changelog entry present.
**Prompt**: `/tasks/WP05-site2-nonchange-and-changelog.md`
**Requirement Refs**: FR-007, C-003

### Included Subtasks
T013 Runtime test: a custom non-WP step blocks via Phase 3, not the CLI pre-check (witness that site 2 needs no change).
T014 Changelog entry for the capability contract + the site-5 out-of-scope note.

### Dependencies
- None.

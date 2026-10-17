# Mission Specification: Mission-type capability contract for custom types

**Mission Branch**: `kitty/mission-mission-type-capability-contract-01M54BVT`
**Created**: 2026-10-17
**Status**: Draft
**Input**: GitHub issue #6315 (child of #4983), follow-on to the merged slice-1 #6317. Operator decision: build the formal capability contract now (not scattered literals); defer the `code_producing` capability and its gate to #6327 / #6328.

## Summary

Several governance gates still decide a mission's rigour by testing the literal
`software-dev` family name, so an activated **custom** mission type is treated as
second-class even when its runtime declares the same lifecycle. This mission
converges those literals onto an explicit **capability contract** carried by the
resolved charter-offering mission-type object (`ResolvedMissionType`), exposed
through the charter offering public surface, and routes the gates through the
capabilities instead of the family name.

Two capabilities are introduced now:

- **`wp_driven`** — the mission iterates work packages through `implement`/`review`.
  Drives the WP-advance guard, and fixes a real defect: a custom WP-driven family
  currently hits `UnregisteredMissionFamilyError` in the pure guard core and the
  WP-advance guard is **silently skipped**, so such a mission can advance past
  `implement`/`review` with work packages still pending.
- **`requires_substantive_spec`** — the mission type's spec must carry substantive
  content (not just be committed). Drives the substantive-spec resume prerequisite.

The mission also pays down slice-1 debt by moving the charter-local runtime-shape
step-id parser into `kernel` (the single layer both `charter` and `runtime`
import), deleting the duplicate.

The `code_producing` capability and its consumer (the review-time
implementation-commit prerequisite, formerly "site 3") are **out of scope**,
deferred to #6327 and #6328 — that gate can only be generalized once the property
exists on the DTO.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A custom WP-driven mission type gets the WP-advance guard (Priority: P1)

A custom mission type whose runtime declares `implement`/`review` steps iterates
its work packages like `software-dev`: `spec-kitty next` holds at `implement`/
`review` until every work package has reached an accepting lane, instead of
silently advancing with work still pending.

**Why this priority**: Without it a custom dev-rigour mission can "complete"
with unfinished work packages — a correctness hole, not cosmetics. It is the
highest-priority sibling named in #6315.

**Independent Test**: Drive a custom WP-driven mission to the `implement` board
with a work package still `planned`; assert the decision holds at the WP step
(advance blocked), and that `software-dev` behaves identically and `plan` (a
non-WP family with a lone planning `review`) is unaffected.

**Acceptance Scenarios**:

1. **Given** a custom mission type whose resolved runtime declares an `implement`
   step and a work package still pending, **When** `next` decides the action at
   the implement/review board, **Then** it holds at the WP step (does not advance)
   — and it no longer raises/silently-swallows `UnregisteredMissionFamilyError`.
2. **Given** the built-in `plan` mission type (declares `review` but not
   `implement`), **When** resolved, **Then** `wp_driven` is false and its
   behaviour is byte-identical to today.

---

### User Story 2 - A substantive-spec mission type enforces a substantive spec (Priority: P1)

A mission type that requires a substantive specification (today: `software-dev`
and `research`) refuses to proceed past a committed-but-empty spec; a type that
does not (today: `documentation`, `plan`, and custom types without a spec schema)
is unaffected.

**Why this priority**: The current allow-list (`mission_type not in
{"software-dev","research"}`) cannot admit a custom type that genuinely has a
substantive-spec schema, and naively removing it would wrongly force
`documentation`/`plan` to carry FR rows.

**Independent Test**: A custom type with a substantive-spec schema and a thin
committed spec fails the resume prerequisite; `documentation`/`plan` committed
specs still pass.

**Acceptance Scenarios**:

1. **Given** a mission type with `requires_substantive_spec = true` and a
   committed-but-non-substantive spec, **When** the resume prerequisite is checked,
   **Then** it fails closed asking for substantive content.
2. **Given** `documentation` or `plan` (`requires_substantive_spec = false`) with a
   committed spec, **When** checked, **Then** it passes unchanged.

---

### User Story 3 - One canonical runtime-shape parser (Priority: P2)

The runtime-shape step-id reader lives in one place that both `charter` and
`runtime` consume, instead of the charter-local duplicate slice 1 had to add.

**Why this priority**: Pays down the single-canonical-authority debt #6315 names;
removes the silent-drift risk between two parsers.

**Independent Test**: The `kernel` reader and the `runtime` loader extract the
same ordered step ids from one fixture (parity test), and charter resolves custom
types through the shared reader with no behavioural change.

**Acceptance Scenarios**:

1. **Given** a valid `mission-runtime.yaml`, **When** the `kernel` reader and the
   `runtime` loader each parse it, **Then** they return identical ordered step ids.
2. **Given** a malformed runtime shape, **When** the `kernel` reader parses it,
   **Then** it fails closed (`[]`) exactly as slice 1 pinned.

### Edge Cases

- A custom mission type that declares neither capability resolves conservative
  defaults (`wp_driven` from the DAG; `requires_substantive_spec = false`) so no
  existing custom type silently gains a gate.
- The pure guard core must learn `wp_driven` as a plain boolean fact (it cannot
  read disk); the capability is computed in the I/O seam and carried on the
  snapshot.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | `wp_driven` capability on the resolved mission-type DTO | As a consumer, I want the resolved charter-offering mission type to expose whether it is WP-driven so gates stop testing the family name. | High | Open | [build] | no — paired with the non-WP `plan` control |
| FR-002 | `requires_substantive_spec` capability on the DTO | As a consumer, I want the resolved mission type to expose whether its spec must be substantive. | High | Open | [build] | no — paired with the documentation/plan false control |
| FR-003 | WP-advance guard keyed on `wp_driven` | As a custom-type user, I want the implement/review WP-advance guard to fire for any wp_driven mission so work cannot advance with WPs pending. | High | Open | [build] | no — paired with the WPs-pending control |
| FR-004 | wp_driven custom families route through the WP-iteration guard, not `UnregisteredMissionFamilyError` | As a maintainer, I want a wp_driven custom family's implement/review guards evaluated (fail-closed) instead of silently skipped. | High | Open | [build] | no — red-first: today it silently advances |
| FR-005 | Substantive-spec prerequisite keyed on `requires_substantive_spec` | As a custom-type user, I want the substantive-spec resume gate driven by the capability, not the `{software-dev,research}` literal, without breaking documentation/plan. | High | Open | [build] | no — paired with the documentation/plan pass control |
| FR-006 | Runtime-shape step-id parser lives in `kernel` | As a maintainer, I want one canonical runtime-shape reader imported by both charter and runtime, replacing the charter-local duplicate. | Medium | Open | [build] | no — paired with the kernel↔runtime parity test |
| FR-007 | Site `runtime_bridge.py` non-WP pre-check stays software-dev-only by design | As a maintainer, I want the CLI-native non-WP pre-check left software-dev-literal, with a custom non-WP step still blocking via composition-dispatch Phase 3 (not this pre-check). | Medium | Open | [ratchet] | no — paired as the deliberate-non-change witness |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Built-in parity | `software-dev`, `research`, `documentation`, `plan` resolve byte-identical decisions and capabilities-equivalent behaviour before and after (0 diffs across the existing runtime + prerequisite test suites). | Reliability | High | Open |
| NFR-002 | Additive public surface | The capability fields are additive to the charter-offering resolved mission-type surface (`charter.offering.api`); no existing field renamed or removed, no existing consumer broken. | Compatibility | High | Open |
| NFR-003 | Quality gates clean | New/changed code passes `ruff check`, `ruff format --check`, `mypy` with zero new issues; complexity ≤ 15. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Single mission-type authority | Capabilities are a facet of the existing `ResolvedMissionType`; no competing resolver is introduced. | Technical | High | Open |
| C-002 | Derivation with conservative default | Capability values are derived at resolution from the mission type's own definition (`wp_driven` ⇐ `implement ∈ action_sequence`/DAG; `requires_substantive_spec` from the existing substantive-spec field-declaration seam), defaulting conservatively when undeclared. Explicit pack-authored declaration of these two is a later extension, not required here. | Technical | High | Open |
| C-003 | Scope fence | The `code_producing` capability (#6327) and its gate (#6328, the worktree implementation-commit prerequisite) and the template-precedence site (`runtime_bridge_io.py:665`) are out of scope. | Technical | High | Open |
| C-004 | Layer chain | `kernel` is the home for the shared parser (charter cannot import runtime/mission_runtime); runtime's richer `load_mission_template_file` is NOT replaced — the kernel reader is the minimal id+title reader, parity-pinned to the runtime loader. | Technical | High | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A custom WP-driven mission type holds at `implement`/`review` with a work package pending (no silent advance, no `UnregisteredMissionFamilyError`), and `software-dev` is byte-identical. — [build] · no-op passable: no
- **SC-002**: A custom `requires_substantive_spec` type's thin committed spec fails the resume prerequisite while `documentation`/`plan` committed specs pass. — [build] · no-op passable: no
- **SC-003**: The existing runtime decision + prerequisite + mission-type resolution suites show 0 behavioural diffs for the four built-in families. — [ratchet] · no-op passable: no
- **SC-004**: Exactly one runtime-shape step-id parser exists (in `kernel`); the charter-local duplicate is deleted and the parity test pins `kernel`↔`runtime`. — [build] · no-op passable: no

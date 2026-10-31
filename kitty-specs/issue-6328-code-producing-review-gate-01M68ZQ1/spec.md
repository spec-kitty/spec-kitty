# Mission Specification: Enforce the implementation-commit review prerequisite from the `code_producing` capability

**Mission Branch**: `issue-6328-code-producing-review-gate`
**Created**: 2026-10-31
**Status**: Draft
**Input**: User description: "Issue #6328 — before a work package may be reviewed, spec-kitty verifies that implementation commits exist on the work package's lane. Today that review-readiness prerequisite runs only for the `software-dev` family, via a `mission_type == "software-dev"` literal in the review-readiness check. A custom code-producing mission type therefore bypasses it. Make the prerequisite apply to any mission type whose `code_producing` capability is true."

## Problem statement

`_validate_ready_for_review` (`src/specify_cli/cli/commands/agent/tasks_parsing_validation.py`)
runs Check 2 — the worktree-state prerequisite, which includes
`_check_implementation_commit_present` — only under the literal

```python
if mission_type == MISSION_TYPE_SOFTWARE_DEV:
```

`#6315` converged the *other* `software-dev` comparisons onto capabilities
(`wp_driven`, `requires_substantive_spec`) and explicitly deferred this one:
"the code-producing review gate (#6328, which needs the #6327 capability) [is]
out of scope". The consequence today is that an activated custom mission type
that produces code reaches review-readiness with no implementation commit on its
lane, and the gap is invisible until a later gate or until landing.

`code_producing` does not exist anywhere in the tree (verified: `rg -n
code_producing --type py` returns 0 hits, and `git log -S code_producing` returns
only the `#6315` mission dossier). This mission therefore also lands the minimal
`#6327` prerequisite — the property on the resolved mission-type DTO, its
resolver, its built-in defaults and its public accessor — because the `#6328`
consumer cannot be written without it, `#6327` is unclaimed and has no open PR,
and splitting them would leave the shipped code with a capability nobody can
read.

## Scope boundary

**In scope**

- The `code_producing` capability: authored field on the charter-offering
  `MissionType` DTO, built-in defaults, layered (built-in / org / project)
  declaration, resolver, lazy memoised facet on `ResolvedMissionType`, and the
  public `charter.activation.api` accessor.
- The one enforcement site: the review-readiness Check 2 gate in
  `_validate_ready_for_review`, keyed on the capability rather than the family
  name.

**Out of scope (explicitly not touched)**

- The `#6715` / `#5939` evidence gates: `specify_cli/lanes/for_review_gate.py`,
  `consolidation.wp_evidence`, and the `single_branch` / `SINGLE_BRANCH_*` gates.
  They keep their current semantics, exclusion list and error codes. This change
  does not duplicate, widen, or weaken them: it changes *which mission types* the
  pre-existing review-readiness pre-flight applies to, and nothing about what that
  pre-flight checks.
- Other `software-dev` comparison sites whose own issues own them:
  `runtime_bridge_io` template-tier ordering (`#6315` follow-up), `runtime_bridge`
  step-graph guard, and `mission_check_prerequisites` (already capability-keyed).
- Template precedence.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A custom code-producing type cannot reach review with nothing implemented (Priority: P1)

An operator runs an activated custom mission type that produces code. A work
package has no commit on its lane beyond the base. When the operator moves the
work package to `for_review`, review-readiness fails closed and names the missing
implementation commits, exactly as `software-dev` does today.

**Why this priority**: This is the defect. Without it the mission delivers
nothing.

**Independent Test**: Resolve a custom type that declares `code_producing: true`,
run the review-readiness pre-flight with no lane commit, and assert it is blocked
with the implementation-commit guidance.

**Acceptance Scenarios**:

1. **Given** a code-producing mission type with a work package that has no implementation commits on its lane, **When** review-readiness is evaluated, **Then** it fails closed and names the missing implementation commits.
2. **Given** a code-producing mission type whose work package has implementation commits, **When** review-readiness is evaluated, **Then** the implementation-commit prerequisite passes.

---

### User Story 2 - Non-code-producing types stay unaffected (Priority: P1)

A documentation, research, plan, or custom non-code mission type keeps reaching
review without an implementation commit, because the prerequisite does not apply
to it.

**Why this priority**: Equal and opposite to US1 — a capability gate that fires on
the wrong side is as wrong as one that never fires, and it would break four
built-in families.

**Independent Test**: Run the pre-flight for `research` / `documentation` / `plan`
with no lane commit and assert it is not blocked, while `software-dev` on the same
fixture is blocked (same-fixture positive control).

**Acceptance Scenarios**:

1. **Given** a non-code-producing mission type, **When** review-readiness is evaluated, **Then** the implementation-commit prerequisite is not applied.
2. **Given** the built-in `software-dev` family, **When** its capabilities are resolved, **Then** `code_producing` is `true` and the prerequisite still applies exactly as before.

---

### User Story 3 - The capability is readable from the charter offering public surface (Priority: P2)

A consumer outside `charter.activation` asks "does this mission type produce
code?" through `charter.activation.api` instead of testing the family name, and a
charter-pack / org / project type can declare its own value.

**Why this priority**: This is what stops the next `software-dev` literal from
being written. It is the `#6327` deliverable.

**Independent Test**: Resolve the four built-ins, a custom type declaring
`code_producing: true`, a custom type declaring `code_producing: false` and a
custom type declaring nothing, and assert `code_producing_for` answers
`true/false/true/false/false`.

**Acceptance Scenarios**:

1. **Given** the built-in `software-dev` mission type, **When** its capabilities are resolved, **Then** `code_producing` is `true`.
2. **Given** the built-in `documentation`, `research` or `plan` mission type, **When** resolved, **Then** `code_producing` is `false`.
3. **Given** a custom mission type that declares `code_producing: true`, **When** resolved, **Then** the capability is `true` and available through the public surface.
4. **Given** a custom mission type that declares nothing, **When** resolved, **Then** `code_producing` defaults to `false`.

---

### Edge Cases

- **Mission type cannot be resolved at all** (missing charter config, unknown
  type, unreadable pack): the pre-flight must not crash. `code_producing_for`
  falls back to the built-in default map, so `software-dev` keeps its gate and an
  unknown type conservatively bypasses — the same contract
  `requires_substantive_spec_for` already has.
- **Mission with no `meta.json` / no mission type**: `get_mission_type` already
  yields a fallback; the capability resolver must treat it as its built-in default
  and not raise.
- **`--force`**: the pre-flight already returns success before any check runs;
  unchanged.
- **A repo-root / single-branch work package**: the repo-root arm of the
  worktree-state prerequisite (`_validate_repo_root_workspace`) is unchanged; it
  already delegates to the shared claim-base gate.
- **Both gates firing**: a code-producing custom type now fails at the
  review-readiness pre-flight (this change) *and*, if it ever got past, at the
  surface-neutral `#6715` `for_review` gate. Those are two pre-existing layers at
  two different points; this change adds no third.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | `code_producing` on the MissionType DTO | As a charter author, I want to declare whether a mission type produces code so that gates can ask instead of testing a family name. | High | Open | [build] | no |
| FR-002 | Built-in `code_producing` defaults | As an operator, I want `software-dev` to resolve `code_producing = true` and `research`/`documentation`/`plan` `false` so that built-in behaviour is unchanged. | High | Open | [build] | no |
| FR-003 | Conservative default for undeclared custom types | As a maintainer, I want an undeclared custom type to resolve `false` so that no existing custom type silently gains code-rigour gates. | High | Open | [build] | no |
| FR-004 | Lazy `code_producing` facet on `ResolvedMissionType` | As a runtime caller, I want the capability resolved lazily and memoised so that the hot `action_sequence` path keeps its single layered-roster read. | Medium | Open | [build] | no |
| FR-005 | Public accessor `code_producing_for` | As a CLI consumer, I want one accessor on `charter.activation.api` so that I never reach `charter.activation` internals. | High | Open | [build] | no |
| FR-006 | Review-readiness prerequisite keyed on the capability | As an operator, I want the worktree-state prerequisite to apply to any code-producing type so that a custom code type cannot reach review with nothing implemented. | High | Open | [build] | no |
| FR-007 | Non-code-producing types bypass the prerequisite | As an operator, I want documentation/research/plan/custom-non-code missions unchanged so that their review flow does not demand implementation commits. | High | Open | [build] | no |
| FR-008 | `#6715`/`#5939` evidence gates untouched | As a maintainer, I want those gates byte-unchanged so that this fix cannot weaken or duplicate them. | High | Open | [ratchet] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Resolution failure never crashes the pre-flight | A resolution error (unknown/unactivated type, unreadable config) returns the built-in default instead of raising; covered by a test that patches the resolver to raise. | Reliability | High | Open |
| NFR-002 | No new eager read on the hot path | `code_producing` is a `cached_property` behind a thunk, like `requires_substantive_spec`; `resolve_mission_type_context` performs no additional roster/disk read for a caller that only reads `action_sequence` (asserted by a call-count test). | Performance | High | Open |
| NFR-003 | Module boundary respected | `specify_cli` reaches the capability only through `charter.activation.api`; no new import of `charter.activation.mission_type_profiles` from `specify_cli`, enforced by the existing architectural boundary test. | Maintainability | High | Open |
| NFR-004 | One owning list | The built-in `code_producing` defaults live in exactly one map beside `BUILTIN_REQUIRES_SUBSTANTIVE_SPEC`; no second roster or per-site literal is introduced. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Do not change the evidence gates | `lanes/for_review_gate.py`, `consolidation.wp_evidence` and the `SINGLE_BRANCH_*` gates are read-only for this mission. | Technical | High | Open |
| C-002 | Preserve user-facing behaviour for built-ins | `software-dev` keeps the gate; the three other built-ins keep bypassing it. | Technical | High | Open |
| C-003 | Do not add a required parameter to `_validate_ready_for_review` | Its injected collaborators are a live monkeypatch contract across the test suite; the capability resolves from `main_repo_root` + `mission_type` inside the function. | Technical | High | Open |

### Key Entities

- **`MissionType`** (`charter.offering.missions.models`): the authored,
  layered mission-type descriptor; gains the optional `code_producing` field
  (`None` = undeclared).
- **`ResolvedMissionType`** (`charter.activation.mission_type_profiles`): the
  in-memory bundle consumers read; gains the lazy `code_producing` facet.
- **Review-readiness pre-flight** (`_validate_ready_for_review`): the
  `for_review` pre-check under `agent tasks move-task`; its Check 2 gate becomes
  capability-keyed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A custom mission type declaring `code_producing: true`, with a work package and no lane commit, is refused by the review-readiness pre-flight with the implementation-commit guidance (and its `false` twin on the same fixture passes). — [build] · no-op passable: no
- **SC-002**: Zero `mission_type == "software-dev"` (or equivalent) comparisons remain in the review-readiness path. — [build] · no-op passable: no
- **SC-003**: `software-dev`, `research`, `documentation` and `plan` produce the same pre-flight verdicts as on `origin/main` `dfe9efb0e8`. — [ratchet] · no-op passable: no
- **SC-004**: The `#6715`/`#5939` gate modules and their tests are unchanged by this mission's diff (`git diff --stat origin/main -- src/specify_cli/lanes/for_review_gate.py src/specify_cli/lanes/consolidation.py` is empty). — [ratchet] · no-op passable: no
- **SC-005**: `code_producing_for` answers `true, false, false, false` for the four built-ins and `false` for an undeclared custom type. — [build] · no-op passable: no

# Mission Specification: charter resynthesize project-directive layer split

**Mission Branch**: `issue-6768-charter-resynth-project-directive`
**Created**: 2026-10-31
**Status**: Ready for planning
**Issue**: [#6768](https://github.com/spec-kitty/spec-kitty/issues/6768) (P0)
**Input**: "charter resynthesize refuses every project directive: the CLI snapshot lists PROJECT_* directives as built-in DRG nodes (blocks charter amendments)"

## Problem Statement

`charter resynthesize --topic directive:<PROJECT_xxx>` refuses to regenerate a
project's own directive:

```text
ProjectDRGValidationError: Additive-only violation (FR-020 / EC-6):
URN 'directive:PROJECT_002' already exists in the built-in DRG layer.
built_in_nodes=16, colliding_urn='directive:PROJECT_002'
```

The refusal happens inside `charter/activation/synthesizer/project_drg.py::emit_project_layer`,
whose additive-only invariant is "a synthesized artifact may not shadow a **built-in** node".
That invariant is correct. The input it is given is not.

`src/specify_cli/cli/commands/charter/_synthesis.py::_build_synthesis_request` assembles
`SynthesisRequest.drg_snapshot` from `directives_for_synthesis` — the config-activated
directive list, i.e. every built-in, org **and project** directive in force. Every consumer
that wants "the built-in layer" reads that one snapshot
(`_built_in_drg_from_snapshot` / `_built_in_drg_from_request`, in three call sites), so a
project-layer directive that is *activated* is classified as *built-in* and collides with
itself the moment it is the resynthesis target.

Two project states reach this today (both reproduced on `main` at `d75e0bc5`):

1. A project directive the project **authored itself** and then registered through
   `charter activate directive <stem>`: it is in `activated_directives` and in the manifest
   as a `project-direct-write` registration, which is deliberately *not* synthesis ownership.
2. A synthesis-created project directive whose ownership record was lost or rewritten
   (the state #6510's own remedy text names).

#6510 already narrowed the symptom for one case — ids the manifest records as
synthesis-owned are dropped from the snapshot — but that is an ownership filter on top of a
mis-classified snapshot, not a layer split. It also cannot be extended to case (1): those
directives are project output the project owns even though synthesis did not create them.

Removing project directives from the snapshot is **not** a fix on its own, and the issue
records why: the same snapshot is the reference universe for EC-2 source-URN validation
(`targets.build_targets`) and for the pre-write validation gate (`validation_gate.validate`).
Drop the project nodes and the project's companion tactics
(`directive:PROJECT_x --suggests--> tactic:how-we-apply-project-x`) fail closed as dangling
against the "built-in DRG snapshot". The snapshot is doing two jobs; the fix is to give each
job the layer it actually needs.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Amend a project directive the project authored (Priority: P1)

A maintainer of a project (for example `spec-kitty-charter`) hand-authors a project directive,
activates it with `charter activate directive <stem>`, and later needs to regenerate it from an
edited interview answer with `charter resynthesize --topic directive:PROJECT_007`. Today the
command refuses, naming the directive as a built-in DRG node. It must regenerate.

**Why this priority**: P0. Every charter amendment of a project directive is blocked, which
blocks the downstream project's own governance work.

**Independent Test**: Drive the real `charter activate` → `charter resynthesize` commands on a
"synthesized once" fixture project whose project pack holds an authored directive, and assert
exit 0 with the artifact rewritten.

**Acceptance Scenarios**:

1. **Given** a project with an authored `PROJECT_007` directive registered by `charter activate`,
   **When** `charter resynthesize --topic directive:PROJECT_007` runs, **Then** it exits 0 and
   rewrites the directive, and no refusal names `colliding_urn`.
2. **Given** the same project, **When** the same command runs twice, **Then** the second run is
   either a successful regeneration or a no-op, never a refusal.

---

### User Story 2 - The additive-only gate still refuses real built-in shadowing (Priority: P1)

The FR-020 / EC-6 invariant exists so a project can never overwrite shipped doctrine. Fixing
the classification must not turn the check into a no-op: a target whose URN genuinely exists in
the shipped built-in DRG must still raise.

**Why this priority**: P1. A fix that silences the gate would be worse than the defect.

**Independent Test**: On the same fixture, emit a project layer whose target URN is a shipped
built-in URN and assert the same `ProjectDRGValidationError` with `colliding_urn` set.

**Acceptance Scenarios**:

1. **Given** the shipped built-in DRG, **When** a synthesis target's URN equals a shipped
   built-in node URN, **Then** `emit_project_layer` raises the FR-020 / EC-6 additive-only
   violation and carries `colliding_urn`.
2. **Given** the same emit with a project-layer target URN, **Then** no collision is raised
   (the positive control that the probe can see the difference).

---

### User Story 3 - Project tactics that reference project directives keep validating (Priority: P1)

The companion tactics (`how-we-apply-project-00x`) carry
`source_urns=("directive:PROJECT_00x",)`. Those references must keep resolving after the layer
split, both for the EC-2 early gate and for the pre-write validation gate.

**Why this priority**: P1. The issue records that a naive "remove project nodes from the
snapshot" fix breaks exactly this; it is the other half of the same fix.

**Independent Test**: Resynthesize the companion tactic of a project directive on the fixture
and assert exit 0 plus a persisted `directive:PROJECT_00x --suggests--> tactic:...` edge.

**Acceptance Scenarios**:

1. **Given** a project directive `PROJECT_007` and its companion tactic, **When** the tactic is
   resynthesized, **Then** it exits 0 and the tactic's reference to `directive:PROJECT_007`
   resolves in the persisted project graph.
2. **Given** a project tactic that references a URN no layer declares, **Then** validation still
   fails closed (the reference universe is wider, not unchecked).

---

### Edge Cases

- **Org layer**: an activated org directive is in the reference universe but not in the
  built-in-only layer. A project artifact may override an org node (documented
  `merge_three_layers` precedence) while it may not override a built-in node; the additive-only
  check stays built-in-only, as `emit_project_layer`'s contract already states.
- **Absent built-in pack**: if the shipped built-in graph cannot be loaded, the request falls
  back to the previous single-snapshot behavior rather than failing with an unrelated load error
  (the existing pre-flight already fails closed earlier with `BuiltInPackMissing`).
- **Backward compatibility**: a `SynthesisRequest` built without the new field (every existing
  test, fixture and external caller) must behave exactly as before.
- **Fixture stability**: `normalize_request_for_hash` is documented "do not change" — the new
  field must not enter the fixture hash, so existing generated-artifact fixtures keep loading.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Resynthesize an activated project directive | As a project maintainer, I want `charter resynthesize --topic directive:<PROJECT_xxx>` to succeed for a project directive that is active but not synthesis-owned, so that a project can amend its own directives. | High | Open | [build] | no |
| FR-002 | Built-in shadowing still refuses | As a maintainer, I want the FR-020 / EC-6 additive-only violation to keep firing for a genuine built-in URN, so that the layer split cannot become a gate bypass. | High | Open | [ratchet] | yes — paired with FR-001 on the same fixture (one emit collides, one does not) |
| FR-003 | Project references keep resolving | As a project maintainer, I want project tactics that reference project directives to keep validating, so that the layer split does not merely move the refusal to a dangling-reference error. | High | Open | [ratchet] | yes — paired with an undeclared-URN refusal on the same fixture |
| FR-004 | One authored classification | As a maintainer, I want the built-in layer to come from one authored source (the shipped built-in DRG) and the reference universe to be assembled once, so that no consumer re-derives a layer from a list that means something else. | High | Open | [build] | no |
| FR-005 | Backward-compatible request | As a caller of the synthesis library, I want a request without the new built-in layer to behave exactly as before, so that existing callers and fixtures are unaffected. | Medium | Open | [ratchet] | yes — pinned by the existing suite |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No added load cost | Building the request adds at most one memoized `load_built_in_graph()` call; the existing pre-write gate stays inside its documented 5 s fail-closed budget (measured by `test_validation_gate.py`). | Performance | Medium | Open |
| NFR-002 | Fixture keys unchanged | `normalize_request_for_hash` output for a request without the new field is byte-identical; every pre-existing generated-artifact fixture still loads. | Reliability | High | Open |
| NFR-003 | No new dependency | The change uses only the shipped DRG loader already imported by the synthesis layer. | Maintainability | Low | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No id-prefix heuristic | The classification may never key on the `PROJECT_` id prefix (the issue's session-local patch did; that is a workaround, not the fix). | Technical | High | Open |
| C-002 | Charter layering | The built-in layer is read through `charter.offering.drg.loader`; the CLI keeps only the request assembly. | Technical | High | Open |
| C-003 | No gate weakening | Only the *classification* of the additive-only input changes; the invariant, its error type and its `colliding_urn` contract are untouched. | Business | High | Open |

### Key Entities

- **Built-in layer**: the shipped DRG (`load_built_in_graph()`); the only layer the
  additive-only check may refuse a target against.
- **Reference universe**: the set of URNs a target's `source_urns` may name — shipped built-in
  plus org plus project nodes; today's `SynthesisRequest.drg_snapshot` role.
- **Synthesis request**: the frozen envelope handed to adapters; gains an explicit built-in
  layer field that defaults to `None` ("use the reference snapshot", pre-fix behavior).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `charter resynthesize --topic directive:<PROJECT_xxx>` exits 0 for an activated, project-authored directive with no source patch (reproduced red before the fix on the same fixture). — [build] · no-op passable: no
- **SC-002**: The FR-020 / EC-6 violation still raises for a shipped built-in URN on the same fixture, with `colliding_urn` populated. — [ratchet] · no-op passable: yes — the paired FR-001 case proves the probe distinguishes the two inputs
- **SC-003**: A project companion tactic referencing a project directive resynthesizes with exit 0 and its `suggests` edge persists; an undeclared URN still refuses. — [ratchet] · no-op passable: yes — the paired undeclared-URN refusal proves the universe is still checked
- **SC-004**: The existing charter synthesis suites (`tests/charter/synthesizer`, `tests/charter`) stay green with no fixture regeneration. — [ratchet] · no-op passable: yes — guarded by the new tests above, which fail without the change

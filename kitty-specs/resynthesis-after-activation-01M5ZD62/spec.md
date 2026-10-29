# Mission Specification: Re-synthesis after activation

**Mission Branch**: `issue-6510-resynthesis-after-activation`
**Created**: 2026-10-27
**Status**: Draft
**Input**: #6510 and #4226. `charter synthesize` and `charter resynthesize` refuse with
`colliding_urn='directive:PROJECT_001'` once an explicit `activated_directives` list contains the
project directive that synthesis itself created. Phase 0 research: [research.md](research.md).

## Intent Summary (confirmed 2026-10-27)

- **Actor:** an operator, or an agent following the implement gate's remedy
  (`run spec-kitty charter synthesize`), in a project with a synthesized charter.
- **Trigger:** they activate or deactivate any directive, so `activated_directives` becomes an
  explicit list that contains the project's own synthesized directive (for example
  `001-project-intent-directive`, which resolves to `PROJECT_001`), and then they run
  `charter synthesize` or `charter resynthesize`.
- **Outcome:** synthesis succeeds and regenerates that directive in place. The directive stays
  activated, so `charter context` still delivers it to agents.
- **Rule:** a directive that synthesis owns (one recorded in its synthesis ownership record) is
  synthesis output, never synthesis input. The additive-only check still refuses a real clash with a
  built-in, org or hand-authored (`charter new`) artifact.
- **Exception:** an activated project directive that collides with a synthesis target but has no
  ownership record refuses, and the refusal says how to recover. The fix never removes a directive
  from activation.
- **Out of scope:** unbounded `.failed` staging directories, and the neutrality-gate refusal on a
  generated companion tactic (both reported in #4226; filed as follow-ups).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Re-synthesize after activating a directive (Priority: P1)

An operator has synthesized their charter once. They activate a further built-in directive and run
`charter synthesize` again, as the activation output and the implement gate tell them to.

**Why this priority**: today this always fails. It blocks the documented activate-then-resynthesize
workflow and, through the implement gate, every work-package claim in the repository (#4226).

**Independent Test**: in a project whose first synthesis promoted `PROJECT_001`, activate one
directive, run `charter synthesize`, and observe exit 0 with the project directive regenerated.

**Acceptance Scenarios**:

1. **Given** a synthesized charter whose explicit `activated_directives` list contains the project's
   synthesized directive, **When** the operator runs `charter synthesize`, **Then** it exits 0, the
   project directive is rewritten in place under the same identity, and no additive-only refusal
   appears.
2. **Given** the same project, **When** the operator runs `charter resynthesize --topic
   directive:PROJECT_001` (the worked example in that command's help), **Then** it exits 0 and
   regenerates that directive.
3. **Given** the same project after a successful re-synthesis, **When** an agent loads
   `charter context --action implement`, **Then** the project directive's rule text is still
   delivered.
4. **Given** the same project, **When** synthesis runs, **Then** it does not demand a companion tactic
   for the project's own synthesized directive (`how-we-apply-project-NNN`).

---

### User Story 2 - A real clash still refuses, and says why (Priority: P2)

An operator's activated directive list contains a directive the synthesizer did not create, and a
synthesis target would produce the same identity.

**Why this priority**: the additive-only rule protects built-in, org and hand-authored doctrine from
being overwritten. The fix must not weaken it, and the refusal must stop sending operators to rename
the tool's own identifiers (#4226).

**Independent Test**: in a project with an activated, hand-authored project directive whose identity
a synthesis target also produces, run `charter synthesize` and observe the refusal text.

**Acceptance Scenarios**:

1. **Given** an activated project-layer directive with no synthesis ownership record whose identity a
   synthesis target produces, **When** the operator runs `charter synthesize`, **Then** it refuses
   (exit 1). The message names the directive, says it was not created by synthesis, and names the
   recovery steps. It does not tell the operator to choose new identifiers.
2. **Given** a synthesis target whose identity matches a built-in or org node, **When** synthesis
   runs, **Then** it still refuses with the additive-only violation, and the message says which kind
   of artifact the target collides with.
3. **Given** an activated hand-authored project directive that no synthesis target produces, **When**
   synthesis runs, **Then** that directive is treated exactly as today: it stays in the snapshot and
   still gets its companion tactic.

### Edge Cases

- The ownership record is missing or empty (a first run, or a project that never synthesized): no
  directive counts as synthesis-owned, so behaviour is unchanged from today.
- The ownership record is unreadable: synthesis refuses with the existing fail-closed error for an
  unreadable record. It never guesses ownership.
- The activation key is absent (three-state "all"): the snapshot is empty today and stays empty.
- The operator deactivated the project directive: it is not in the snapshot today and is not added.
- A synthesis-owned directive is no longer a synthesis target (the interview changed): it is left out
  of the snapshot all the same. What happens to it on disk is the existing reconcile and `--prune`
  behaviour, unchanged.
- Several synthesis-owned directives (`PROJECT_001`, `PROJECT_002`): all are left out.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Re-synthesis succeeds after activation | As an operator, I want `charter synthesize` to succeed when my explicit activation list contains a directive synthesis created, so that I can re-synthesize after activating doctrine. | High | Open | [build] | no — RED today on the same fixture (exit 1, `colliding_urn`) |
| FR-002 | Targeted resynthesis of the project directive succeeds | As an operator, I want `charter resynthesize --topic directive:PROJECT_001` to regenerate that directive after activation, so that the command's own worked example works. | High | Open | [build] | no — RED today on the same fixture |
| FR-003 | Synthesis-owned directives are not synthesis input | As a maintainer, I want directives recorded as created by synthesis left out of the request's graph snapshot and its selected-directive list, so that synthesis never collides with its own output. | High | Open | [build] | no — paired with FR-006's positive control on the same fixture |
| FR-004 | Delivery is unchanged | As an agent, I want a synthesis-owned project directive that is activated to still appear in `charter context` after re-synthesis, so that no governance is lost. | High | Open | [ratchet] | yes — paired with FR-001: same fixture, synthesis must succeed AND the directive must still be delivered |
| FR-005 | Activation is never rewritten by the fix | As an operator, I want re-synthesis to leave my activation and deny lists as they were, so that the fix does not hide a directive. | High | Open | [ratchet] | yes — paired with FR-001 on the same fixture |
| FR-006 | Additive-only stays strict for real clashes | As a maintainer, I want a synthesis target that collides with a built-in, org or hand-authored node to keep refusing, so that synthesis never overwrites doctrine it does not own. | High | Open | [ratchet] | yes — paired with FR-003: same fixture, an unowned colliding node must still refuse |
| FR-007 | Refusal names the cause | As an operator, I want the collision refusal to say whether the colliding artifact is an unowned project directive or a built-in/org node, and how to recover, so that I do not rename the tool's own identifiers. | Medium | Open | [build] | no — the message text is asserted, and today's text fails the assertion |
| FR-008 | Unowned non-colliding project directives keep today's behaviour | As an operator with hand-authored directives, I want them to stay in the snapshot and keep getting companion tactics, so that the fix changes only synthesis-owned directives. | Medium | Open | [ratchet] | yes — paired with FR-003 on the same fixture |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No added I/O hot spot | Building the synthesis request reads the ownership record at most once per run, and on a project with 50 activated directives the request build takes at most 100 ms longer than on base. | Performance | Medium | Open |
| NFR-002 | Fail closed on unreadable ownership | 0 runs treat a directive as synthesis-owned when the ownership record cannot be read; every such run refuses. | Reliability | High | Open |
| NFR-003 | Quality gates | Changed code has 0 new ruff, `ruff format` or mypy findings, every touched function has complexity ≤ 15, and diff coverage is ≥ 90 %. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | One ownership authority | Ownership comes from the existing synthesis record (manifest/provenance). No new record or second ownership authority is introduced. | Technical | High | Open |
| C-002 | Activation untouched | The fix never adds to, removes from or reorders an activation or deny list (ADR 2026-10-19-1). | Technical | High | Open |
| C-003 | Stay in core, at the request seam | The change lives in core (ADR 2026-10-16-1, Amendment 2026-10-19): the exclusion is made where the synthesis request is built. The additive-only invariant in the synthesizer is not loosened. | Technical | High | Open |
| C-004 | Avoid M2 surfaces | Do not change `reach_only.py` or `reconcile.py` (owned by M2: #6453, #6455, #6456) beyond read-only use of a public helper. | Process | Medium | Open |
| C-005 | Red-first | Each FR's acceptance test is committed failing before the fix and passes after, through the real CLI entry point. | Process | High | Open |

### Key Entities

- **Synthesis ownership record**: the persisted list of artifacts synthesis has produced, each with
  its kind, slug and identity (`artifact_urn`). It is the authority for "this directive is ours".
- **Synthesis request graph snapshot**: the set of upstream nodes synthesis treats as existing,
  read-only input. The additive-only check refuses any target whose identity is already in it.
- **Activated directive list**: the operator's activation choice. It governs delivery; this mission
  only reads it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the #6510 reproduction (synthesize, activate one directive, synthesize again), the
  second synthesis exits 0 where it exits 1 on base. — [build] · no-op passable: no
- **SC-002**: After that run, the project directive's rule text appears in `charter context --action
  implement` output, as it did before activation. — [ratchet] · no-op passable: yes (paired with SC-001)
- **SC-003**: Every collision refusal that remains names the colliding artifact's origin, and 0 of
  them say "must carry new URNs" without naming that origin. — [build] · no-op passable: no
- **SC-004**: 0 changes to activation files during any synthesize/resynthesize run in the mission's
  tests. — [ratchet] · no-op passable: yes (paired with SC-001)

## Assumptions

- The synthesis ownership record already exists after every successful synthesis and records each
  directive's identity. Phase 0 verified this on a live run.
- Whether synthesis should demand a companion tactic for its own directive was never observable: no
  run with that demand could succeed. Dropping the demand changes no shipped output.

## Follow-ups (out of scope)

- Unbounded `.kittify/charter/.staging/*.failed` directories after refused runs (#4226).
- Neutrality-gate refusal on a synthesizer-generated companion tactic (#4226).

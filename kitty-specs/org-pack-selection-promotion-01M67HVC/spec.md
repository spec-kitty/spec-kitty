# Mission Specification: Promote org-pack interview selections on upgrade

**Mission Branch**: `issue-6686-org-pack-selection-promotion`
**Created**: 2026-10-30
**Status**: Draft
**Input**: Issue spec-kitty/spec-kitty#6686 — "Upgrade promotes interview selections against the built-in pack only, so org-pack selections are reported unresolved".

## Context

Two writers turn an interview selection (`answers.yaml` `selected_<kind>`) into an
activation-list entry: the `4.0.0rc8_promote_interview_selections` upgrade step and
`spec-kitty charter interview`. They disagree on the same input.
`charter interview` resolves an id through the layer-aware identity authority that
`charter context` reads (#6406/#6407) — project pack, org packs, then built-in — so an
org-pack artifact is promoted. The upgrade step resolves against the built-in pack
alone, so the same org-pack id is reported "Unresolved interview selections skipped
(not promoted)" and is left out of the activation list.

The #6678 landing review also flagged the two resolution loops (index probe + dedupe +
unresolved collection) as a second copy of one rule. This mission removes the second
copy by moving that loop behind one resolver exposed on the activation layer's public
seam, and routes both writers through it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An org-pack selection survives an upgrade (Priority: P1)

A project runs on an org pack (`charter_packs.org`), selects an org-pack directive or
tactic during `charter interview`, and later runs `spec-kitty upgrade`. The upgrade
promotes the selection into the project's present `activated_<kind>` list instead of
reporting it unresolved.

**Why this priority**: This is the reported defect. Until it is fixed, an org-pack
user's upgrade quietly drops a selection the interview accepted, and the only signal
is a warning that calls a valid id "unresolved".

**Independent Test**: Build a project whose `answers.yaml` selects an org-pack
artifact's declared id, give it a present `activated_directives` list, run the
migration, and assert the org artifact's stem is appended and no unresolved warning is
raised.

**Acceptance Scenarios**:

1. **Given** a project with an org pack and a present `activated_directives` list,
   **When** `answers.yaml` selects an org-pack directive's declared id and the upgrade
   step runs, **Then** the directive's stem is appended to the list and the result
   carries no unresolved warning.
2. **Given** the same project, **When** `charter interview` records the same selection,
   **Then** the interview and the upgrade store the same stem for that id.

---

### User Story 2 - One resolution rule serves both writers (Priority: P2)

A maintainer reading the two writers sees one resolution path, not two. The
layer-aware resolution lives behind the activation layer's public seam like the rest of
that surface, so the upgrade step and the interview cannot drift apart again.

**Why this priority**: The drift is the defect's cause; leaving two loops in place
invites the next layer (project pack, a new kind) to be added to only one of them.

**Independent Test**: Assert both call sites obtain their stems from the shared
resolver (one exported symbol, no local resolution loop), and that a single
layer-aware identity index build per run serves each writer.

**Acceptance Scenarios**:

1. **Given** the shared resolver on the activation layer's public seam, **When** the upgrade step
   and `charter interview` resolve the same selection set, **Then** both get the same
   stems and the same unresolved ids from it.

---

### User Story 3 - A genuinely unknown id is still reported (Priority: P3)

An operator with a stale or misspelled selection keeps the diagnostic they have today:
the id is named as unresolved and is not promoted. An ambiguous directive id keeps its
existing treatment in each writer (reported by the upgrade, refused by the interview).

**Why this priority**: The fix must not turn "reported, never dropped silently" into
"silently dropped" or "silently reinterpreted as another file".

**Independent Test**: On the same fixture that shows an org-pack id promoting, assert
that an id no layer knows is still listed as unresolved and is absent from the written
list.

**Acceptance Scenarios**:

1. **Given** a selection naming an id no layer declares, **When** the upgrade step runs,
   **Then** the result warns with `Unresolved interview selections skipped (not
   promoted): <kind>:<id>` and writes nothing for that id.
2. **Given** a directive identity no file stem can represent, **When** `charter
   interview` promotes, **Then** it still refuses with the collision error before any
   write.

### Edge Cases

- Project-pack (not org-pack) selection: resolved too, because the resolver indexes the
  same layers `charter context` does. Covered by the shared resolver, not by a second
  lookup.
- Org artifact whose stem differs from its declared id: the stem is what is promoted,
  as with built-in artifacts.
- A selection that spells the same artifact twice (declared id and stem): promoted
  once.
- Mission-step-contract selections: they do not resolve in either writer today
  (`kind_vocabulary`); out of scope unless the shared resolver covers them for free.
- An org-pack selection for a kind whose activation key is absent: the key stays absent
  (the #6629 zero-drop rule is unchanged) and no unresolved warning is raised.
- A broken doctrine root: still a failed migration result, not a traceback.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Org-pack selections are promoted | As an org-pack user, I want my interview selection promoted on upgrade so that the upgrade does not discard a selection the interview accepted. | High | Open | [build] | no — a no-op change leaves the org id unresolved on the fixture | 
| FR-002 | Project-pack selections are promoted | As a project-pack user, I want my interview selection promoted on upgrade so that local artifacts resolve like published ones. | Medium | Open | [build] | no — same fixture, project-pack root |
| FR-003 | One shared selection resolver | As a maintainer, I want one resolution rule, exposed on the activation layer's public seam and used by both writers, so that the two cannot drift apart. | High | Open | [build] | no — the duplicated loop is asserted gone at both call sites |
| FR-004 | Unknown ids stay reported | As an operator, I want an id no layer knows reported as unresolved and not promoted so that a stale selection is visible. | High | Open | [ratchet] | yes — paired positive control on the same fixture: the known org id promotes while the unknown one is reported |
| FR-005 | Ambiguity keeps both treatments | As a maintainer, I want the upgrade to report an unrepresentable directive id and the interview to refuse it, so that neither silently drops or reinterprets it. | Medium | Open | [ratchet] | yes — paired with the unambiguous fixture that resolves in both |
| FR-006 | Present lists only | As an operator, I want the promotion to keep writing only present `activated_<kind>` lists so that #6629's absent-key rule is untouched. | High | Open | [ratchet] | yes — paired with the present-list case on the same fixture |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | One index per run | Each writer builds at most one layer-aware identity index per run; the migration resolves the layer roots once, not once per selection. | Performance | Medium | Open |
| NFR-002 | No regression on built-in projects | The existing migration, interview-promotion and activation test modules pass unchanged in behaviour (built-in selections, absent keys, deactivation, seeded-list hint, collision refusal). | Reliability | High | Open |
| NFR-003 | Seam-only reach | The CLI and upgrade layers reach the new resolver only through the activation layer's public seam; the architectural boundary ratchet's frozen row count does not grow. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Resolution only | The activation write path (write target plus the one promotion primitive) is unchanged; only resolution changes. | Technical | High | Open |
| C-002 | Mission-step contracts out of scope | Their resolution is broken in both writers already; not fixed here unless free. | Technical | Medium | Open |
| C-003 | Layer precedence unchanged | The resolver uses the same layer-aware identity authority `charter context` uses (#6407); no new precedence rule is invented. | Technical | High | Open |

### Key Entities

- **Interview selection**: a `selected_<kind>` entry in `.kittify/charter/interview/answers.yaml`; an id or stem in any layer's spelling.
- **Activation stem**: the file-stem spelling an activation list stores; the shared resolver's output.
- **Selection resolver**: the shared, layer-aware resolution rule exposed on the activation layer's public seam; it returns the stem per selection, grouped per `activated_<kind>` key, plus the ids no layer knows.
- **Layer precedence**: project pack first, then org packs last-declared-first, then built-in — the order `charter context` already uses for the same ids.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a project with an org pack, an org-pack directive selected in `answers.yaml` is present in the written `activated_directives` list after the upgrade step, and no unresolved warning names it. — [build] · no-op passable: no
- **SC-002**: The upgrade step and `charter interview` resolve the same selection set to the same stems on the same fixture. — [build] · no-op passable: no
- **SC-003**: A selection naming an id no layer declares is still reported, and the same fixture's known id promotes in the same run. — [ratchet] · no-op passable: yes — positive control is the known-id promotion in the same assertion
- **SC-004**: The migration, interview-promotion, activation-identity and API-reexport test modules pass with zero changed expectations for built-in projects. — [ratchet] · no-op passable: no

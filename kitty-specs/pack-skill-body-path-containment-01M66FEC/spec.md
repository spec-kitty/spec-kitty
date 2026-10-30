# Mission Specification: pack-skill body_path containment uses the shared primitive

**Mission Branch**: `issue-6734-pack-skill-body-path-containment`
**Created**: 2026-10-30
**Status**: Confirmed
**Input**: Issue spec-kitty/spec-kitty#6734 (follow-up from #6418, campsite cleanup): "Pack-skill `body_path` containment uses the shared containment primitive".

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pack-skill body reads stay inside the skill directory (Priority: P1)

A pack author (or an attacker who controls a pack's file tree) declares a
prompt-form pack skill whose `body_path` points outside the skill's directory —
an absolute path, a `..` traversal, or a symlink that resolves outside. Today
the load-time validator (`charter/offering/pack_skills/validation.py::_read_body`)
refuses this with a hand-rolled `resolve().is_relative_to(base)` check, but the
read-time accessor (`pack_skills/repository.py::body_text`) reads
`source.parent / skill.body_path` with **no containment at all**: a body that
passed load-time validation can be read from outside the skill directory after
a symlink swap (proven on pristine `main`: `body_text` returned the content of
a file outside the skill directory). The escaped body then reaches
`charter/activation/skill_preparation.py`, which projects it into users' agent
skill folders. As a pack consumer activating skills, I want both read paths to
refuse an escaping `body_path` through the one shared containment authority so
no pack-skill body is ever read from outside the skill's own directory.

**Why this priority**: This is the defect the issue names — one containment
authority, enforced at every read. Everything else in the mission supports it.

**Independent Test**: A prompt-form skill with an escaping `body_path`
(absolute, `..`, or a symlink swapped after load) is refused by
`PackSkillRepository.body_text` and by `validate_pack_skill` with the same
refusal class and wording, proven by tests over both entry points.

**Acceptance Scenarios**:

1. **Given** a prompt-form skill whose `body_path` is absolute, **When** it is
   validated or its body is read through the repository, **Then** the operation
   is refused with a `PackSkillViolation` naming the escape.
2. **Given** a prompt-form skill whose `body_path` contains a `..` component,
   **When** it is validated or its body is read through the repository, **Then**
   the operation is refused the same way.
3. **Given** a prompt-form skill whose `body_path` passes load-time validation
   and is then repointed (symlink swap) to a file outside the skill directory,
   **When** `body_text` is called, **Then** it refuses instead of reading the
   outside file.
4. **Given** a well-formed skill whose `body_path` is a plain relative file
   inside the skill directory (possibly nested), **When** validated or read,
   **Then** behaviour is unchanged from today.

### User Story 2 - One containment authority, correctly described (Priority: P2)

As a maintainer reading the code and docs, I want every pack-skill `body_path`
containment decision routed through
`charter.offering.drg.org_pack_config.resolve_relative_path_within_root` (the
shared primitive introduced for #6418), and any prose claiming where containment
is enforced to match reality, so the campsite rule ("one containment authority")
holds with no hand-rolled copies beside the primitive.

**Why this priority**: The campsite cleanup is the reason the issue was filed;
without it the fix would be a second hand-rolled check.

**Independent Test**: `grep` finds no `is_relative_to`-based containment in
`pack_skills/`; both read paths call the shared primitive; docstrings/docs that
describe containment name the primitive truthfully.

**Acceptance Scenarios**:

1. **Given** the pack-skills package, **When** containment is judged, **Then**
   both `_read_body` and `body_text` delegate to
   `resolve_relative_path_within_root` anchored at the skill file's directory.
2. **Given** any docstring claiming containment is judged elsewhere (including
   the primitive's own "single canonical escape-detection implementation"
   docstring and the pack validator's hand-rolled-count ordinal), **When** the
   mission lands, **Then** the claim matches the routed-through-primitive
   reality.

### Edge Cases

- A `body_path` that is an empty string: unchanged from today (the model
  requires prompt-form skills to declare a non-empty `body_path`; the
  repository accessor returns `None` for a missing/empty one — before any
  containment decision).
- A `body_path` that cannot be resolved at all (NUL byte, symlink loop): the
  primitive raises its escape error; the refusal is reported as a violation, not
  a crash.
- Windows-style absolute paths (`C:\x`, UNC): the primitive refuses them; both
  paths inherit that refusal unchanged.
- A string-level `..` that resolves back inside (e.g. `sub/../body.md`): the
  primitive refuses any `..` component, so this becomes refused at load time
  (today's hand-roll accepts it). The mission adopts the primitive's rule —
  "keep today's semantics" means the same anchor (skill directory) and trust
  stance (fail-closed), not parity with the hand-roll's looser edge.
- A contained body whose file is missing: still the separate "not found" load
  finding, never an escape refusal.
- The `enhances`/`overrides` fold: an enhancement keeps the base's file as its
  body source and an override keeps its own — both continue to be anchored at
  the source file the repository already records (semantics unchanged).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Repository body_text enforces containment | As a pack consumer, I want `PackSkillRepository.body_text` to refuse (fail-closed, `PackSkillViolation`) a `body_path` that escapes the skill directory so a pack can never have me read a body from outside it. | High | Open | [build] | no — proven by the same-fixture positive control (FR-003) |
| FR-002 | Validation routes through the shared primitive | As a maintainer, I want `validation.py::_read_body` to judge containment through `resolve_relative_path_within_root` anchored at the skill file's directory so the hand-rolled copy is gone. | High | Open | [build] | no — the routing itself is the change; refusal behaviour proven by FR-003 |
| FR-003 | Identical refusal on both paths | As a pack consumer, I want an escaping `body_path` (absolute, `..`, symlink) refused identically on the validation path and the repository read path so the two read surfaces cannot drift. | High | Open | [build] | no — paired positive control: a contained body still loads and reads on both paths |
| FR-004 | Containment-authority claims corrected | As a maintainer, I want docstrings describing containment (the primitive's "single canonical" claim, the pack validator's hand-rolled-count ordinal) to match the routed-through-primitive reality so no stale claim survives. | Medium | Open | [build] | yes — paired with the code routing that makes them true |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No new authority | No new containment implementation is introduced: both read paths call `resolve_relative_path_within_root`; `pack_skills/` contains no hand-rolled resolve-then-`relative_to` containment after the change (0 occurrences). | Maintainability | High | Open |
| NFR-002 | Semantics preserved | Every existing test in `tests/charter_offering/pack_skills/` passes unchanged; skill-directory-relative anchoring and the `PackSkillViolation` refusal surface are preserved (the primitive's stricter `..`-component rule applies, per the edge cases). | Compatibility | High | Open |
| NFR-003 | Coverage | The new branches (repository-path refusal, primitive delegation) are covered by focused tests in the same PR (diff-cover gate ≥90% on changed lines). | Quality | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Anchor | Containment is anchored at the skill file's directory (`source.parent` / `skill_file.parent`), preserving today's skill-directory-relative anchoring — never at the pack root (that is the org-DRG `body_path` contract, a different rule owned by `find_body_path_escapes`). | Technical | High | Open |
| C-002 | Refusal surface | A read-time escape raises `PackSkillViolation` (the package's existing violation type), with a message that names the escape; load-time skipping behaviour (skip-and-warn via the repository's `ValidationError` wrapper) is unchanged. | Technical | High | Open |
| C-003 | Scope | No change to the primitive's own semantics, to the org-DRG `body_path` contract, to pack layout, or to the skill renderer — only the two pack-skill read paths, their tests, the changelog, and claim corrections. | Technical | Medium | Open |

### Key Entities

- **PackSkill**: the `*.skill.yaml` aggregate; `body_path` names the prompt body
  file relative to the declaring `*.skill.yaml` file's directory.
- **resolve_relative_path_within_root**: the shared containment primitive in
  `charter.offering.drg.org_pack_config` (single containment authority, #6418);
  refuses absolute paths, `..` components, and symlink-resolved escapes.
- **PackSkillViolation**: the pack-skills violation type raised by validation
  and (after this mission) by the repository read path.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An escaping `body_path` (absolute, `..`, post-load symlink swap)
  is refused by both `validate_pack_skill` and `PackSkillRepository.body_text`
  with a `PackSkillViolation`, and a contained body still loads and reads —
  covered by tests on both entry points. — [build] · no-op passable: no
- **SC-002**: `pack_skills/` contains no hand-rolled containment; both read
  paths call `resolve_relative_path_within_root` — 0 occurrences of the removed
  pattern in the package. — [build] · no-op passable: no
- **SC-003**: Every containment-describing docstring touched by the mission
  names the primitive and both read paths truthfully. — [build] · no-op passable: yes

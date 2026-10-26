# Mission Specification: charter list shows org-required ids in force (#6417)

**Mission Branch**: `issue-6417-charter-list-org-required`
**Created**: 2026-10-26
**Status**: Draft
**Input**: Issue #6417 and the operator rulings relayed for it; discovery in
`kitty-specs/charter-list-org-required-research-01M5WZQH/research.md`.

## Intent Summary (confirmed)

The intent comes from the operator's binding rulings for #6417 (relayed by the orchestrator),
which stand in for a discovery interview; one open question was recorded as a Decision Moment
(`decisions/DM-01M5WZW16V06ARQ43WD31D7M5F.md`).

- **Primary actor**: a developer governing a project with a charter whose team (org) pack
  requires governance through `required_<plural>`.
- **Trigger**: the developer runs `spec-kitty charter list` (or `--json`) to see what governs
  the work.
- **Outcome**: for a kind the project left at its default (no allow list of its own), the listing
  names the org-required ids that are in force, with the pack that requires them.
- **Rule**: the listing claims in force exactly what the activation layer puts in force. A
  required id that no layer provides is not claimed; a required id the project excluded is still
  in force (the required floor wins over an exclusion).
- **Boundary**: an explicit allow list that leaves out a required id keeps today's
  "required (not in force: explicit allow list omits it)" marker (FR-023 of mission
  persistent-deactivation-ledger); core activation semantics do not change.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See the team's required rule in force (Priority: P1)

A team pack requires the rule `team-rule`; the project never selected directives itself. The
developer runs `charter list` and sees the directive row name `team-rule` and the team that
requires it, next to the note that every built-in directive is in force.

**Why this priority**: it is the defect (#6417) and the gating acceptance scenario
`PR-CHARTER-GOVERNANCE-002`.

**Independent Test**: run `charter list` on a project with that team pack; the output names
`team-rule`.

**Acceptance Scenarios**:

1. **Given** an org pack that provides and requires `team-rule` and no project allow list for
   directives, **When** the developer runs `charter list`, **Then** the directive row reads the
   all-built-ins note followed by `team-rule (required by team-pack)`.
2. **Given** the same project, **When** the developer runs `charter list --json`, **Then** the
   directive row carries `"activated": ["team-rule"]` and `"allow_list_present": false`, and the
   payload carries `"schema_version": "2"`.

### User Story 2 - Scripts can still tell a default from an explicit choice (Priority: P2)

A script reading `charter list --json` used `activated: null` to mean "no allow list". After this
change it reads `allow_list_present` instead, and `schema_version` tells it which contract it reads.

**Independent Test**: every row of `charter list --json` carries `allow_list_present`, `true` for
a kind with an allow list (even an empty one) and `false` otherwise.

**Acceptance Scenarios**:

1. **Given** a project with an explicit directive list, **When** `charter list --json` runs,
   **Then** that row has `"allow_list_present": true` and `activated` is the list.
2. **Given** a kind with no allow list and no in-force required id, **When** `charter list --json`
   runs, **Then** that row keeps `"activated": null` with `"allow_list_present": false`.

### User Story 3 - An explicit allow list keeps its warning (Priority: P2)

A project lists its own directives and leaves out the team's required one. The listing keeps
warning that the required id is not in force, exactly as today.

**Independent Test**: the existing FR-023 tests keep passing unchanged.

**Acceptance Scenarios**:

1. **Given** an explicit directive list that omits a required id, **When** `charter list` runs,
   **Then** the row keeps the `required (not in force: explicit allow list omits it)` marker and
   `--json` keeps the top-level `required_not_in_force`.

### Edge Cases

- A required id the project excluded (`deactivated_<plural>`): still in force, still named.
- A required id no layer provides: not named on the row (Decision Moment 01M5WZW16V06ARQ43WD31D7M5F);
  `doctor charter-packs` still reports the floor.
- `skill` (absent key means "only the org-required skills"): the row names the in-force required
  skills once and is never listed twice.
- An unreadable org required floor: the listing does not fail (lenient read, as FR-023 does).
- `mission-type`: unchanged; it carries `allow_list_present` like every row.
- A required id whose file stem differs from its declared id: named as `stem (declared_id)`.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Name in-force required ids on a default row | As a developer, I want a kind row without an allow list of its own to name the org-required ids in force, with the requiring pack, so that I see the team's governance in force. | High | Open | [build] | no — red on the base commit with the org-pack fixture |
| FR-002 | Derive in force from the activation layer | As a maintainer, I want the listed ids to be exactly the required ids the activation layer's effective set admits over what the layers provide, so that the listing and the activation layer cannot disagree. | High | Open | [build] | no — paired controls: an excluded required id is named, an unprovided one is not |
| FR-003 | JSON `activated` for a default row | As a script author, I want such a row's `activated` to be the sorted in-force required ids, and `null` when there are none. | High | Open | [build] | no — red on the base commit (`null`) |
| FR-004 | JSON `allow_list_present` on every row | As a script author, I want every row to say whether the project has its own allow list, so that I can tell a default from an explicit choice. | High | Open | [build] | no — absent key on the base commit |
| FR-005 | JSON `schema_version: "2"` | As a script author, I want the payload to carry `schema_version: "2"`, so that I know which contract I read. | Medium | Open | [build] | no — absent key on the base commit |
| FR-006 | Explicit allow list unchanged | As a developer, I want an explicit allow list that omits a required id to keep the FR-023 marker and `required_not_in_force`. | High | Open | [ratchet] | yes — paired with FR-001 on a sibling fixture that differs only by the allow list |
| FR-007 | Skill row listed once | As a developer, I want the skill row to name each in-force required skill once. | Medium | Open | [build] | no — the base commit prints the all-built-ins note with no skill named |
| FR-008 | Acceptance scenario gates | As a maintainer, I want `PR-CHARTER-GOVERNANCE-002` to gate the nightly with a fixture whose rule an org layer really provides. | High | Open | [build] | no — the scenario asserts the rule name in the listing |
| FR-009 | Contract documented | As a script author, I want the `charter list --json` reference and the changelog to describe the new keys and the changed `activated`. | Medium | Open | [build] | yes — documentation; checked by review |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No extra work without a floor | A project whose org packs require nothing reads no availability and builds no extra index for this feature (0 additional layer scans). | Performance | High | Open |
| NFR-002 | Listing stays fast | `charter list` on the fixture project completes in under 2 seconds (charter performance standard). | Performance | Medium | Open |
| NFR-003 | Lenient failure | An unreadable org required floor never makes `charter list` exit non-zero (0 new failure exits). | Reliability | High | Open |
| NFR-004 | Code quality | New code passes ruff, ruff format and mypy with 0 findings; no function exceeds complexity 15. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Seam direction | `specify_cli` reaches the activation layer only through `charter.activation.api`; the in-force derivation lives in `charter.activation`. | Technical | High | Open |
| C-002 | No new semantics | Core activation semantics are unchanged (ruling `required_always_active_divergence`). | Technical | High | Open |
| C-003 | Red first | The acceptance and CLI-level tests are committed red before the fix. | Process | High | Open |
| C-004 | Terminology | Mission terminology; no `feature` aliases in new surfaces. | Business | Medium | Open |

### Key Entities

- **Required id in force**: an org-required id of one kind, the packs that require it, and the
  fact that the activation layer admits it while the kind has no allow list.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the scenario fixture, `charter list` names the team's required rule (0 → 1 rule named) — [build] · no-op passable: no
- **SC-002**: 100% of `charter list --json` rows carry `allow_list_present` — [build] · no-op passable: no
- **SC-003**: Every existing FR-023 test passes unchanged (0 regressions) — [ratchet] · no-op passable: yes
- **SC-004**: `charter list` and `doctor charter-packs` agree on the fixture's in-force required rule — [build] · no-op passable: no

## Assumptions

- The Cucumber-JVM suite needs Java 25, not available in this container; the nightly runs it, and
  a CLI-level Python test reproduces the same fixture here.
- No `src/` code parses `charter list --json` (research consumer list).

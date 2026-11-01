# Mission Specification: Scoped agent-profile sentinel lookup for the board

**Mission Branch**: `issue-6917-sentinel-scoped-profile-read`
**Created**: 2026-11-01
**Status**: Draft
**Input**: GitHub issue #6917 — `spec-kitty agent tasks status` builds the whole charter service
and profile catalog to render one 👤 sentinel boolean per claimed work package.

**Operator guidance recorded**: small, single-purpose fix; it must actually solve the issue
(the board must stop materialising the whole catalog), must not weaken the charter sole-door
boundary or its ratchet, must not turn the structural `sentinel` read into an activation-gated
read, and must stay a tight mission (no full heavy suites locally).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read-only board renders the 👤 marker without parsing the whole catalog (Priority: P1)

A maintainer runs `spec-kitty agent tasks status --mission <slug>` on a project whose pack ships
26 agent profiles and whose board names one or two claimed profiles. The 👤 marker still renders
for a work package assigned to `human-in-charge`, but the command parses only the profile
documents its rows name instead of all 26 (plus the lineage graph it never consults).

**Why this priority**: this is the issue itself: a read-only render pays a governance catalogue
build for one structural boolean, measured at ~0.9 s of a ~4 s command.

**Independent Test**: run the board render with a two-profile mission and count profile YAML
documents parsed through the production entry point; assert the count is bounded by the named ids
and that the marker text is unchanged. Fails on unmodified `main` (26 parses), passes after.

**Acceptance Scenarios**:

1. **Given** a mission with a claimed WP whose `agent_profile` is `human-in-charge`, **When**
   `agent tasks status` renders the board, **Then** the row shows `👤 ` and the number of
   agent-profile YAML documents parsed is at most the number of distinct profile ids the board
   names.
2. **Given** the same mission, **When** no rendered row carries an `agent_profile`, **Then** no
   profile document is parsed at all.

---

### User Story 2 - The marker follows the layer that actually supplies the profile (Priority: P2)

A project (or an org pack) overlays `human-in-charge`, or declares its own sentinel profile. The
marker follows the same built-in → org → project layering, field merge and language-scope rules
the full profile repository applies, so a project overlay that flips `sentinel` changes the
marker and one that merely extends the profile does not lose it.

**Why this priority**: the scoped read must not become a second, weaker interpretation of the
profile schema; a marker that disagrees with the catalogue is worse than a slow one.

**Independent Test**: build a project overlay for `human-in-charge` under
`.kittify/charter-packs/agent_profiles/` (and an org-pack fixture) and assert the scoped lookup
agrees with the full `AgentProfileRepository` for every id, including one whose overlay sets
`sentinel: false`.

**Acceptance Scenarios**:

1. **Given** a project overlay of `human-in-charge` that only extends the description, **When**
   the board renders, **Then** the 👤 marker is still present.
2. **Given** a project overlay declaring `sentinel: false` for the id, **When** the board
   renders, **Then** no 👤 marker appears — the higher layer wins, exactly as in the repository.
3. **Given** every id shipped in `packs/built-in/agent_profiles/`, **When** the scoped lookup and
   the full repository are compared, **Then** the two agree on `sentinel` for every id.

---

### User Story 3 - Structural sentinel stays structural (Priority: P3)

An operator narrows or denies `activated_agent_profiles` (activation), and the 👤 marker must not
disappear: `sentinel` is a structural profile property, like provenance.

**Why this priority**: already-pinned behavior from `charter-sole-door-bypass-closure-01KZ3WAA`;
the scoped path must not regress it while dropping the activation-service build.

**Independent Test**: extend the existing deny/narrowing marker tests to the scoped path; they
must stay green.

**Acceptance Scenarios**:

1. **Given** a project whose `.kittify/config.yaml` narrows or denies `human-in-charge`, **When**
   the board renders, **Then** the 👤 marker is still present.

---

### Edge Cases

- A row names a profile id no layer ships: no marker, no exception, and the rest of the board
  renders normally.
- A row's `agent_profile` is `None` or `""`: no marker (unchanged historical guard).
- The board is empty or nothing is claimed: the profile read is skipped entirely.
- `.kittify/config.yaml` is malformed: the command still fails closed with a structured error
  rather than silently rendering a markerless board.
- A pack holds a profile file whose stem differs from its `profile-id`: the full repository
  remains the authority for that case; the scoped read is documented to resolve ids by the
  repository's own `<id>.agent.yaml` file convention.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Scoped sentinel accessor on the sole door | As a maintainer, I want one charter-layer accessor that answers `sentinel` for a named id set so that callers never rebuild the catalogue for one boolean. | High | Open | [build] | no |
| FR-002 | Board reads only the profiles it names | As a maintainer, I want `agent tasks status` to parse at most the profiles its rows name so that the read-only render stays cheap as the catalogue grows. | High | Open | [build] | no |
| FR-003 | Loader parity for the scoped read | As a maintainer, I want the scoped read to reuse the repository's layer order, field merge, schema/skip and language-scope rules so that the marker never disagrees with the catalogue. | High | Open | [build] | no |
| FR-004 | Marker survives narrowing and deny | As an operator, I want the 👤 marker to keep rendering when `activated_agent_profiles` narrows or denies the id, because `sentinel` is structural. | Medium | Open | [ratchet] | no |
| FR-005 | No second profile reader in `specify_cli` | As a maintainer, I want the CLI to reach profiles only through the charter sole door so that the FR-001 boundary ratchet stays green. | Medium | Open | [ratchet] | no |
| FR-006 | Absent or falsy id degrades quietly | As an operator, I want an unknown or empty `agent_profile` to yield no marker and no error so that one bad row cannot break the board. | Low | Open | [ratchet] | no |
| FR-007 | Full-profile readers unchanged | As a maintainer, I want the default `AgentProfileRepository` load (and every existing caller) unchanged so that the scoping is opt-in. | Medium | Open | [ratchet] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded profile parses | A board render on this repository's shipped pack parses ≤ the number of distinct `agent_profile` ids its rows carry (today 26 shipped documents; target ≤ 3 for a two-profile board), measured by a census test on the production entry point. | Performance | High | Open |
| NFR-002 | Wall-clock improvement | The charter-side cost of the marker lookup on this repository drops from the measured ~2.1 s (service build + full catalog + lineage graph) to ≤ 0.5 s warm, measured in one process against the unmodified baseline. | Performance | Medium | Open |
| NFR-003 | Fail-closed preserved | A malformed `.kittify/config.yaml` still surfaces a structured error from `agent tasks status`; the scoped path must not degrade it to a markerless render. | Reliability | High | Open |
| NFR-004 | Sole-door gates stay green | `tests/architectural/test_charter_sole_door_agent_profile_repository.py`, `…_offering_service.py`, `…_inner_reacharound.py` and `…_resolver_imports.py` pass with zero new exclusions. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Construction stays in the exempt layer | The scoped load lives inside `charter/offering/` (the repository's owner); `specify_cli` reaches it only through the sole-door accessor and the existing builder module. No new construction site outside those files. | Technical | High | Open |
| C-002 | Structural, not activation-gated | The accessor must not consult `PackContext` activation state: `sentinel` is structural (charter-sole-door-bypass-closure-01KZ3WAA rationale for `agent_profile_repository`). | Technical | High | Open |
| C-003 | Opt-in scope only | The default load path of `AgentProfileRepository` and every existing caller keep today's behavior byte-for-byte; the scope is a new, keyword-only parameter and a new accessor. | Technical | High | Open |
| C-004 | No full heavy suites | Validation runs the targeted fast suites and the architectural gates only, per `NO_FULL_HEAVY_SUITES_IN_MISSION`. | Business | Medium | Open |

### Key Entities

- **Agent profile sentinel**: the structural `sentinel` boolean on an agent profile — declares that
  a work package is human-in-charge and gets a 👤 marker on the board.
- **Scoped sentinel read**: a per-id lookup over the same three pack layers, parsing only the
  documents that can supply the requested ids.
- **Board marker**: the rendered `👤 ` prefix on a work-package row.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A board render for a two-profile mission parses at most 3 agent-profile YAML documents where `main` parses 26, proven by a census test that fails on unmodified `src`. — [build] · no-op passable: no
- **SC-002**: The 👤 marker is byte-identical for every board row that shows it on `main`, including org/project-overlay and activation-narrowed fixtures. — [ratchet] · no-op passable: no
- **SC-003**: The charter sole-door gates pass with zero new exclusions and zero unresolved constructions. — [ratchet] · no-op passable: no
- **SC-004**: The scoped lookup agrees with the full repository's `sentinel` for every id in the shipped built-in catalogue. — [build] · no-op passable: no

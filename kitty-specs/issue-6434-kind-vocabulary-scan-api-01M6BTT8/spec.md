# Mission Specification: Promote kind_vocabulary scanning helpers to a module-internal API

**Mission Branch**: `issue-6434-kind-vocabulary-scan-api`
**Created**: 2026-11-01
**Status**: Draft
**Input**: GitHub issue spec-kitty/spec-kitty#6434 — "Promote kind_vocabulary's artifact
scanning helpers to a small internal API used by IdentityIndex and tests", opened as a
pre-PR review finding on the #6404–#6408 Mission, with scope guidance: behaviour-preserving
promotion only (no resolution-precedence, discovery or gate semantics change).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A charter maintainer reads the scanning API instead of guessing (Priority: P1)

A maintainer working on charter activation needs to know how an artifact kind's files are
discovered across the project, org and built-in layers. Today the only answer is five
underscore-named helpers inside `kind_vocabulary`, reachable only by reading the module.
After this mission, the module exposes a small, documented scanning API (roots for a kind,
the files under one root, the artifact paths for a kind, an artifact's id field and its
config stem, and the canonical id reader), and `IdentityIndex` is written against it.

**Why this priority**: it is the substance of the issue: production code (`IdentityIndex`)
currently consumes private names, so the seam cannot be documented, tested or refactored
without touching call sites that were never meant to be part of an interface.

**Independent Test**: import the public names from `charter.activation.kind_vocabulary`,
call them on a synthetic layer set, and confirm `IdentityIndex` resolves the same
identities it resolved before the change.

**Acceptance Scenarios**:

1. **Given** a kind and a project/org/built-in layer set, **When** a caller asks
   `scan_roots` for that kind, **Then** it receives the ordered `(directory, recursive)`
   pairs, exactly as `IdentityIndex` scans them today.
2. **Given** an artifact file that declares `id:` (or `profile-id:` for an agent profile),
   **When** a caller reads it through the public id reader, **Then** it receives the
   declared id, falling back to the file stem when the id is missing or unparseable.
3. **Given** `IdentityIndex` built over the same roots, **When** any token is resolved,
   **Then** the outcome (declared id, stem, layer, collision behaviour) is identical to the
   pre-change outcome.

---

### User Story 2 - Tests probe a public seam instead of patching underscore names (Priority: P1)

A test author counting scans or seeding a graph currently patches `kind_vocabulary.
_scan_dir_matches`, `kind_vocabulary._parse_id` or `IdentityIndex._scan`, and imports
`_iter_artifact_paths`, `_read_id`, `_id_field_for`, `_config_stem` and `_built_in_scan_dir`.
After this mission those tests wrap or call the public seam, so a rename inside the module
no longer silently breaks a scan-count assertion, and the count assertions keep their
meaning.

**Why this priority**: the issue names test coupling as half the defect; a promotion that
leaves the tests on underscore names has not removed the coupling.

**Independent Test**: run the scan-count and memoization tests, then rename the public
seam's internals — the tests keep passing and still fail if the production path rescans.

**Acceptance Scenarios**:

1. **Given** the scan-count tests (`test_identity_index.py`,
   `test_directive_resolution_memoization.py`, `test_context_identity_reuse.py`,
   `test_resolver_directive_activation_keying.py`), **When** they are run, **Then** they
   wrap public seams only, and they still fail if a per-kind or per-layer scan doubles.
2. **Given** a repository-wide AST scan of `src/` and `tests/`, **When** it looks for the
   retired underscore names on the scanning seams, **Then** it finds none.

---

### User Story 3 - The other private seams named by the same review finding are promoted too (Priority: P2)

The same pre-PR review found tests importing `_load_action_governance_bundle` from
`charter.activation.action_governance_bundle` (a name already listed in that module's
`__all__`) and `_direct_root_urns` from `charter.activation.compiler`. After this mission
both are public names, so the graph-seeding tests stop importing private surface.

**Why this priority**: it closes the issue's Context list rather than half of it, and both
are pure renames with no behavioural change, so they carry little risk.

**Independent Test**: import both names publicly, run the graph-seeding tests, and confirm
the resolved bundles and direct-root URN sets are unchanged.

**Acceptance Scenarios**:

1. **Given** an org pack and a project activation state, **When**
   `load_action_governance_bundle` is called with the same arguments the private name took,
   **Then** the returned bundle is identical.
2. **Given** the same config-activated roots, **When** `direct_root_urns` is called,
   **Then** the returned URN set is identical, including the reach-only tactic/styleguide
   exclusions.

### Edge Cases

- A built-in content directory that is absent, or whose pack root cannot be resolved: the
  public `scan_roots` keeps the current fail-soft contract (`built_in_scan_dir` returns
  `None`, no raise), and the mission-wide step-contract special case keeps its flat,
  non-recursive root.
- A kind with no `glob_pattern` (for example `anti_pattern`): `iter_artifact_paths` still
  returns no paths rather than scanning.
- A YAML artifact that is unparseable, has a BOM/CRLF, or omits its id: the public id
  reader keeps the current fallback to the file stem and never raises for these inputs.
- A downstream/organisation consumer that imported one of the retired underscore names: the
  names are removed, not aliased. This is an internal `charter`-layer module; the mission
  records the removal in the changelog so searchers find the new name.
- A dataclass- or `ResolutionPass`-threaded caller that already shares a pass: the public
  reader keeps the pass-scoped memo, so scan counts do not regress.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Public scanning API | As a charter maintainer, I want `scan_roots`, `scan_dir_matches`, `iter_artifact_paths` and `built_in_scan_dir` public and documented so that discovery is an interface, not a private detail. | High | Open | [build] | no — the names do not exist before the change |
| FR-002 | Public id/identity helpers | As a charter maintainer, I want `artifact_id_field`, `read_artifact_id`, `parse_artifact_id` and `artifact_config_stem` public so that reading an artifact's identity needs no underscore name. | High | Open | [build] | no — same reason |
| FR-003 | IdentityIndex consumes the public API | As a maintainer, I want `IdentityIndex` written against the public scanning API so that production code carries no coupling to private names. | High | Open | [build] | no — `IdentityIndex` calls private names today |
| FR-004 | IdentityIndex scan seam is public | As a test author, I want `IdentityIndex` to expose its per-kind scan publicly so that scan-count probes wrap a documented seam. | Medium | Open | [build] | no — `_scan` is private today |
| FR-005 | Governance seams renamed | As a test author, I want `load_action_governance_bundle` and `direct_root_urns` public so that graph-seeding tests import supported surface. | Medium | Open | [build] | no — both carry a leading underscore today |
| FR-006 | No retired name remains | As a maintainer, I want an architectural ratchet that fails when `src/` or `tests/` reaches for any retired underscore name on these seams, so that the coupling cannot return. | High | Open | [ratchet] | no — the ratchet is red before the change and green after |
| FR-007 | Behaviour preserved | As an operator, I want every identity/graph resolution outcome unchanged so that the refactor cannot alter governance delivery. | High | Open | [ratchet] | no — pinned by the existing resolution suites, which fail on any drift |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Scan-count parity | Per-kind `IdentityIndex` scan count and per-layer resolver scan count stay at most one per kind/layer per pass; the existing scan-count tests stay green with unchanged expected counts. | Performance | High | Open |
| NFR-002 | Import boundary | The public scanning API lives in `charter.activation.kind_vocabulary` only; no new `specify_cli` import appears in the `charter` layer and no second discovery authority is introduced. | Architecture | High | Open |
| NFR-003 | Ratchet cost | The new architectural test completes inside the fast tier (no pack fetch, no full-repo YAML parse; AST/text scanning of `src/` and `tests/` only). | Performance | Medium | Open |
| NFR-004 | API surface discipline | Every promoted name is exported in `kind_vocabulary.__all__` (and the two renamed governance seams in their modules' `__all__`/import lists), with a one-line docstring a reader can act on. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Behaviour-preserving refactor | No change to layer precedence, recursion, the reserved `built-in/` subtree rule, directive round-trip rules, or gate semantics; the diff is a promotion, not a redesign. | Technical | High | Open |
| C-002 | Remove, do not alias | The retired underscore names are deleted, not kept as deprecated aliases; every call site in `src/` and `tests/` moves to the public name in the same PR. | Technical | High | Open |
| C-003 | Single canonical authority | `kind_vocabulary` remains the one discovery authority for artifact scanning; the promoted names must not become a second source that a consumer can diverge from. | Technical | High | Open |
| C-004 | Internal module, documented change | These are internal `charter`-layer seams, not a consumer-facing contract: the changelog entry says so plainly and no public CLI/doc contract is claimed. | Business | Medium | Open |

### Key Entities

- **Scan root**: a `(directory, recursive)` pair for one artifact kind in one layer; ordered
  project, then org packs from last-declared to first, then built-in.
- **Artifact identity**: the declared `id:` (or kind-specific id field) of an artifact file,
  with the file stem as fallback; its config stem is the filename with all suffixes removed.
- **Identity entry**: one indexed artifact — kind, stem, declared id, layer and path — the
  row `IdentityIndex` builds its lookups from.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero references to the retired underscore names (`_scan_roots`,
  `_scan_dir_matches`, `_read_id`, `_parse_id`, `_id_field_for`, `_config_stem`,
  `_iter_artifact_paths`, `_built_in_scan_dir`, `IdentityIndex._scan`,
  `_load_action_governance_bundle`, `compiler._direct_root_urns`) remain in `src/` or
  `tests/`, proven by an AST ratchet that fails on any hit. — [ratchet] · no-op passable: no
- **SC-002**: The four scan-count/memoization test modules and the two identity-index test
  modules pass with unchanged expected scan counts. — [ratchet] · no-op passable: no
- **SC-003**: The charter activation, identity and governance-bundle test suites pass
  unchanged, proving resolution outcomes did not move. — [ratchet] · no-op passable: no
- **SC-004**: Every promoted name is reachable from the module's public surface (`__all__`)
  and carries a docstring, checked mechanically. — [build] · no-op passable: no

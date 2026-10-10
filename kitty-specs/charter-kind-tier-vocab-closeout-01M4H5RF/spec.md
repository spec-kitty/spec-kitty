# Mission Specification: Charter kind/tier vocabulary cutover closeout

**Mission Branch**: `feat/charter-kind-tier-vocab-closeout`
**Created**: 2026-10-09
**Status**: Draft
**Input**: Finish the residual single-authority kind/tier vocabulary work and inert-residue cleanup deferred by the merged doctrine→charter cutover (#5962 / #5827 / #5979). Closes #5823, #5824, #5825, #5961, #5836, #5322.

## User Scenarios & Testing *(mandatory)*

The "users" of this mission are the Spec Kitty maintainers and the agent harnesses that edit this codebase, plus the operator who reads `doctor`/charter CLI output. The value is drift-proofing: the artifact-kind and pack-tier vocabularies each get exactly one owning source, every mirror derives from it, and a structural gate makes a future hand-copied mirror impossible by construction rather than caught after the fact.

### User Story 1 - Kind/tier vocabulary cannot drift (Priority: P1)

A maintainer (or a subagent) edits a charter/offering surface and is tempted to hand-write a set/map/tuple that restates the artifact-kind universe or the pack-tier token. The single-authority gates must refuse any such literal and point at the one authority to derive from — including the five mirror shapes the kind gate misses today and the dual pack-tier spelling that has no single home.

**Why this priority**: This is the core defect class the cutover PRs explicitly deferred (#5823, #5825/#5961) and the gate blind spot that lets a mirror cross a facade unseen (#5836). Closing it by construction is the mission's reason to exist.

**Independent Test**: Extend each gate with a failing self-mutation (planted-mirror) case first, confirm it goes RED, then make it GREEN by migrating every live site to derive from the authority. The gates close with empty allowlists.

**Acceptance Scenarios**:

1. **Given** a planted universe set padded with one non-kind string, a glob/suffix-valued kind map, an operator-token→singular map, or an `ArtifactKind`→`NodeKind` identity map, **When** the kind-vocabulary gate scans `src/`, **Then** each is flagged with a reason and the gate names the authority to derive from.
2. **Given** a planted tuple/frozenset re-exported through a charter facade without an identity-table row, **When** the facade re-export gate runs, **Then** it is reported (not silently skipped for lacking `__module__`).
3. **Given** a planted pack-tier token literal under `src/`, **When** the new tier-token gate scans, **Then** it is flagged and the gate's allowlist is empty.

### User Story 2 - Diagnostic surfaces cover every layered kind (Priority: P2)

An operator runs `doctor charter-packs` or the org-layer lint on a project whose org pack ships glossary packs, skills, or assets. Those three kinds use the same three-source layered repository as the original eight, so collisions and overrides in them must be reported and counted — today only the eight "core" kinds are covered.

**Why this priority**: #5824 — a real reliability/usability gap (silent blind spots in diagnostics), and the enabler for retiring the transitional `ArtifactKind.core`.

**Independent Test**: Add tests proving a glossary_pack/skill/asset collision and an org override of each are reported, then repoint the surfaces onto a capability predicate; delete `core` once no surface reads it.

**Acceptance Scenarios**:

1. **Given** an org pack with a colliding glossary_pack/skill/asset layer, **When** the collision scan runs, **Then** the collision is reported.
2. **Given** an org override of a built-in glossary_pack/skill/asset, **When** the org-layer lint runs, **Then** the override is flagged.
3. **Given** the codebase after the mission, **When** anything references `ArtifactKind.core`/`CORE_KIND_PLURALS`, **Then** there are zero such references and the symbols are deleted.

### User Story 3 - Dead cutover residue is gone (Priority: P3)

A reader browsing the agent command copies no longer finds files that point at the deleted `src/doctrine/skills/...` path.

**Why this priority**: #5322 — low-risk campsite cleanup; most of the residue the issue described is already gone, leaving only the 13 dead generated copies.

**Independent Test**: The 13 `spec-kitty-standalone.md` copies are deleted; `graph.yml` is deliberately left untouched (existing migration decision + guard test); no `src/` reader is affected.

**Acceptance Scenarios**:

1. **Given** the repo after the mission, **When** grepping tracked files for `src/doctrine/skills/`, **Then** the 13 dead standalone copies no longer appear.
2. **Given** `.kittify/charter/graph.yml`, **When** the mission completes, **Then** it is unchanged and `test_retired_activation.py` still passes.

### Edge Cases

- A legitimate curated construct (`DIRECT_WRITE_KINDS`, the intentionally-total `PROJECT_KIND_DIRS`, the str→`NodeKind` `_KIND_BY_LEGACY_FIELD`, `typing.Literal[...]` kind aliases, callable/`NodeKind`-valued dispatch tables) must NOT be false-flagged by any new rule — the new rules are scoped to exclude them, proven by a "leaves a legitimate construct alone" test.
- A pack-tier `"built-in"` spelling that names the on-disk `packs/built-in/` directory or `kernel._BUILT_IN_DIR_NAME` is NOT a tier token and must stay unchanged; only tier-token/provenance/rank spellings unify.
- The `DEFAULT_KIND_GATE` snapshot value (a frozen release artifact that merely equals the core plurals today) must get its own literal, never the new topology predicate.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Facade gate sees non-class re-exports (#5836) | As a maintainer, I want the facade re-export gate to catch re-exported tuples/frozensets by object identity so a drifted non-class constant cannot cross a facade unchecked. | High | Open | [ratchet] | no — paired with a planted non-class re-export self-test that must be reported |
| FR-002 | Kind gate rule R1′ padded universe sets (#5823) | As a maintainer, I want a universe set padded with one non-kind string flagged so `RECOGNISED_ARTIFACT_DIRS`/`_VALID_SELECTOR_KINDS`-shaped mirrors cannot drift. | High | Open | [ratchet] | no — planted padded-set self-mutation is the positive control |
| FR-003 | Kind gate rule R4 glob/suffix-valued maps (#5823) | As a maintainer, I want plural→glob kind maps checked against `ArtifactKind.glob_pattern` so a per-kind glob map cannot drift. | High | Open | [ratchet] | no — planted glob-map self-mutation is the positive control |
| FR-004 | Kind gate rule R5 operator-token maps (#5823) | As a maintainer, I want operator-token→singular maps flagged so a restatement of `from_operator_token` cannot drift. | High | Open | [ratchet] | no — planted operator-token-map self-mutation is the positive control |
| FR-005 | Kind gate rule R6 ArtifactKind→NodeKind identity maps (#5823) | As a maintainer, I want `ArtifactKind`-keyed `NodeKind`-valued identity maps flagged so an enum-pair restatement cannot drift. | High | Open | [ratchet] | no — planted enum-identity-map self-mutation is the positive control |
| FR-006 | Synthesizable 3-kind subset has one home (#5823) | As a maintainer, I want `{directive,tactic,styleguide}` restatements to derive from the public `SYNTHESIZABLE_KINDS` so the subset has one owner. | Medium | Open | [build] | no — a migrated site deriving from the constant is asserted |
| FR-007 | All live kind-mirror sites migrated; gate empty-allowlist (#5823) | As a maintainer, I want every current kind-vocabulary mirror site migrated to derive from the authority and the gate docstring follow-up note removed, with the allowlist empty. | High | Open | [build] | no — gate self-test over the full `src/` scan is the control |
| FR-008 | `has_layered_repository` predicate (#5824) | As a maintainer, I want a capability predicate on `ArtifactKind` (11 kinds = all but TEMPLATE/ANTI_PATTERN) with its own backing frozenset and a "coincides with org_requirable today — do not merge" docstring. | High | Open | [build] | no — focused unit tests pin the exact 11-kind set |
| FR-009 | Diagnostic surfaces cover layered kinds (#5824) | As an operator, I want the `doctor charter-packs` collision scan, org-pack dir count, org-layer override lint, and the API-source 404 fallback to cover glossary_pack/skill/asset via the predicate. | High | Open | [build] | no — tests prove a glossary_pack/skill/asset collision and override are reported |
| FR-010 | Isolate the DEFAULT_KIND_GATE snapshot (#5824) | As a maintainer, I want the `DEFAULT_KIND_GATE` cutover-snapshot value given its own literal rather than the topology predicate so a frozen release artifact is not coupled to repository topology. | High | Open | [ratchet] | no — the snapshot equality test pins the exact set |
| FR-011 | Retire `core` (#5824) | As a maintainer, I want `ArtifactKind.core`, `_CORE_KINDS`, `CORE_KIND_PLURALS` and the `charter.drg` facade re-export deleted once no surface reads them. | Medium | Open | [ratchet] | no — a zero-reference check plus the facade-table/`__all__` removal are the controls |
| FR-012 | Single kernel pack-tier authority (#5825/#5961) | As a maintainer, I want one kernel-owned authority for the pack-tier token (one spelling, `"built-in"`), importable by kernel, charter and specify_cli. | High | Open | [build] | no — the authority's single-spelling invariant is asserted |
| FR-013 | Migrate tier-token sites to the authority (#5825/#5961) | As a maintainer, I want every pack-tier token/rank/provenance site to derive from the authority with one spelling, leaving the on-disk `packs/built-in/` directory and `_BUILT_IN_DIR_NAME` unchanged. | High | Open | [build] | no — a site deriving from the authority is asserted and the dual-spelling gate is the control |
| FR-014 | Net-new tier-token single-authority gate (#5825/#5961) | As a maintainer, I want a new architectural gate, empty allowlist, that flags a hand-authored pack-tier token literal under `src/`. | High | Open | [ratchet] | no — planted tier-token literal self-mutation is the positive control |
| FR-015 | Delete dead standalone copies; leave graph.yml (#5322) | As a maintainer, I want the 13 dead `spec-kitty-standalone.md` generated copies deleted and `.kittify/charter/graph.yml` left untouched per the existing migration decision + guard test. | Low | Open | [ratchet] | no — a grep-for-`src/doctrine/skills/` check over tracked files plus the unchanged `test_retired_activation.py` are the controls |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Empty-allowlist gates | Every architectural gate this mission adds or extends closes with an empty allowlist / no new frozen-baseline entry; a transient allowlist entry is a mission failure. | Reliability | High | Open |
| NFR-002 | Clean lint/types | New and changed code passes `ruff check`, `ruff format --check` and `mypy --strict` with zero issues and zero new suppressions (no blanket `# noqa`/`# type: ignore`). | Maintainability | High | Open |
| NFR-003 | No behavioural/path breakage | The on-disk `packs/built-in/` directory name, `kernel._BUILT_IN_DIR_NAME`, and any persisted/compared provenance value are unchanged; tier-token unification is verified against persisted consumers before each edit. | Reliability | High | Open |
| NFR-004 | Terminology canon | No `doctrine`-tier vocabulary is reintroduced; `test_no_legacy_terminology.py` passes; the product object stays a Mission, never a feature. | Compliance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Single canonical authority | Every new kind/tier fact derives from `ArtifactKind` (or the new kernel tier authority); no hand-copied mirror is introduced, including the frozensets this mission adds. | Technical | High | Open |
| C-002 | Smallest viable diff + hard scope fence | Honour DIRECTIVE_024/025; do NOT touch the out-of-scope missions (#5323, #4400, #5959, #5960, #5826). Any pull toward them is a scope-widening decision to escalate. | Technical | High | Open |
| C-003 | Red-first gate discipline | Each extended/new gate rule adds its failing self-mutation case first (proven RED), then GREEN; never skip/disable/xfail/quarantine a test or retry-to-green a flake. | Technical | High | Open |
| C-004 | Leave graph.yml alone | `.kittify/charter/graph.yml` is not modified; the deliberate existing migration decision and its guard test (`test_retired_activation.py`) stand. | Technical | Medium | Open |

### Key Entities

- **ArtifactKind authority** (`src/charter/offering/artifact_kinds.py`): the single owner of kind facts (plural, glob, activatable, org_requirable, selection_overlayable, effective_when_absent, and the new `has_layered_repository`).
- **Pack-tier authority** (new kernel module): the single owner of the pack-tier token, its ordered tuple, rank, and provenance spelling.
- **Architectural gates**: `test_charter_kind_vocabulary_single_authority.py`, `test_charter_facades_reexport_offering.py`, and the net-new tier-token gate.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The kind-vocabulary gate flags all five previously-missed mirror shapes via planted self-tests and its live allowlist is empty (`test_allowlist_is_empty` passes). — [ratchet] · no-op passable: no
- **SC-002**: `doctor charter-packs` collision scan + org-pack dir count + org-layer override lint report glossary_pack, skill and asset (new tests prove each), and `ArtifactKind.core`/`CORE_KIND_PLURALS` have zero references and are deleted. — [build] · no-op passable: no
- **SC-003**: The pack-tier token resolves to one spelling (`"built-in"`) sourced from one kernel authority, and a net-new tier-token gate passes with an empty allowlist. — [build] · no-op passable: no
- **SC-004**: The facade re-export gate reports a planted non-class re-export, and all six issues (#5823, #5824, #5825, #5961, #5836, #5322) are closed by the single hand-off PR. — [ratchet] · no-op passable: no

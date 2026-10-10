---
description: "Work package task list for charter-kind-tier-vocab-closeout"
---

# Work Packages: Charter kind/tier vocabulary cutover closeout

**Inputs**: Design documents from `/kitty-specs/charter-kind-tier-vocab-closeout-01M4H5RF/`
**Prerequisites**: plan.md (required), spec.md (user stories + FR/NFR/C), the four grounding-scout reports (recorded in Decision Moments)

**Tests**: Required — this is gate/authority work; each gate rule lands a red-first self-mutation test. Targeted blast radius only (no full `tests/architectural/` / `test-full` sweep).

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Topology is `single_branch`: WPs run sequentially in the repository root checkout.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/`, `tests/`.

---

## Work Package WP01: Facade re-export gate sees non-class values (Priority: P1)

**Goal**: The facade identity gate catches re-exported tuples/frozensets (no `__module__`) by object-identity scan, so a drifted kind-vocabulary constant cannot cross a facade unchecked. Enabler for WP02.
**Independent Test**: A planted non-class constant re-exported through a fake facade without a `_FACADE_TABLE` row is reported; the existing wrapper self-test and all live facade tests stay green.
**Prompt**: `/tasks/WP01-facade-nonclass-reexport-gate.md`
**Requirement Refs**: FR-001

### Included Subtasks

T001 Add a failing self-test: a planted non-class (tuple/frozenset) `charter.offering`-origin re-export advertised in `__all__` but absent from the table is reported by `_untabled_reexports` (RED first).
T002 Make `_untabled_reexports` resolve origin for a value lacking `__module__` by identity-scanning the `_IDENTITY_REQUIRED_ORIGINS` modules (and submodules); keep the `__module__` class path and the existing wrapper self-test green.

### Dependencies

- None (enabler; land first).

### Risks & Mitigations

- Identity scan must not import-cycle or misattribute a shared stdlib value → scope the scan to `_IDENTITY_REQUIRED_ORIGINS` modules already imported; match by `is`.

---

## Work Package WP02: Kind-vocabulary gate rules R1′/R4/R5/R6 + synthesizable subset (Priority: P1)

**Goal**: Teach the kind-vocabulary gate the five mirror shapes it misses and migrate every live site to derive from `ArtifactKind`/`SYNTHESIZABLE_KINDS`, keeping the allowlist empty and the docstring follow-up note removed.
**Independent Test**: Planted self-mutation cases for each new rule are flagged; a "leaves legitimate constructs alone" test passes for the six known-good shapes; the full `src/` scan is green with an empty allowlist.
**Prompt**: `/tasks/WP02-kind-vocabulary-gate-rules.md`
**Requirement Refs**: FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, C-001, C-003, NFR-001

### Included Subtasks

T010 Add R1′ self-mutation test (universe set + one non-kind string) — RED.
T011 Add R4 self-mutation test (plural→glob map checked vs `glob_pattern`) — RED.
T012 Add R5 self-mutation test (operator-token→singular map) — RED.
T013 Add R6 self-mutation test (`ArtifactKind`-keyed `NodeKind`-valued identity map) — RED.
T014 Add "leaves legitimate constructs alone" test (DIRECT_WRITE_KINDS, total PROJECT_KIND_DIRS, str→NodeKind `_KIND_BY_LEGACY_FIELD`, `Literal[...]` aliases, callable/NodeKind dispatch tables) — must stay unflagged.
T015 Implement R1′/R4/R5/R6 classifier rules, tightly scoped; GREEN the self-tests.
T016 [P] Migrate `pack_manifest.py` `RECOGNISED_ARTIFACT_DIRS` and `fetch_stanza.py` `_VALID_SELECTOR_KINDS` to derive (R1′).
T017 [P] Migrate `pack_assembler.py` `_ARTIFACT_DIRS_AND_GLOBS` to derive from `glob_pattern` (R4).
T018 [P] Migrate `consistency_check.py` `_CLI_KIND_TO_DRG_SINGULAR` to derive from `operator_token`/`from_operator_token` (R5).
T019 [P] Migrate `executor.py` `_ARTIFACT_TO_NODE_KIND` and `synthesizer/project_drg.py` `_KIND_TO_NODE_KIND` to derive (R6).
T020 Point `{directive,tactic,styleguide}` restatements (`bundle.py`, `write_pipeline.py`, `_synthesis.py`) at `SYNTHESIZABLE_KINDS`; remove the gate docstring "tracked as a follow-up" note.

### Dependencies

- Depends on WP01 (facade enforcement must be real before trusting facade re-exports as the one authority object).

### Risks & Mitigations

- False positives on legitimate constructs → T014 pins them before T015; rules scoped to exact shapes.
- `RECOGNISED_ARTIFACT_DIRS` stays a `charter.packs` facade re-export → keep its table row; the object stays identity-held.

---

## Work Package WP03: Retire ArtifactKind.core via has_layered_repository (Priority: P1)

**Goal**: Replace the transitional `core` with a capability predicate (11 layered kinds), widen the four diagnostic surfaces to glossary_pack/skill/asset, isolate the `DEFAULT_KIND_GATE` snapshot, then delete `core`/`_CORE_KINDS`/`CORE_KIND_PLURALS` + the `charter.drg` facade re-export.
**Independent Test**: Unit tests pin the 11-kind `has_layered_repository` set; tests prove a glossary_pack/skill/asset collision and an org override are reported; a repo-wide check finds zero `core`/`CORE_KIND_PLURALS` references.
**Prompt**: `/tasks/WP03-retire-core-layered-predicate.md`
**Requirement Refs**: FR-008, FR-009, FR-010, FR-011, C-001, C-003, NFR-001

### Included Subtasks

T030 Add `has_layered_repository` property + `_HAS_LAYERED_REPOSITORY_KINDS` frozenset (11 kinds = all but TEMPLATE/ANTI_PATTERN) + derived `LAYERED_REPOSITORY_KIND_PLURALS` to `artifact_kinds.py`, with a "coincides with org_requirable today — do not merge" docstring; unit tests first (RED).
T031 Repoint `_charter_pack_collect.py` `_ORG_ARTIFACT_DIRS` (collision scan + dir count) to the predicate; add tests proving glossary_pack/skill/asset collision + count coverage.
T032 Repoint `org_layer.py` `_OVERRIDABLE_ARTIFACT_TYPES` to the predicate; add a test proving an org override of each new kind is flagged.
T033 Widen `api_source.py` `DEFAULT_ARTIFACT_TYPES` to the 11 layered kinds (operator decision: widen); update/extend the 404-fallback test.
T034 Give `_charter_pack_cutover_snapshots.py` `DEFAULT_KIND_GATE` its own frozenset literal (NOT the predicate); keep the snapshot equality test green.
T035 Delete `ArtifactKind.core`, `_CORE_KINDS`, `CORE_KIND_PLURALS` + its `__all__` entry; remove the `charter.drg` re-export (import + `__all__`) and the two `_FACADE_TABLE["charter.drg"]` rows; repo-wide zero-reference check.

### Dependencies

- Depends on WP02 (shared `artifact_kinds.py`; the new frozenset must pass the live kind gate).

### Risks & Mitigations

- The `DEFAULT_KIND_GATE` fifth usage must NOT get the topology predicate → T034 isolates it before T035 deletes the symbol.
- Facade gate test file overlaps WP01 → sequential single_branch; WP03 only removes the two stale rows.

---

## Work Package WP04: Pack-tier token single authority (Priority: P2)

**Goal**: One kernel-owned pack-tier token (spelling `"built-in"`), every tier-token/rank/provenance site deriving from it, net-new empty-allowlist gate; the on-disk `packs/built-in/` directory and `_BUILT_IN_DIR_NAME` stay fixed.
**Independent Test**: A planted pack-tier token literal under `src/` is flagged by the new gate; `grep` shows one tier-token spelling; existing built-in-location and kind-vocab gates stay green.
**Prompt**: `/tasks/WP04-pack-tier-token-authority.md`
**Requirement Refs**: FR-012, FR-013, FR-014, C-001, C-003, NFR-001, NFR-003

### Included Subtasks

T050 Verify no `"builtin"`/`"built-in"` tier-token/provenance value is persisted or compared against serialized data (snapshots, fixtures, config); record any exclusion with rationale.
T051 Add `src/kernel/pack_tiers.py`: canonical tier token (`"built-in"`), ordered tuple, rank map, provenance helper; unit tests (RED first for the single-spelling invariant).
T052 Add `tests/architectural/test_pack_tier_token_single_authority.py` with a planted-literal self-mutation test; empty allowlist — RED first.
T053 Migrate `pack_paths.py`/`presets.py` `PackTier` and `pack_skills/validation.py` `Tier` to the authority (one spelling).
T054 Migrate `pack_skills/repository.py` `_TIER_RANK` and `agent_profiles/repository.py` `_LAYER_RANK` to the authority rank.
T055 Migrate `pack_manager.py` `_LAYER_SEGMENTS`, `list_cmd.py` tier map, and `drg/merge.py` layer markers to the authority.
T056 Migrate the `"builtin"` provenance strings (context_json, progressive_disclosure, skill_preparation, mission_type_profiles, runtime discovery, base.py, diagnostics, resolver, context) to the authority spelling.
T057 GREEN the tier gate; confirm built-in-location + kind-vocab + path-authority gates stay green.

### Dependencies

- None (independent vocabulary; files disjoint from WP02/WP03). Sequenced after WP03 under single_branch.

### Risks & Mitigations

- Must split tier-sense from the on-disk directory sense → T050/T053-T056 touch only tier tokens, never `_BUILT_IN_DIR_NAME` or the `packs/built-in/` path segment.
- A persisted provenance value → T050 gates each change; exclude + document if found.

---

## Work Package WP05: Delete dead standalone generated copies (Priority: P3)

**Goal**: Delete the 13 dead `spec-kitty-standalone.md` generated agent copies that point at the removed `src/doctrine/skills/...` path (no regeneration path exists). Leave `.kittify/charter/graph.yml` untouched per its existing migration decision + guard test.
**Independent Test**: `git ls-files '*/spec-kitty-standalone.md'` returns nothing; `grep -rl 'src/doctrine/skills/' <agent dirs>` is empty; `test_retired_activation.py` still passes; `graph.yml` is byte-unchanged.
**Prompt**: `/tasks/WP05-delete-dead-standalone-copies.md`
**Requirement Refs**: FR-015, C-002, C-004

### Included Subtasks

T070 Confirm no `src/` reader or manifest/ownership contract references the 13 copies (they are unmanaged orphans; deletion is the operator-approved remedy).
T071 Delete the 13 `*/spec-kitty-standalone.md` files across the generated agent dirs; leave `graph.yml` untouched.

### Dependencies

- None (independent; file deletions only).

### Risks & Mitigations

- A manifest-owned path would make deletion unsafe → T070 proves they are unmanaged orphans first.

---

## Dependency & Execution Summary

- **Sequence**: WP01 → WP02 → WP03 (shared gate/authority chain) → WP04 → WP05. WP04 and WP05 are logically independent of the chain and of each other; under `single_branch` they run sequentially.
- **MVP Scope**: WP01+WP02+WP03 are the single-authority core (drift-proofing the kind vocabulary and retiring `core`). WP04 completes the tier half; WP05 is campsite cleanup.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP02 |
| FR-003 | WP02 |
| FR-004 | WP02 |
| FR-005 | WP02 |
| FR-006 | WP02 |
| FR-007 | WP02 |
| FR-008 | WP03 |
| FR-009 | WP03 |
| FR-010 | WP03 |
| FR-011 | WP03 |
| FR-012 | WP04 |
| FR-013 | WP04 |
| FR-014 | WP04 |
| FR-015 | WP05 |
| NFR-001 | WP02, WP03, WP04 |
| NFR-002 | WP01, WP02, WP03, WP04 |
| NFR-003 | WP04 |
| NFR-004 | WP02, WP04 |
| C-001 | WP02, WP03, WP04 |
| C-002 | WP05 |
| C-003 | WP02, WP03, WP04 |
| C-004 | WP05 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Non-class re-export self-test (RED) | WP01 | P1 | No |
| T002 | Identity-scan origin resolution | WP01 | P1 | No |
| T010 | R1′ self-test | WP02 | P1 | No |
| T011 | R4 self-test | WP02 | P1 | No |
| T012 | R5 self-test | WP02 | P1 | No |
| T013 | R6 self-test | WP02 | P1 | No |
| T014 | Legitimate-construct guard test | WP02 | P1 | No |
| T015 | Implement R1′/R4/R5/R6 | WP02 | P1 | No |
| T016 | Migrate R1′ sites | WP02 | P1 | Yes |
| T017 | Migrate R4 site | WP02 | P1 | Yes |
| T018 | Migrate R5 site | WP02 | P1 | Yes |
| T019 | Migrate R6 sites | WP02 | P1 | Yes |
| T020 | Synthesizable subset + docstring | WP02 | P1 | No |
| T030 | has_layered_repository + tests | WP03 | P1 | No |
| T031 | Repoint collision scan + counts | WP03 | P1 | No |
| T032 | Repoint org-layer lint | WP03 | P1 | No |
| T033 | Widen API fallback to 11 | WP03 | P1 | No |
| T034 | Isolate DEFAULT_KIND_GATE | WP03 | P1 | No |
| T035 | Delete core + facade rows | WP03 | P1 | No |
| T050 | Persistence safety audit | WP04 | P2 | No |
| T051 | kernel/pack_tiers.py authority | WP04 | P2 | No |
| T052 | tier-token gate (RED) | WP04 | P2 | No |
| T053 | Migrate PackTier/Tier | WP04 | P2 | No |
| T054 | Migrate rank maps | WP04 | P2 | No |
| T055 | Migrate segments/list/merge markers | WP04 | P2 | No |
| T056 | Migrate provenance strings | WP04 | P2 | No |
| T057 | GREEN gates | WP04 | P2 | No |
| T070 | Orphan-safety proof | WP05 | P3 | No |
| T071 | Delete 13 copies | WP05 | P3 | No |

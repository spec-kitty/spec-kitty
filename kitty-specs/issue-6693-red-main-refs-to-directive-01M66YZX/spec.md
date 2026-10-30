# Mission Specification: Repoint the red-main references to the RED_MAIN_RELEASE_DISCIPLINE directive

**Mission Branch**: `issue-6693-red-main-refs-to-directive`
**Created**: 2026-10-30
**Status**: Draft
**Input**: GitHub issue spec-kitty/spec-kitty#6693 — "Repoint red-main-release-discipline procedure references to the RED_MAIN_RELEASE_DISCIPLINE directive on the next open-packs pin bump"

**Rename target (bulk edit)**: this mission repoints the artifact reference
`procedure:red-main-release-discipline` → `directive:RED_MAIN_RELEASE_DISCIPLINE`
and `procedure:spec-kitty-red-main-policy` →
`directive:SPEC_KITTY_RED_MAIN_POLICY`, with per-category rules captured in
`occurrence_map.yaml`. The mission is `change_mode: bulk_edit` in `meta.json`
because the same existing string changes in more than one file (DIRECTIVE_035).
Historical records keep the old wording (C-002).

**Guidance recorded**: the brief for this run says doctrine content lives in
`spec-kitty-open-packs` and is *fetched, not committed*. The only legitimate
upstream move from this repository is a pin bump; fetched pack content is never
hand-edited. If the upstream change did not exist, the mission stops and reports.
It exists: `spec-kitty/spec-kitty-open-packs#74` merged as `72cb7dbc` on
2026-10-26, so this mission vendors that commit and repoints core.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A maintainer's governed command stops naming a retired artifact (Priority: P1)

A maintainer runs any governed command in a Spec Kitty checkout (here, this
repository itself, and any consumer project that activated the red-main
procedure). Before this change, after the pin moves forward, the charter context
renderer reports `Charter catalog miss for procedure:red-main-release-discipline;
cause=missing_artifact`, and `doctor charter-packs` reports `DENY_UNKNOWN_ID` for a
denied id no layer provides. The maintainer sees a governance surface that names
an artifact that no longer exists.

**Why this priority**: this is the user-visible half of the defect. A dangling
reference in the charter makes every governed command print a warning and makes
Standing Order #9's doctrine pointer unresolvable, so the rule that keeps main
honest is no longer reachable from the charter.

**Independent Test**: run `spec-kitty charter context --action implement` and
`spec-kitty doctor charter-packs` in a checkout with the new pins; assert zero
catalog misses and zero activation-ledger warnings.

**Acceptance Scenarios**:

1. **Given** the pins point at the open-packs commit that landed #74, **When** a
   maintainer runs `spec-kitty charter context --action implement`, **Then** no
   artifact referenced by the active charter is reported missing.
2. **Given** the same checkout, **When** `spec-kitty doctor charter-packs` runs,
   **Then** the activation ledger reports no `DENY_UNKNOWN_ID` warning.
3. **Given** the same checkout, **When** the charter's own red-main standing
   order is read, **Then** it points at the `RED_MAIN_RELEASE_DISCIPLINE`
   directive, not at a procedure id that no longer resolves.

---

### User Story 2 - The vendored pin is the single source of the doctrine change (Priority: P1)

A maintainer who wants to know *where* the red-main rule now lives follows the pin
lockfile rather than a copy: `packs/built-in.source.yaml` and
`packs/internal.source.yaml` name one open-packs commit, `make sync-packs`
fetches both trees, and every core-side test reads the fetched tree.

**Why this priority**: it is equal-first with story 1 — vendoring without
repointing leaves six red tests, and repointing without vendoring is a no-op.
Doing the change by hand-editing `packs/**` would be wiped by the next sync and
would break the digest verification.

**Independent Test**: `spec-kitty charter pack vendor --check` passes for both
packs, and no tracked file under `packs/` changes in the diff.

**Acceptance Scenarios**:

1. **Given** a clean clone at the branch head, **When** `make sync-packs` runs,
   **Then** both packs are fetched from the pinned commit and verify against
   their recorded tree digests.
2. **Given** the branch diff, **When** it is inspected for tracked changes under
   `packs/`, **Then** only the two `*.source.yaml` pin lockfiles appear.
3. **Given** the fetched built-in tree, **When** `packs/built-in/directives/`
   and `packs/built-in/procedures/` are listed, **Then**
   `red-main-release-discipline.directive.yaml` is present and
   `red-main-release-discipline.procedure.yaml` is absent.

---

### User Story 3 - Core's own reference surfaces agree with the fetched packs (Priority: P2)

A reviewer asks whether *every* place in core that names the red-main artifact
agrees with what the packs now ship. The curated DRG edge, the five tests named by
the issue, the `minimal_org_pack_2` fixture, and this repository's own charter
surfaces must all name the directive.

**Why this priority**: each of these is a place where a second, stale source of
truth would otherwise survive the bump — mechanically enforced by an existing
test for the curated edge (regenerated graph must equal the shipped graph) and by
the tests the issue lists.

**Independent Test**: run the five named test files plus the charter and
pack-inventory gates; all pass, and the regenerated built-in graph is
byte-identical to the shipped one.

**Acceptance Scenarios**:

1. **Given** the bumped pins, **When**
   `tests/charter_offering/drg/migration/test_extractor_projection.py` runs,
   **Then** pure regeneration produces exactly the shipped built-in graph — no
   extra `procedure:red-main-release-discipline` node from the curated edge.
2. **Given** the bumped pins, **When**
   `tests/charter_offering/drg/test_single_owner_edges.py`,
   `tests/charter_offering/test_testing_doctrine_single_owner.py` and
   `tests/integration/test_org_pack_chain_delivery.py` run, **Then** the
   `test-first-bug-fixing -> RED_MAIN_RELEASE_DISCIPLINE` `requires` edge and the
   internal pack's `refines` edges are found in the fetched trees.
3. **Given** the bumped pins, **When** the `minimal_org_pack_2` fixture is merged
   with the built-in layer, **Then** its `refines` edge resolves to
   `directive:RED_MAIN_RELEASE_DISCIPLINE` and the DRG validator reports no
   dangling target.

---

### Edge Cases

- **The internal pack's `spec-kitty-red-main-policy` also moved.** It is a
  procedure today and a directive (`SPEC_KITTY_RED_MAIN_POLICY`) after #74. This
  repository does not activate it directly, but the internal pack's DRG fragment
  and glossary now point the built-in rule at the directive; the org pack's
  `refines` edges must still reach the consumer (asserted by
  `test_class_b_internal_pack_delivers_every_declared_kind`).
- **A pin bump can be wider than the change it is for.** Pinning to open-packs
  `main` tip would drag in the later "sanitized-shape" migration. This mission
  pins the commit that carries #74 and nothing else; the diff between the old pin
  and the new one is the red-main move alone (six built-in files, five internal
  files).
- **A retired id can leave a deny-list residue.** Deactivating the procedure
  writes it into `deactivated_procedures`; because no layer provides it any more,
  `doctor charter-packs` reports `DENY_UNKNOWN_ID`. The stale deny entry is
  removed by hand (the doctor's own prescription) rather than left to rot.
- **Consumers who activated the procedure by name.** Their activation ledger will
  still name the retired procedure. Core cannot rewrite a consumer's project
  ledger from this repository; this mission fixes this repository's own ledger and
  states the consumer-side consequence in the changelog.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Pin both packs to the commit that landed open-packs#74 | As a maintainer, I want the built-in and internal pins to name open-packs `72cb7dbc` so that the fetched trees carry the directive and no hand-edited copy exists. | High | Open | [build] | no — paired with FR-002's absent-procedure assertion on the same fetched tree |
| FR-002 | Repoint the curated DIRECTIVE_030 edge | As a maintainer, I want `_CURATED_ARTIFACT_EDGES` to suggest `directive:RED_MAIN_RELEASE_DISCIPLINE` so that graph regeneration mints no orphan procedure node. | High | Open | [build] | no — the shipped-vs-regenerated graph equality check fails without it |
| FR-003 | Repoint the five named tests and the org-pack fixture | As a reviewer, I want the tests and the `minimal_org_pack_2` fixture to assert the directive so that each reference surface is checked against the fetched tree. | High | Open | [build] | no — each assertion names a node the packs no longer ship as a procedure |
| FR-004 | Repoint this repository's own charter surfaces | As a maintainer, I want the activated procedure replaced by the activated directive and the stale deny entry removed so that governed commands resolve cleanly. | High | Open | [build] | no — the new ledger-resolution guard test fails on the unfixed ledger |
| FR-005 | Guard the ledger-resolution invariant | As a maintainer, I want a test that every id in this repository's activation ledger resolves against the fetched packs, so the next re-kinding upstream is caught here rather than by a warning nobody reads. | Medium | Open | [build] | no — it fails on the pre-fix ledger (positive control: the fixed ledger passes on the same fixture) |
| FR-006 | Record the change in the changelog | As a consumer, I want an `[Unreleased]` entry so that I know the red-main rule is now a directive and what to do if I activated the procedure. | Medium | Open | [build] | no — an entry that names neither the directive nor the consumer action does not meet the doc standard |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No fetched pack file is edited | The branch diff contains zero tracked changes under `packs/**` except `packs/built-in.source.yaml` and `packs/internal.source.yaml`; the fetched trees stay untracked and regenerable. | Maintainability | High | Open |
| NFR-002 | No stale reference survives in core | Zero occurrences of `procedure:red-main-release-discipline` outside the preserved-history surfaces named as `do_not_change` exceptions in `occurrence_map.yaml` (this repository's past `kitty-specs/**` snapshots, the changelog's earlier entries, dated ADRs and engineering notes, the #4253 narrative in `tests/charter/test_activation_preserves_effective_4253.py`, the pre-relocation `content-manifest.json`, and `.kittify/evidence/**`) at the branch head. | Correctness | High | Open |
| NFR-003 | Regeneration is deterministic | `spec-kitty charter pack regenerate-graph` on the fetched built-in tree reproduces the shipped graph byte-for-byte (the existing zero-delta gate stays green). | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Upstream-first | The doctrine change is authored in `spec-kitty-open-packs` (#74) and reaches core only through the pin; this mission authors no doctrine. | Process | High | Open |
| C-002 | Historical citations are preserved | Changelog history, merged ADRs, past missions' `kitty-specs/` and recorded evidence keep their original wording; they are snapshots, not live references. | Process | High | Open |
| C-003 | The pin is a single commit | Both packs pin the same open-packs commit (`72cb7dbc`) so one doctrine change is not split across two upstream states. | Technical | Medium | Open |

### Key Entities

- **Pin lockfile** (`packs/<pack>.source.yaml`): records `commit`, `subtree`, `tree_digest`, `requires_core`. The only tracked representation of pack content in core.
- **Fetched pack tree** (`packs/built-in/`, `packs/internal/`): untracked, digest-verified, regenerated by `make sync-packs`; the source every doctrine test reads.
- **Activation ledger** (`.kittify/charter/activation.yaml`): this repository's allow/deny lists per artifact kind; the single authority for what is active.
- **Compiled charter** (`.kittify/charter/charter.yaml`): the catalog projection of the ledger; regenerated by the `charter activate`/`deactivate` compile seam.
- **Curated artifact edges** (`_CURATED_ARTIFACT_EDGES`): non-default DRG relations core adds on top of the pack-authored ones.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The six tests that are red at the bumped pin are green, and the pins are the only reason they were red — measured by reverting only the reference repoints and seeing all six fail again. — [build] · no-op passable: no
- **SC-002**: `spec-kitty doctor charter-packs` reports zero activation-ledger warnings and `spec-kitty charter consistency-check` reports coherent, on the branch head. — [build] · no-op passable: no
- **SC-003**: The branch diff shows two changed tracked files under `packs/`, both `*.source.yaml`. — [ratchet] · no-op passable: no — the pre-fix tree shows the old pins, so the probe distinguishes states on the same fixture
- **SC-004**: `git grep -n 'procedure:red-main-release-discipline'` at the branch head returns hits only under the preserved-history paths of C-002. — [build] · no-op passable: no

## Assumptions

- open-packs#74 (`72cb7dbc`) is the correct pin target; it is on open-packs `main`
  and its built-in tree satisfies `requires_core: '>=4.0.0rc7,<5'`, which the
  current CLI (`4.0.0rc8`) meets.
- This repository's own charter is the only *live* consumer-side activation in
  scope; consumer projects' ledgers are documented, not rewritten.
- The `graph.yaml` label refresh and `generated_at` stamp that the ledger compile
  emits are legitimate regeneration output, not hand edits.

## Out of Scope

- Removing the pending-vendoring allowlist entry in the open-packs CI (that is an
  open-packs-side change, named in the issue as the follow-up).
- Bumping past `72cb7dbc` to the later open-packs `main` (the sanitized-shape
  migration is a separate, breaking change).
- Any doctrine content change: no wording of the red-main rule is authored or
  reworded here.
- Renaming the artifact file stems: the new directive keeps the
  `red-main-release-discipline` stem, so config ids remain stable.

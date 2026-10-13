# Mission Specification: CI router selects charter + dossier for mission-manifest edits

**Mission Branch**: `issue-6125-ci-router-charter-dossier-routing`
**Created**: 2026-10-13
**Status**: Draft
**Input**: Issue #6125 — "CI path router does not select charter/dossier modules for an expected-artifacts.yaml change"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A mission-manifest edit runs charter AND dossier per-PR (Priority: P1)

A maintainer opens a PR that edits a mission's `packs/built-in/missions/*/expected-artifacts.yaml`
(the artifact contract consumed by `charter.offering.missions` and `dossier.ManifestRegistry`).
Today the per-PR CI path router selects **zero** test modules for that change — only the
non-module `corpus` group matches and `unmatched_src` is False — so neither `tests/charter`
(+`tests/charter_offering`) nor `tests/dossier` runs. A broken charter/dossier assertion
therefore passes the required PR gates and surfaces only in the nightly, i.e. as red `main`.
After this mission, the router selects the `charter` **and** `dossier` modules for such an edit,
so the assertions that a manifest-shape change moves are checked before merge.

**Why this priority**: This is the whole point of #6125 — closing a per-PR → red-main hazard
in CI routing. Without it, manifest edits keep shipping blind.

**Independent Test**: A router-parity test calls the single routing authority
`scripts/ci/gate_selection.select_modules(["packs/built-in/missions/software-dev/expected-artifacts.yaml"])`
and asserts the result is a superset of `{"charter", "dossier"}` (and for all four manifests).
RED on `origin/main`, GREEN after the routing change.

**Acceptance Scenarios**:

1. **Given** current `main`, **When** `select_modules` is called with any of the four mission
   `expected-artifacts.yaml` paths, **Then** the result is `frozenset()` (the gap — RED proof).
2. **Given** this mission's change, **When** `select_modules` is called with any of the four
   mission `expected-artifacts.yaml` paths, **Then** the result ⊇ `{"charter", "dossier"}`.
3. **Given** this mission's change, **When** `select_gates(["packs/built-in/missions/foo.md"])`
   is evaluated, **Then** it still selects zero code shards and does not trip `unmatched_src`
   (the file-specific glob must not broaden to every `packs/**` corpus file).

---

### User Story 2 - `tests/dossier` has a real per-PR home as a selectable module (Priority: P1)

`dossier` is not a registry module today; `tests/dossier` + `tests/specify_cli/dossier` are
nightly-only (`out_of_matrix_test_dirs`). Even a `src/specify_cli/dossier/**` edit (which forces
run-all via the fail-closed catch-all) never runs `tests/dossier`, because it is in no module's
matrix. Minting a real `dossier` module gives those trees a per-PR executor and narrows a
dossier-source diff from run-all to a `dossier`-scoped shard (an improvement).

**Why this priority**: Required for Story 1's dossier leg and for the issue's second suggested
fix ("make `tests/dossier` a selectable per-PR module").

**Independent Test**: `select_modules(["src/specify_cli/dossier/manifest.py"])` includes
`"dossier"` (and no longer forces blanket run-all), and `"dossier"` is in the registry module
universe; the registry↔scrub bijection/verbatim and claim-once guards stay green.

**Acceptance Scenarios**:

1. **Given** this mission's change, **When** the registry module universe is read, **Then**
   `dossier` is present with `test_dirs` `[tests/dossier, tests/specify_cli/dossier]`.
2. **Given** this mission's change, **When** a `src/specify_cli/dossier/**` path is routed,
   **Then** `select_modules` includes `dossier` and `unmatched_src` is False (scoped, not run-all).
3. **Given** this mission's change, **When** the shard-timings strict check runs, **Then** the
   committed `dossier` durations equal the live-collected count (measured, not guessed).

---

### Edge Cases

- A corpus-only edit to a non-manifest pack file (`packs/built-in/missions/foo.md`) must still
  select zero code shards — the manifest glob is file-specific (`…/expected-artifacts.yaml`), so
  it never matches `foo.md`.
- A pure `src/specify_cli/dossier/**` edit must route to the `dossier` module only, not trip the
  fail-closed run-all (the new group is src-backed and joins the `unmatched` union + heavy-battery gate).
- A mission-manifest edit must not broaden selection beyond `charter` + `dossier` (no `missions`,
  no run-all).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Router-parity gate for manifest edits | As a maintainer, I want a non-vacuous test asserting a mission-manifest diff selects charter+dossier so that the routing gap cannot silently reopen. | High | Open | [ratchet] | no — RED on origin/main, GREEN after; a self-break (removing a glob) flips it red |
| FR-002 | Charter leg routes the manifest glob | As a maintainer, I want `packs/built-in/missions/**/expected-artifacts.yaml` added to the `charter` group (scrub roots + registry roots + router filter, in lockstep) so that a manifest edit selects the `charter` module. | High | Open | [build] | no — pinned by FR-001 and the verbatim/bijection guards |
| FR-003 | Dossier module minted | As a maintainer, I want a real `dossier` module (scrub group + registry row + router filter group) with `test_dirs` `[tests/dossier, tests/specify_cli/dossier]` so that a dossier-source or manifest edit runs those trees per-PR. | High | Open | [build] | no — pinned by FR-001/FR-005 and the registry guards |
| FR-004 | Out-of-matrix claim released | As a maintainer, I want `tests/dossier` and `tests/specify_cli/dossier` removed from `out_of_matrix_test_dirs` when the `dossier` row claims them so that the claim-once guard stays green. | High | Open | [build] | no — claim-once guard reds on double-claim |
| FR-005 | Measured shard-timings for dossier | As a maintainer, I want `.github/ci-shard-timings.json` to carry a real measured `dossier` capture (committed == collected) so that the strict/nightly shard-timings checks pass. | High | Open | [build] | no — strict check compares committed to live collection |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Single canonical authority | Registry, scrub, and router filter for charter/dossier stay byte-verbatim in lockstep; no second hand-maintained path→group map is introduced. | Architecture | High | Open |
| NFR-002 | No new size/length ratchet | The mission adds a routing gate only; it introduces no new size/length allowlist or ratchet (operator ruling). | Architecture | High | Open |
| NFR-003 | Selection not broadened | A mission-manifest edit selects exactly `charter` + `dossier` (plus always-on gates); not `missions`, not run-all. | Correctness | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Router verbatim guard | Any glob on a scrub-backed group's router filter must equal its scrub `roots` ordered-exactly (`test_router_src_filters_derive_from_scrub_verbatim`); the manifest glob therefore lives in scrub roots too. | Technical | High | Open |
| C-002 | File-specific glob only | The manifest glob must be file-specific (`…/expected-artifacts.yaml`), never the broad `packs/built-in/missions/**`, to keep the corpus golden green and avoid `_canonical_test_mirror` pollution. | Technical | High | Open |
| C-003 | No product code | The mission touches CI wiring + tests only; no `src/**` product behaviour changes. | Technical | High | Open |

### Key Entities

- **Mission manifest** (`packs/built-in/missions/<type>/expected-artifacts.yaml`): the artifact
  contract; produced by `charter.offering.missions`, consumed by `charter.activation` and
  `dossier.ManifestRegistry`.
- **Routing authority** (`scripts/ci/gate_selection.py`): parses the router's two authorities;
  `select_modules` answers which registry modules a diff selects.
- **Module registry / scrub / router filter**: three verbatim transcriptions of one group→roots source.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On `origin/main` the parity test is RED (`select_modules(manifest) == frozenset()`);
  after the change it is GREEN (`⊇ {charter, dossier}`) for all four manifests — [ratchet] · no-op passable: no
- **SC-002**: The named CI gate suites (`test_gate_selection_authority`, `test_module_shard_registry`,
  `test_retirement_scrub`, `test_out_of_matrix_evidence`, `test_ci_router_transcription_guards`,
  `test_ci_quality_path_filters`, `test_ci_corpus_trigger_completeness`, `tests/ci/test_ci_module_wiring`)
  are GREEN after the change — [build] · no-op passable: no
- **SC-003**: `tests/dossier` + `tests/specify_cli/dossier` pass as the newly-routed `dossier`
  module (prove the module green) — [build] · no-op passable: no
- **SC-004**: `.github/ci-shard-timings.json` carries a `dossier` capture whose committed count
  equals the live-collected count (measured, not guessed) — [build] · no-op passable: no

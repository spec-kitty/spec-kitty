# Mission Specification: Deep ROI pass over the large tests/charter suites

**Mission Branch**: `feat/6485-charter-tests-deep-roi-pass` (stacked on PR #6483)
**Created**: 2026-10-19
**Status**: Draft
**Input**: GitHub issue #6485 — follow-up to PR #6483's first `tests/charter` pass.

## Intent Summary

A Spec Kitty maintainer runs the charter test suite in CI and locally. Today the large
`tests/charter` suites carry tests that cost run time and maintenance without guarding a
live contract: change-detectors, tautologies, mock-only tests, tests of retired paths,
private-helper tests already covered through the public path, and near-duplicate files.
After this mission, those suites keep only tests that guard live contracts. Every removal
is either a deletion with a named covering test or a merge/parametrization into a
surviving test, and every removal is recorded in a ledger. No product code changes.

Coverage is a signal, not a floor: a small drop in `src/charter` line coverage is
acceptable when the removed tests are low-ROI (clunky, flaky or heavy for a marginal
coverage gain). Each such drop is stated with its reason.

## Scope

**In scope** (paths relative to `tests/charter/`):

- Large files: `test_context.py`, `test_mission_type_profiles.py`,
  `packs/test_pack_validator.py`, `activation/test_org_charter.py`, `test_resolver.py`,
  `synthesizer/test_synthesize_reconcile.py`, `test_context_selection_render.py`,
  `synthesizer/test_orchestrator_resynthesize.py`,
  `synthesizer/test_bundle_validate_extension.py`, `synthesizer/test_manifest.py`,
  `test_org_drg_loader.py`, `test_pack_manager.py`, `test_cascade.py`, `test_compiler.py`.
- Families: `test_context_*_seams.py` and `*_parity.py` under `tests/charter/`.
- Suspected duplicate clusters:
  1. `synthesizer/test_synthesize_path_parity.py` ↔ `synthesizer/test_orchestrator_synthesize.py`
  2. `activation/test_context_identity_reuse.py` ↔ `activation/test_context_org_root_identity.py`
  3. `activation/test_effective_set.py` ↔ `activation/test_effective_set_chain.py`
  4. `test_charter_cwd_isolation.py` ↔ `test_charter_cwd_tripwire.py`
  5. `test_schemas.py`, `test_schemas_additive_fields.py`, `test_schemas_selection.py`
  6. `test_retired_pack_fields.py` ↔ `test_retired_accompanies_doctrine_pack.py`
  7. `test_sync_paths.py` ↔ `test_sync.py`

- Heavy files (added at plan time, operator decision): `test_compiler_charter_yaml.py`,
  `test_context_unknown_language.py`, `test_regenerate_rederives_languages.py`,
  `test_progressive_disclosure.py`, `test_every_load_delivery.py`,
  `test_active_languages_idempotency.py`, `test_retrospective_governance_emit.py`,
  `test_activation_preserves_effective_4253.py`. For these, a test may also be made
  cheaper (shared fixture, smaller project, fewer repeated runs) as long as it keeps its
  contract.

**Out of scope**: product code under `src/`; test files outside the list above (they may
be named as *covering* tests but are not edited, except as the receiving file of a merge
when that is the natural home); `tests/architectural/` gates.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Prune the large suites (Priority: P1)

A maintainer opens any in-scope large file after the mission and finds only tests that
guard a live contract; each removed test is listed in the ledger with its covering test
or merge target.

**Independent Test**: For one file, the ledger rows match the diff and the file's
surviving tests pass.

**Acceptance Scenarios**:

1. **Given** a test asserting an exact incidental string, count or ordering, **When** the
   file is reviewed, **Then** it is deleted or rewritten to assert the contract, and the
   ledger records the verdict.
2. **Given** a private-helper test whose branches are exercised through a public entry
   point, **When** reviewed, **Then** it is deleted and the ledger names the public-path test.
3. **Given** a test guarding a live contract with no other coverage, **When** reviewed,
   **Then** it is kept.

### User Story 2 - Resolve the duplicate clusters (Priority: P1)

A maintainer sees a recorded verdict for each of the 7 clusters: merged, one side
deleted, or confirmed distinct.

**Acceptance Scenarios**:

1. **Given** two files testing the same behaviour, **When** resolved, **Then** one
   survives (possibly parametrized) and the ledger names it.
2. **Given** two files that only look alike, **When** resolved, **Then** both stay and
   the ledger records why they are distinct.

### Edge Cases

- A deleted test is the only coverage of a rarely-hit branch: keep it unless the test is
  heavy/flaky and the branch is low-risk; if removed, state the coverage loss and reason.
- A test is marked `regression` or pins a known issue: keep unless the issue is closed
  and a functional test covers the behaviour.
- A covering test lives in `tests/charter_offering/` or `tests/architectural/`: name it
  by node id.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Requirement | Status | Delivery | No-op passable? |
|----|-------------|--------|----------|-----------------|
| FR-001 | Every test function in the in-scope large files and families gets a verdict (keep / delete / merge / rewrite) against the #6485 rubric. | Draft | [build] | no — the ledger must list every reviewed file with a non-empty verdict count |
| FR-002 | Every deleted test is recorded in the mission ledger with the node id of its covering test, or with the merge target it was folded into. | Draft | [build] | no — each deletion in the diff must have a ledger row |
| FR-003 | Each of the 7 duplicate clusters gets a recorded verdict: merged, one side deleted, or confirmed distinct with a reason. | Draft | [build] | no — 7 cluster rows required |
| FR-004 | Near-duplicate tests may be merged or parametrized into one surviving test that asserts the union of their contract checks. | Draft | [build] | no |
| FR-005 | Tests that guard a live contract and have no equivalent elsewhere are kept. | Draft | [ratchet] | yes — positive control: the kept-test count per file is recorded in the ledger |
| FR-007 | Each in-scope heavy file's total test time drops, or the ledger records why its cost is justified. | Draft | [build] | no — before/after per-file time is recorded |
| FR-006 | Any drop in `src/charter` line coverage caused by a removal is stated in the ledger with its reason (low ROI: clunky, flaky or heavy for marginal gain). | Draft | [build] | no |

### Non-Functional Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| NFR-001 | All surviving tests in `tests/charter/` and `tests/charter_offering/` pass after the mission. | Draft |
| NFR-002 | Total `src/charter` line-coverage drop from this mission is at most 1.0 percentage point, measured on `tests/charter` + `tests/charter_offering`, before vs after. | Draft |
| NFR-003 | Wall-clock time of `tests/charter/` does not increase. | Draft |

### Constraints

| ID | Constraint | Status |
|----|-----------|--------|
| C-001 | No changes to product code under `src/`. | Draft |
| C-002 | No changes to `tests/architectural/` gates. | Draft |
| C-003 | The branch stays stacked on PR #6483 until it merges, then rebases onto `main`. | Draft |
| C-004 | Changed test files pass `ruff check`, `ruff format --check --force-exclude` and `mypy` with no new suppressions. | Draft |

## Success Criteria

- SC-001: 100% of in-scope files have a ledger section with per-test verdicts. — [build] · no-op passable: no
- SC-002: All 7 duplicate clusters have a recorded verdict. — [build] · no-op passable: no
- SC-003: The in-scope test line count shrinks, and every removed test traces to a ledger row. — [build] · no-op passable: no
- SC-004: Coverage drop ≤ 1.0 pp with every contributing removal justified. — [ratchet] · no-op passable: yes (positive control: before/after coverage numbers recorded)

## Key Entities

- **ROI ledger**: per-file table of reviewed tests — test node id, verdict, covering test or merge target, and reason.

## Assumptions

- PR #6483's deletions are final; the mission reviews the tree as #6483 leaves it.
- The 1.0 pp coverage budget is a mission default chosen from the operator's "slight drop is allowed" steer.

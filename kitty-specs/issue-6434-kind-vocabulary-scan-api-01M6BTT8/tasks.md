# Work Packages: Promote kind_vocabulary scanning helpers to a module-internal API

**Mission**: `issue-6434-kind-vocabulary-scan-api-01M6BTT8`
**Branch**: `issue-6434-kind-vocabulary-scan-api` (planning base and merge target)
**Inputs**: `spec.md`, `plan.md`, `research.md` in this mission directory.

**Scope note**: one work package. A single behaviour-preserving promotion of five
`charter`-layer seams, with the red-first architectural ratchet in the same WP because the
ratchet only turns green once every call site has moved — splitting it would leave a WP
that ends red.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** means the subtask is safe to parallelise (different files, no ordering
  dependency). This WP is executed by a single implementer, so the markers document
  ordering freedom, not a claim of parallel execution.
- Every subtask below appears in exactly one work package.

## Path Conventions

Repository root is the project root; all paths are repo-root-relative.

- Production: `src/charter/activation/`
- Tests: `tests/charter/`, `tests/charter_offering/`, `tests/architectural/`
- Changelog: `docs/changelog/CHANGELOG.md`

---

## Work Package WP01: Promote the scanning and id seams, then ratchet them (Priority: P0)

**Goal**: `kind_vocabulary`'s scanning/id helpers, `IdentityIndex`'s per-kind scan and the
two governance seams named in issue #6434 become documented public names; every call site
in `src/` and `tests/` moves onto them; an architectural ratchet proves no retired
underscore name remains and cannot come back.

**Independent test**: run the new ratchet (red on the untouched tree, green after the
promotion) plus the scan-count, identity-index, parity and governance-bundle suites, and
confirm they pass with unchanged expectations.

**Prompt**: `tasks/WP01-promote-scanning-seams.md`

### Included Subtasks

T001 Write the ratchet test and run it red (retired-name scanner + public-surface control)
T002 Promote `kind_vocabulary`'s scanning and id helpers to public names
T003 Rewire `IdentityIndex` onto the public surface and make its per-kind scan public
T004 Move the scan-seam tests onto the public seams
T005 Rename `_load_action_governance_bundle` to `load_action_governance_bundle`
T006 Rename `compiler._direct_root_urns` to `direct_root_urns`
T007 Add the `[Unreleased]` changelog entry
T008 Run the targeted suites and the ratchet green, then record the proof

### Implementation Notes

- Anchored renames only: `rg "\b_scan_roots\b"` style matches, never a blind
  `sed s/_scan_roots/scan_roots/` — similar names exist that must not move
  (`_iter_mission_scan_roots`, `_default_scan_roots`, `catalog._resolve_scan_roots`,
  `_iter_charter_scan_roots`, `pack_assembler._read_id`).
- Keep `_org_scan_dirs`, `_layer_scan_dirs`, `_layer_candidate_dir`,
  `_under_reserved_builtin_subdir`, `_built_in_step_contract_dir`, `_scan_cache_key`,
  `_declares_id`, `_directive_ids_by_stem` private: no consumer outside their module.
- Update the docstring cross-references that name the old helpers (`pack_manager.py`,
  `identity_index.py`, `tests/charter_offering/test_activation_parity_guard.py`,
  `tests/charter/test_org_scan_dirs_activation_regression.py`,
  `tests/charter_offering/drg/test_unknown_kind_fails_loudly.py`).
- No behaviour edit: every renamed function keeps its body, its ordering and its
  fail-soft contracts.

### Parallel Opportunities

- T005/T006 are independent of T002–T004 (different modules, different tests) and may be
  done in either order.
- T007 does not depend on code shape.

### Dependencies

- T001 before T002 (red first).
- T003 depends on T002; T004 depends on T003.
- T008 last, after every other subtask.

### Risks & Mitigations

- **Rename collision with lookalike helpers** → anchored patterns and a post-rename
  `rg` sweep for the retired names.
- **Scan-count drift** → the seam wrapped by the tests stays the per-kind scan
  (`IdentityIndex.scan`), and the resolver-level seam stays `scan_dir_matches`; expected
  counts must not change.
- **Ratchet false green** → the test carries a negative control (a synthetic snippet with a
  retired name must be detected) and a positive control (the public names resolve).
- **Typed/strict mypy on touched modules** → public signatures keep their existing
  annotations; only the names change.

---

## Dependency & Execution Summary

- **Sequence**: WP01 is the only work package, so the lane graph is a single node.
- **Parallelization**: T005/T006 may interleave with T002–T004; everything else is ordered.
- **MVP scope**: WP01 is the whole mission.

## Requirements Coverage Summary

| Requirement | Covered by |
| --- | --- |
| FR-001 | T002 |
| FR-002 | T002 |
| FR-003 | T003 |
| FR-004 | T003, T004 |
| FR-005 | T005, T006 |
| FR-006 | T001, T008 |
| FR-007 | T004, T008 |
| NFR-001 | T004, T008 |
| NFR-002 | T002, T003 |
| NFR-003 | T001 |
| NFR-004 | T002, T005, T006 |
| C-001 | T002, T003, T005, T006 |
| C-002 | T002, T003, T004, T005, T006 |
| C-003 | T002, T003 |
| C-004 | T007 |
| SC-001 | T001, T008 |
| SC-002 | T004, T008 |
| SC-003 | T008 |
| SC-004 | T001, T008 |

## Subtask Index (Reference)

| Subtask | Description | WP | Priority | Parallel |
| --- | --- | --- | --- | --- |
| T001 | Ratchet test, run red first | WP01 | P0 | No |
| T002 | Promote `kind_vocabulary` scanning/id API | WP01 | P0 | No |
| T003 | Rewire `IdentityIndex`, public `scan` | WP01 | P0 | No |
| T004 | Move scan-seam tests to public names | WP01 | P0 | No |
| T005 | Rename `load_action_governance_bundle` | WP01 | P1 | Yes |
| T006 | Rename `compiler.direct_root_urns` | WP01 | P1 | Yes |
| T007 | Changelog entry | WP01 | P1 | Yes |
| T008 | Targeted suites + ratchet green | WP01 | P0 | No |

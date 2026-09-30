# Pre-merge squad (PHASE=pr): operator and orchestrator rulings

Date: 2026-09-29. Mission `charter-generation-drops-scoped-references-01M3M1KF` (#5257).
Evidence: `pr.merged.yaml`, `pr-refute-1.yaml` (7 of 7 confirmed), `pr.confirmed.yaml`.

## Operator ruling: PR-TESTS-001 (severity 4), accepted as #4732 territory

The new tests in `tests/specify_cli/charter_runtime/` (WP04) and
`tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` (WP03) are not collected
by any per-PR CI module shard. They run only in the nightly out-of-matrix job. The cause is
the deferred out-of-matrix promotion tracked in open issue #4732, a pre-existing CI
architecture gap that this mission neither creates nor worsens.

Ruling: leave it to #4732 and do not change the shared CI registry in this mission. The PR's
*Tests run* section states that these files were run locally, with counts, and that
per-PR CI does not collect them because of #4732.

## Operator ruling: fold in the pre-existing main red

`tests/specify_cli/cli/commands/charter/test_recompile_preserves_mission_4908.py::test_catalog_mission_has_exactly_one_reader_outside_the_shared_accessor`
fails on this mission's base and on current `main`: the migration
`src/specify_cli/upgrade/migrations/m_4_0_0rc5_heal_template_set_provenance.py` reads
`catalog.get("mission")` directly. The operator chose to fold the fix into this mission as a
separate, clearly labelled commit instead of filing an issue.

## Routed to the fix round

All other confirmed findings: PR-BOUNDARY-001, PR-CONTRACT-001, PR-TESTS-002, PR-TESTS-003,
PR-TESTS-004 and PR-TESTS-005. Also the per-WP review items WP03-C1-002 (a CLI-level test
for a DRG-transitively-reached missing id) and WP03-C1-004 (a CLI-level fail-closed
`--json` test).

## HALT after fix round 2: operator rulings (2026-09-30)

The early-stop rule fired. Fresh sweep 2 (`pr-fresh-2.yaml`) raised findings at
severity 3 or higher, from 1 to 2. `pr-verify-2.yaml` has all 12 prior items resolved.
These rulings REPLACE the acceptance bar for the two findings below.

- **PR-FRESH2-001 (sev 4, vacuous tracked-kinds drift test): compute on demand.** Remove
  the separate `_TRACKED_REFERENCE_KIND_PLURALS` module constant. Its use site(s) call a
  small private function that derives the plurals from `_TRACKED_KIND_TO_GRAPH_ATTR` at
  call time, so exactly one literal exists and drift is impossible by construction. The
  test monkeypatches `_TRACKED_KIND_TO_GRAPH_ATTR` on the module and asserts that the
  function reflects the mutation. Against a scratch copy with a hand-written independent
  plural set, that test must FAIL. Remove the false "mutation-style" docstring claim.
- **PR-FRESH2-002 (sev 3, mismatched document predicates): `collections.abc.Mapping`
  everywhere.** Both the shared accessor in `charter.activation.charter_yaml_io`
  (`catalog_field_from_document` / `catalog_mission_from_document`) and the rc5
  provenance migration's local `catalog` guard use `isinstance(document, Mapping)`
  (and the same predicate for the nested `catalog` value, if one is applied there).
  Behaviour for `dict` / ruamel `CommentedMap` documents is unchanged. A regression test
  with a `types.MappingProxyType` document proves the mission is read and healing
  proceeds.

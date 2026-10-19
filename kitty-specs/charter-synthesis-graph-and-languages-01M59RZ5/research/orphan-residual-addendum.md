# Orphan residual addendum (2026-10-19)

The DRG orphan residual record `kitty-specs/mission-lifecycle-dispatch-drg-closeout-01KV0S99/drg-orphan-residual.md` belongs to an archived Mission and is frozen (`tests/architectural/test_archive_root_byte_identical.py`), so this Mission records the ceiling change here instead.

## 2026-10-19 addendum: ceiling 21 -> 25 (#6379, #6432)

The built-in pin bump of PR #6379 vendored the plan mission's four step contracts, so the shipped graph
gained `mission_step_contract:plan/{plan,research,review,specify}`. They are edge-less by construction
(resolved by the `(mission_type, action)` join, never by traversal), so the shipped-graph orphan count is 25.
`DOCUMENTED_ORPHAN_RESIDUAL` in `tests/specify_cli/cli/commands/test_doctrine_regenerate_graph.py` was raised
21 -> 25 by Mission `charter-synthesis-graph-and-languages-01M59RZ5`. No edges were wired and `packs/built-in/`
was not changed for this. The four nodes were already listed in `_EDGELESS_BY_CONSTRUCTION` in
`tests/charter_offering/drg/migration/test_extractor_projection.py`.

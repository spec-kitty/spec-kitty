# Research: status-state-read-dir-dedup (#5180)

## R-1 Is the duplication still real on main?

Yes (main @ f7fe2094). `workflow_cores.py:311` and `tasks_verdict_persistence.py:694`
are byte-equivalent to `review_artifact_consistency.py:45` minus the `.exists()` degrade.
`placement_seam(root, slug).read_dir(kind)` equals
`resolve_artifact_surface(root, slug, kind).path` for every non-RETROSPECTIVE kind
(`mission_runtime/resolution.py:1728-1760`), so the three differ only in the degrade.

## R-2 Does the phantom actually reproduce?

Yes. With the #154 ambient-ancestor layout (`<tmp>/ambient` is a git repo, mission at
`<tmp>/ambient/repo/kitty-specs/<slug>`), the render copy resolves
`<tmp>/ambient/kitty-specs/<slug>` (non-existent), and
`latest_review_feedback_reference` returns `(None, None, None)` although the handed dir
holds a rejection with a resolvable `review_ref`. The canonical copy resolves the handed dir.

## R-3 Where should the single resolver live?

`specify_cli/missions/_read_path_resolver.py` — see `traces/design-decisions.md` for the
alternatives (post_merge module, status submodule, core/paths) and why they were rejected.
No gate forbids CLI → missions imports; the dead-symbol gate is satisfied by three
non-test callers.

## R-4 Sibling exposure (not folded)

The review-cycle artifact dir resolvers (`review/cycle._review_cycle_wp_dir` and its
adapters, WORK_PACKAGE_TASK kind) go phantom under the same fixture, so
`has_prior_rejection` also depends on them. Different kind, different authority → C-005,
noted in the PR as future architecture.

## R-5 Scouted patch/import risk

No test patches the four functions by string, nor `placement_seam` /
`resolve_canonical_root` inside the three modules. Tests import
`_resolve_verdict_read_feature_dir` (`tests/specify_cli/review/test_cycle_kind_flip.py`)
and `_resolve_lane_state_read_dir` (`test_2959_override_partition.py`) — both are kept as
thin adapters.

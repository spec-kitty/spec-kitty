# Contract: the `--skip-lanes` implementation-evidence window

**Owning code**: `src/specify_cli/consolidation/entry_preflight._resolve_planning_base_commit` and
`_synthesize_no_lane_manifest` (the base), `src/specify_cli/consolidation/wp_evidence.py`
(`lane_evidence_window`, `_scan_lane`, `_RECOVERY`).

## Shape

For a Mission with no `lanes.json` completed with `consolidate --skip-lanes`, the run builds one
synthetic `LanesManifest` whose single lane is the canonical planning lane, whose
`mission_branch` and `target_branch` are the resolved target branch, and whose
`planning_commit_sha` is the evidence-window base.

| Input | Value |
| --- | --- |
| base (`planning_commit_sha`) | the target tip immediately before the commit that introduced `kitty-specs/<slug>/` on the target's **first-parent** line — that commit's first parent, or the commit itself when it is a root commit |
| tip | the resolved target branch |
| window | the net tree diff `base..tip`, with Mission bookkeeping paths excluded |

`--target <branch>` retargets both the manifest and the base resolution.

## Guarantees

1. **Deterministic**: for one repository state the base is the same commit on every run.
2. **Never fabricated**: no timestamp, no current tip, no generated value. If the Mission
   directory is not in the target's first-parent history, or git cannot read the history, the base
   is unset.
3. **Fail closed**: an unset base keeps the evidence axis' `EVIDENCE_WINDOW_UNCOMPUTABLE` refusal
   (leading the line, unliftable). Nothing passes vacuously.
4. **No gate relaxation**: the same axis judges the window as for a recorded manifest —
   `IMPLEMENTATION_MISSING` (no attested no-implementation), `OWNERSHIP_UNRESOLVED`,
   `IMPLEMENTATION_UNREADABLE` and `REVIEW_NOT_INDEPENDENT` keep their codes, order and
   strictness.
5. **No git call when `lanes.json` is present**: the synthesized path is the only caller.

## Recovery contract

An `EVIDENCE_WINDOW_UNCOMPUTABLE` refusal names both shapes:

- a recorded but unpinned `lanes.json`: run `spec-kitty agent mission finalize-tasks` to record the
  planning commit (#7210);
- a Mission with no `lanes.json`: `finalize-tasks` records nothing this gate reads, so commit the
  Mission's planning artifacts (`kitty-specs/<slug>/`) on the target branch and re-run.

## Out of contract

A Mission-side branch that merges the target in and is then fast-forwarded onto the target widens
the tree diff: the base lands below the Mission's artifacts. Refs cannot reconstruct a ref's prior
tip, so this is documented and tracked as #7229, not silently claimed as covered.

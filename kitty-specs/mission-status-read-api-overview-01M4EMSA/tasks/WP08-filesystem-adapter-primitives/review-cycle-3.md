---
affected_files: []
cycle_number: 3
mission_slug: mission-status-read-api-overview-01M4EMSA
reproduction_command:
reviewed_at: '2026-10-12T08:14:12Z'
reviewer_agent: reviewer-renata
wp_id: WP08
---

# WP08 reopened (orchestrator): resolver must follow the full oracle routing rule (DD-105)

WP08 was approved under the earlier 2026-10-12 coordination ruling, which rested on an incomplete oracle probe. The full oracle rule is now recorded in reviews/analyze.ruling.md ("coordination routing, corrected to the full oracle rule") and DD-105. WP07 cycle 3 pins it in `conformance/resolver-cases.json` with 20 new rows, each expectedClass from the oracle (lane-a bb4ac6d23; lane-b receives it at your claim).

| id | severity | where | problem | remedy |
|---|---|---|---|---|
| R1 | high | ReadDirResolver.java (`coordinationDir` and the routing decision) | For a stored `coord` or `lanes_with_coord` topology with the coordination Mission folder present, Java reads COORD only when `coordination_branch` is a non-blank string. The oracle reads COORD whenever the coordination folder holds a `meta.json`, whatever `coordination_branch` holds, and otherwise only when `coordination_branch` is a non-blank string. Source: `src/specify_cli/coordination/surface_resolver.py:1352-1369, 1436-1439` and `_read_path_resolver.py:396-417`. | Implement the full rule. STAT the coordination folder's `meta.json` through the seam (no-follow), and never read its content. Add a stat-only path class for it in `Allowlist` (a new `PathClass`, STAT mode only, with matching PATTERNS/ENTRIES text). Keep the existing ban on READ of the coordination `meta.json`. A symlinked coordination `meta.json` is treated as absent, or as refused, matching the oracle: run it and record the result. |
| R2 | medium | ReadDirResolverTest.java (`Case` record, lines 44-46 and 154) | The record cannot represent the new rows: it has no `coordMeta` and no `coordRootKind`, and `coordinationBranch` is a boolean. | Widen the record: `coordMeta` (present/absent), `coordRootKind` (registered/husk), and a three-state `coordinationBranch` (present/absent/empty). Load or mirror ALL rows of the lane's `conformance/resolver-cases.json`, including WP07's 20 new ones, and assert each `expectedClass`. Reading the committed file directly is preferred over mirroring. |
| R3 | medium | README.md (WP19's file, with an AllowlistReadmeParityTest) | A new allowlist pattern breaks README parity. | Update the README fence to equal `Allowlist.PATTERNS`. This is an out-of-map edit of WP19's README: make it its own commit with a one-line rationale. |

Red first: with the lane-a rows merged, the widened resolver test fails on the meta-present, branch-absent/empty rows before the fix. Revert rows:
- drop the meta stat, and the meta-present rows go red;
- drop the branch fallback, and the control rows go red;
- READ the coordination meta instead of stat-ing it, and the allowlist flow test goes red.

Run all mutations in a scratch worktree.

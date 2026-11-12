---
affected_files: []
cycle_number: 1
mission_slug: coord-closeout-leftovers-01M78FRR
reproduction_command:
reviewed_at: '2026-11-12T19:22:27Z'
reviewer_agent: claude-reviewer
wp_id: WP06
---

# WP06 review feedback (cycle 1) — reviewer: claude-reviewer (reviewer-renata)

**Verdict: changes requested.** Red→green is genuine (3 cells red at b7375b95 with
"No merge needed", 66/66 targeted + 856 passed / 3 skipped over tests/acceptance and
tests/specify_cli/acceptance on the lane tip; ruff, format, C901 clean). One finding
breaks FR-010's "name where the record went".

## F1 (blocking): `_acceptance_record_branch` names the wrong branch for an explicit coordination Mission on an unprotected target

`_acceptance_record_branch` returns `meta.coordination_branch` whenever one is recorded.
The record is not committed there for an explicit (`topology_source: explicit`)
`coord` / `lanes_with_coord` Mission whose target is unprotected: its PRIMARY partition
lives on the target (`mission_runtime.resolution._default_mission_primary_ref` returns
the fallback ref for any non-default Mission), and `accept_primary_ref(record_dir, policy)`
returns the unprotected branch checked out at `feature_dir`, so `commit_for_mission`
commits the record on the target.

Reproduced (scratch repo, lane-tip `src` on PYTHONPATH):
`git checkout -b devel && spec-kitty agent mission create probe-dev --topology lanes_with_coord`
→ meta committed on `devel` ("Add scaffold for mission probe-dev-..."), `mission_branch: null`,
`coordination_branch: kitty/mission-probe-dev-...`; then
`_acceptance_record_branch(feature_dir, "devel")` → `kitty/mission-probe-dev-...`, while
`accept_primary_ref(feature_dir, ProtectionPolicy.resolve(repo))` → `devel` (unprotected).
`accept` from `devel` therefore prints "Acceptance recorded on `kitty/mission-probe-dev-...`"
for a record that went to `devel`.

Fix direction: name the branch the commit actually landed on rather than re-deriving it
from meta keys — e.g. carry the branch out of `_commit_acceptance_meta` / the router
result, or resolve it the way the commit does (`accept_primary_ref`, falling back to the
coordination branch only when that returns `None` for a protected/detached checkout).
Add a cell for explicit `lanes_with_coord` on an unprotected target (record on target)
beside the existing default-Mission cell. When no commit was made (`--no-commit`,
`unchanged`) the line should not claim a branch it did not write to.

## F2 (should fix or justify in the WP): flat Mission with `done` but unconsolidated code lanes still says "No merge needed"

`_has_lanes_to_consolidate` treats only `approved` WPs of code lanes as pending. `done` is
not set only by consolidate: `approved -> done` is an unforced, evidence-gated transition
(`validate_transition('approved','done')` only asks for reviewer evidence), and an unforced
`in_review -> done` is a recognised path (CLAUDE.md, approval-bound section). A flat `lanes`
Mission whose WPs were moved to `done` by hand, not yet consolidated and not landed, gets
"No merge needed" — the reverse of FR-010. Since `mission_has_landed` already answers the
"landed" question, "any code lane in lanes.json and not landed" is the tighter predicate; if
the `approved`-only heuristic is deliberate (e.g. pre-landing-record legacy Missions accepted
after a merge), say so in the docstring and pin it with a cell.

## F3 (nit): use the planning-lane seam

`lane.lane_id != PLANNING_LANE_ID` bypasses `specify_cli.lanes.compute.is_planning_lane`,
whose docstring asks call sites not to compare against the constant (#1666); the same module
already uses `is_planning_lane` (`_accepted_lane_roots`). Also consider reusing
`acceptance_lane_derivations(summary)["merge_pending_wps"]` instead of re-reading
`summary.lanes["approved"]`.

## Verified OK
- Scope: only `_build_acceptance_instructions` (+2 kwargs), its call in `perform_acceptance`,
  and the three new helpers changed in `acceptance/__init__.py`.
- single_branch Missions (planning lane only, no coordination) keep "No merge needed" /
  existing off-target text; pr and checklist arms unchanged.
- Coordination Mission after landing → "No merge needed" (mission_has_landed short-circuit).
- Commit trailers present on b7375b95 and fc9635d8.

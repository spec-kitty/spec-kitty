---
affected_files: []
cycle_number: 1
mission_slug: 7091-accept-coord-residual-artifact-commit-01M6G9GS
reproduction_command:
reviewed_at: '2026-11-03T09:26:46Z'
reviewer_agent: reviewer-renata
wp_id: WP01
---

# WP01 review — cycle 1 (reviewer-renata)

**Verdict: reject (1 blocking finding).** The defect is identified correctly, the red-first
proof is real, and the flat-mission control is good. But the chosen fix reverses a recorded
ruling and fails a standing guard; it needs a different seam.

## B1 (blocking, high) — classifying `mission-events.jsonl` reverses #5669 and breaks its C-002 guard

`4fde4459f1 fix(review): mission-events.jsonl is a scoped dirty-gate survivor (#5669)` recorded
that this file is **deliberately NOT a `MissionArtifactKind`** and **must not join the global
churn owner**: it has a keep-local ruling and live research-gate readers, so the destructive
accept/consolidate/merge gates must keep treating its churn as real dirt. That boundary is
pinned by `tests/review/test_mission_events_dirty_survivor_5669.py::test_global_churn_owner_still_treats_mission_events_as_real_dirt`.

With `MissionArtifactKind.MISSION_EVENT_LOG` in `_PLACEMENT_ARTIFACT_KINDS`, that guard fails:

```
tests/review/test_mission_events_dirty_survivor_5669.py::test_global_churn_owner_still_treats_mission_events_as_real_dirt
E   AssertionError: assert True is False
E    +  where True = is_toolchain_generated_churn('kitty-specs/some-slug/mission-events.jsonl')
```

`docs/architecture/artifact-placement-seam.md` ("Unclassified kinds (`None`) have one meaning
(#5697)") states the same thing in prose: "`mission-events.jsonl` (deliberately not a kind,
#5669 — keep-local, must stay real dirt)". A bug-fix PR is not the vehicle to reverse it, and
the reversal is not needed to close #7091.

**Required change.** Revert the classifier work (`MissionArtifactKind.MISSION_EVENT_LOG`,
`_PLACEMENT_ARTIFACT_KINDS`, `_MISSION_FILE_KIND_BY_BASENAME`, the partition-pin edit in
`tests/architectural/test_write_surface_placement_guard.py`, and the reclassification of
`mission-events.jsonl` in `tests/mission_runtime/test_artifact_none_classification.py`).

Fix the actual defect at the seam that produced it — `accept.py::_run_residual_acceptance_commit`
(issue #7091's own expected outcome (b): "treats the coordinator-owned path as already handled
... and returns 0"). A coordination-worktree residual path that the ONE classifier does not
recognise (`kind_for_mission_file(...) is None`) is not a mission artifact: no surface owns it,
`safe_commit` correctly refuses to stage it from the primary root, and the residual tidy-up
commit must not turn that into a mission failure. Subtract those paths from the coordination
leg's commit batch and report them (an `AcceptanceResult.notes` entry naming the path and the
#5669 keep-local rationale) so the outcome is not silent. Use the classifier verdict, not a
basename literal, and do not widen `is_self_bookkeeping_churn` / `is_toolchain_generated_churn`
(the #5669 guard must stay green untouched).

A residual path in the coordination worktree that classifies to a **PRIMARY** kind (e.g. a dirty
`spec.md`) must keep flowing to the router and keep refusing loudly — that is real misplaced
dirt, not a local log.

## B2 (high) — the regression test must pin the survivor, not a commit to the coord branch

Because the fix is now "keep the log local, report it, return 0", the coordination test in
`tests/specify_cli/cli/commands/test_accept_residual_partition.py` must assert the correct
outcome:

- `_run_residual_acceptance_commit` does not raise (the #7091 exit-1 arm);
- the primary branch head is unchanged;
- the coordination branch does **not** gain the log (it stays uncommitted, per #5669);
- a coordination-owned artifact dirtied in the same run (e.g. `acceptance-matrix.json`) still
  commits on the coordination branch — the survivor must not disable the leg;
- an acceptance note names the deferred path.

The flat-mission control (log commits on its own branch) is correct as written; keep it.

## B3 (medium) — keep the two #5669 guards as the proof

Add nothing to the global churn owner. The existing
`tests/review/test_mission_events_dirty_survivor_5669.py` negative controls and C-002 guard are
the evidence that this fix is scoped; state that in the WP summary so a later reader sees the
boundary was respected rather than forgotten.

## What is good and must survive

- The reproduced failure and its exact message are correct (verified on this branch before the
  change).
- Driving the pre-existing seam (`_run_residual_acceptance_commit`) rather than a mocked root is
  right, and the real `_build_coord_mission` fixture reproduces the `safe_commit` refusal.
- The flat-mission control is a genuine scope-ceiling pin.

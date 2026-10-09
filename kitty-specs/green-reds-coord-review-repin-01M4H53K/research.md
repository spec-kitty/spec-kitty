# Grounding — #5928 / #5948 (coord review `[refused]` → `[ok]`)

## Repro (red on main @ ef53a433)
`PWHEADLESS=1 .venv/bin/python -m pytest -n0 -k "TestAgentActionReviewTextEnvelope and test_coord_mission_prompt_skeleton" tests/characterization/test_trio_json_envelope.py`
→ 1 failed. Only `assert "[refused]" in text` fails; exit_code==1, no `[Errno 2]`, `[review] Commits recorded:` all PASS.

## Current actual output (normalized)
```
Branch: trio-integration (target for this mission)
WP01 claim was committed; the lane sync after the for_review -> in_review commit failed: <...>
[review] Commits recorded:
  - kitty/mission-trio-coord-review-0196D7F7  <SHA>  chore: Start WP01 review [reviewer-renata]  [ok]
```

## Mechanism (traced)
- `agent action review` on a coord mission with a materialized coord worktree + a `for_review` WP with NO prior implement/lane commits:
  1. Claims review → records the "chore: Start WP01 review" commit on the coord branch (`BookkeepingTransaction`, `commit_workflow_change`).
  2. Lane auto-rebase/sync after the coord commit FAILS (no lane commits to sync).
  3. `_sync_lane_or_revert` (workflow_executor.py:205) tries to revert the coord commit + roll back status rows.
  4. Rollback REFUSES: `STATUS_ROLLBACK_REFUSED` (mission_write.py:411) — "the rows after the capture point are already committed at HEAD" → `RollbackRefusal.TAIL_ALREADY_COMMITTED`.
  5. Line 248-249: `if outcome.refusal is not TAIL_ALREADY_COMMITTED: _mark_receipt_refused(...)` → since it IS TAIL_ALREADY_COMMITTED, the receipt is NOT marked refused → stays `committed` → glyph `[ok]`.
  6. `_report_refused_rollback` (line 139-151) prints the honest prose "WP01 claim was committed; the lane sync after ... failed"; exit 1.

## Why `[ok]` is the honest/correct marker
- The commit genuinely IS present on the coord branch (rollback could not/would not cut it — fail-closed). Reporting it `[refused]` when it is actually committed was the **misleading-receipt defect** closed by #5440 (and #5819/#5804). The receipt renderer comment (workflow.py:981-986) and the revert guard comment (workflow_executor.py:246-247) both state this intent explicitly.
- The command still FAILS (exit 1) and still discloses the lane-sync failure in prose — operator is NOT misled about success.

## Implement variant passes — why
- Implement coord case uses a `planned` WP; first implement claims + materializes lane and succeeds fully (exit 0 happy path). Review's lane sync fails because there are no lane commits yet. The exit-1 asymmetry is itself expected/pinned; ONLY the glyph changed.

## Verdict
STALE TEST EXPECTATION. The `[refused]` pin encodes pre-#5440 behavior where a committed-but-sync-failed coord commit was mislabeled refused. Honest-receipt discipline now reports `[ok]` (commit present) + prose refusal + exit 1. Product behavior is correct; the characterization pin is out of date. Consistent with EPIC #5106 "red-on-main & stale tests" and the issue's own "could also be that the test's expectation is stale."

## Proposed smallest-viable fix (test side)
Update `TestAgentActionReviewTextEnvelope.test_coord_mission_prompt_skeleton`:
- Replace `assert "[refused]" in text` with `assert "[ok]" in text` (receipt is honestly committed), AND
- Add `assert "claim was committed; the lane sync after" in text` to pin the meaningful honest-failure prose (not just flip a glyph), keeping exit 1 + no `[Errno 2]` + `[review] Commits recorded:`.
- Update the test docstring: it currently says "reports the refused coordination branch" — now stale; reword to the honest-receipt behavior.
No product change. Red-first: the updated assertions are RED on current main's pre-edit expectation and GREEN after re-pin; the product is already correct.

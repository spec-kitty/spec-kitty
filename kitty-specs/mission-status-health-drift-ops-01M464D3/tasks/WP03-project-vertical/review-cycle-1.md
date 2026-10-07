---
affected_files: []
cycle_number: 1
mission_slug: mission-status-health-drift-ops-01M464D3
reproduction_command:
reviewed_at: '2026-10-06T12:59:09Z'
reviewer_agent: user
wp_id: WP03
---

# WP03 review cycle 1 — changes requested

Full review: scratchpad `c12-wp03-review.md`. Fix all four items; nothing else is in scope.

1. **S3 — `.inf` raises.** `schema_version: .inf` in the metadata file makes `build_project` raise `OverflowError` (via `ProjectMetadata.load` / `get_project_schema_version`). FR-002/FR-003 require that the read does not raise. Add `OverflowError` to the builder's except tuples, and plant `.inf` in row 1 or row 3 so a revert of the fix goes red.
2. **S3 — unauthorised timeout loosening.** The reality Project test timeout went from 120 to 300 s. The plan allows no in-test case over 120 s, and the test measures 22.5 s alone (1.7 s in the module run). Revert it to 120.
3. **S2 — dead guard.** Removing `_shape_is_safe` leaves all 26 project tests green, because the residual `AttributeError`/`TypeError` catch makes it equivalent. Drop the guard (the residual catch is the single mechanism), and keep the tests green.
4. **S1 — unasserted gap change.** Nothing asserts that `DEFERRED_GAPS` now holds three gaps or that "project branch" is gone. Add that assertion.

NFR-009: quote the PRIMARY-checkout figure in your hand-off (574 Missions, 37 fallbacks, 35.9 s cold / 16.8 s warm, under 120 s). The lane's 516 fallbacks are a worktree artefact.

Gates after the fix: the targeted project, reality and ratchet tests; the ten contract tools; the negative runner; and the ruff pair. The battery fast leg is binding; re-run the heavy legs only if a non-test file outside the builder changes. Every repo-wide command goes behind the directory guard.

# WP01 review feedback, cycle 1 (reviewer-renata)

T001 (pure move), T002 (shared runner, 4 -> 4) and the five red tests are good. The red tests fail for the #5573 lane / missing-refusal reason only, and both positive controls pass. The old `str.replace` amendment really was a no-op on base: after run 1 the block list is re-serialised as `owned_files:\n- src/alpha.py`, which I confirmed with a probe. The `_resolve_status_read_dir` re-export, `add_owned_file` and the `qa-main` target are all accepted. ruff, format and mypy (on the changed files) are clean, and the trailers are correct.

**Issue 1 (blocking): the "refuse before any write" check can still be faked.** This breaks the binding squad fold and FR-005 ("The refusal comes before any status or manifest write").

Where: `tests/integration/test_refinalize_keeps_started_lanes.py:288-312`. The comment at L293-294 and the red commit message both say the added WP03 means a late refusal "would leave a WP03 seed event and break byte identity". That is not true on this base. When `finalize_tasks` exits with `typer.Exit`, its handler (`mission_finalize.py`, the `except typer.Exit:` block) calls `_restore_status_surface(status_surface)` and `_restore_mission_write_scope_beside_status(...)` (#5641 atomicity). Those calls give the status log, the WP files, `tasks.md` and `meta.json` their bytes back, and the guard rewinds any status commit.

Evidence: I wrote a probe (since deleted) that monkeypatches `mission_finalize._compute_and_write_lanes` to print the exact `LANE_MEMBERSHIP_FROZEN` envelope and raise `typer.Exit(1)`. That is a refusal at the write chokepoint, after `_emit_tasks_started`. On the same fixture as this test it gave exit 1, an empty snapshot diff and the same HEAD, so `test_two_started_lanes_forced_together_refuse_before_writing` would pass.

Impact: WP03 must not edit these tests. A WP03 that preflights only under `--validate-only` and refuses at the chokepoint in write mode would pass this test and WP03's own US2 AS2 (`--validate-only`) test.

Fix:
- Keep the byte-identity and HEAD assertions; they are the SC-003 observable.
- Add a direct "no write happened" observation that the restore cannot hide. Wrap the real writers without replacing them, so the real path still runs: the status-event append that finalize's seeding goes through (find the call site behind `_emit_tasks_started` / bootstrap seeding) and `write_lanes_json`. Record calls during the refused `_finalize`, and assert both lists are empty.
- Show that this observation is non-vacuous: in `test_new_wp_without_collision_is_seeded_positive_control`, assert the same spies DO record calls (WP03 seeding and the lanes write).
- Correct the L293-294 comment and the red commit's claim. Amending the red commit message is optional; a follow-up red-tightening commit is fine, since it is still red-first and comes before any fix.
- Confirm that the test stays red on base for the exit-code reason (`assert 0 == 1`).

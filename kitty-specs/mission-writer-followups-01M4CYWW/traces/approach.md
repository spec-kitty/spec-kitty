# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-08 · claude · Seed: extend the PR 5890 Mission write primitive rather than add a second door. Route every meta.json/frontmatter/matrix read-modify-write through mission_write_lock (key resolved before entering the lock), close the gate by construction (Rule 4 + Rule 1/2/3 extensions, empty allowlist, synthetic offender + near-miss + self-mutation per rule). Runtime: delete the speculative rollback, run the retrospective gate as commit_advance's abort-only before_run_completed hook. Planning: canonicalize runtime templates on packs/built-in/missions, insert an analyze DAG step with a currency guard injected from specify_cli, drift-safe for in-flight runs. Red-first deterministic cross-thread interleavings per writer family.

2026-10-08 · python-pedro · WP01 red-first: tests/status/test_mission_lock_key.py (commit 32cc1fbbb) failed on pre-fix code: mission_write_lock(primary 060-test) held 060-test.status.lock while the transaction key is 060-test-01COORD0; coordination dir likewise; capture_rollback_point(coord) raised 'requires the Mission write lock' under a primary-dir hold. Mutations (key=feature_dir.name; lock removed) fail the key and two-thread tests.

2026-10-08 · claude · WP13 red-first (T005): tests/status/test_mission_lock_order.py on the bare-directory coordination fixture (060-test primary, 060-test-01COORD0 coord) failed 14 of 19 before the fix: direct callers locked 060-test.status.lock while the transaction locks 060-test-01COORD0.status.lock; the lifecycle<->claim two-thread test deadlocked (both threads FeatureStatusLockTimeoutError); coord_seed nested mission_lock_key returned 060-test after meta flatten; owned-root hold not found from the main root. Command: .venv/bin/python -m pytest tests/status/test_mission_lock_order.py -q

2026-10-08 · claude · WP02 red-first: tests/specify_cli/test_locked_meta_writers.py (commit 940775817) ran 6 two-thread overlaps (record_acceptance/set_target_branch, set_origin_ticket/record_discard, set_documentation_state/set_vcs_lock, clear_merge_metadata/set_origin_ticket, flatten/record_acceptance, set_target_branch/flatten) against the unlocked setters: 6 failed, each with the second writer's field lost. Pause point is the fail-closed reader (writer A held after its read until B finishes or 0.5s), no sleeps.

2026-10-08 · claude · WP03 red-first: 20 overlap cases (6 doc-state, 7 consolidation, 7 migrations) and 21 lock-acquisition cases failed on the pre-fix code with 'the locked writer's field was lost' / 'wrote meta.json without taking the Mission lock'; all pass after the fix; 5/5 repeats; mutation (mission_write_lock as nullcontext) fails all 20 overlap cases.

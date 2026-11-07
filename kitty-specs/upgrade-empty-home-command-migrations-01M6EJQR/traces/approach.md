# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-02 · implementer-pedro · WP01 red evidence: tests/upgrade/test_empty_home_command_migrations.py — test_dated_project_removes_marked_command_file_under_an_empty_home FAILED (spec-kitty.specify.md still exists after upgrade under an empty home) and test_same_commit_leaves_the_same_tracked_state_in_both_homes FAILED (the bootstrapped arm also kept the file: _global_command_file_present reads Path.home(), which no home pin reaches). 4 guards passed.

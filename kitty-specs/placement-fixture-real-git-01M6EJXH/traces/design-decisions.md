# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-02 · pi/deepseek-v4.1-flash-1017 · Fix is in the fixture, not the product. A bare .git marker makes git run and refuse; #6673's classifier deliberately treats that as 'tracked copy unknown' and cutover_mission skips with TRACKED_META_UNAVAILABLE (pinned by test_read_tracked_meta_6673.py::test_a_git_that_refuses_to_answer_is_not_read_as_nothing_tracked). A real git init repo reaches PlacementMismatchError (probe verified both branches before planning).

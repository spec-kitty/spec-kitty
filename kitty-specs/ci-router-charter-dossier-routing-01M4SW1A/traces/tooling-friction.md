# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-13 · Stijn Dejongh · capture_shard_timings.py --module dossier requires the dossier registry row to already exist (resolve_test_dirs looks it up), so the registry row must be committed/present before the measured timings capture can run. Order within IC-03: scrub group -> registry row (provisional shard_count) -> capture -> finalize shard_count.

2026-10-13 · Stijn Dejongh · In this cloud container, spec-kitty agent tasks move-task hangs/exceeds 90s (status reduction + git event-log commit; the origin-freshness gate also hung until SPEC_KITTY_ORIGIN_CHECK=off). Per-WP Kanban transitions were therefore not fully driven; mission substance (ATDD red-first proof, all guard suites green, measured timings, independent review) is complete and verified independently. Recorded for the next mission.

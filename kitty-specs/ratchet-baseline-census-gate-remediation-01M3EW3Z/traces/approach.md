# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-09-26 · claude · Pre-spec grounding squad (4 lenses) found 3 of 5 issue premises stale: gates cited by #3011 and #3026 were deleted by earlier sanitation missions (01KZME3P WP13, #3285). Operator chose retire for both, full migration for #5085, act-now for #2631.

2026-09-26 · python-pedro · WP02 RED (07d5d0c1): 8 failed / 3 passed in test_built_in_location_authority.py. Stale test names src/kernel/paths.py:88 and src/specify_cli/runtime/home.py:79 (suppress no live join). Drift: kind_vocabulary.py, neutrality/lint.py, template/manager.py partitions change under a prepended blank line (suppressed -> unexpected); kernel/paths.py and runtime/home.py drift params fail the non-emptiness count (0 vs 1); drift_files_meet_floor fails on the same two. Planted join at kernel/paths.py:88 is suppressed by the dead pin, not reported. Gate + both negative-bite tests stay green.

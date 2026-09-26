# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-09-26 · claude · Pre-spec grounding squad (4 lenses) found 3 of 5 issue premises stale: gates cited by #3011 and #3026 were deleted by earlier sanitation missions (01KZME3P WP13, #3285). Operator chose retire for both, full migration for #5085, act-now for #2631.

2026-09-26 · python-pedro · WP02 RED (07d5d0c1): 8 failed / 3 passed in test_built_in_location_authority.py. Stale test names src/kernel/paths.py:88 and src/specify_cli/runtime/home.py:79 (suppress no live join). Drift: kind_vocabulary.py, neutrality/lint.py, template/manager.py partitions change under a prepended blank line (suppressed -> unexpected); kernel/paths.py and runtime/home.py drift params fail the non-emptiness count (0 vs 1); drift_files_meet_floor fails on the same two. Planted join at kernel/paths.py:88 is suppressed by the dead pin, not reported. Gate + both negative-bite tests stay green.

2026-09-26 · python-pedro · WP01 RED: widened ban (import-agnostic tuple arm, Path()/div elements, 2-/3-tuples, embedded path:line[:op] keys, line-keyword records, class-body seeds, _exemptions/*.txt text arm) with EMPTY _POSITIONAL_ANCHOR_EXEMPTIONS fails the two standing gates with exactly 94 sites: _KNOWN_JOIN_ALLOWLIST 6 / kernel _PRE_EXISTING_EXEMPTIONS 2 / destructive _ALLOWLIST 22 / mutation _ALLOWLIST 56 / overwrite _ALLOWLIST 2 / os-detect-ban-deferred.txt 3 / mypy-narrowing.txt 2 / sanctioned-raw.txt 1. No other hits (no false positives). Red for the intended reason (#5068); also red: exactness + real-kernel-gate subset tests (same 94/2 sites).

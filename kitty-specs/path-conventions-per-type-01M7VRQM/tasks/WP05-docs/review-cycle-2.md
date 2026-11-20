---
affected_files: []
cycle_number: 2
mission_slug: path-conventions-per-type-01M7VRQM
reproduction_command:
reviewed_at: '2026-11-20T12:06:58Z'
reviewer_agent: claude::generic-reviewer
wp_id: WP05
---

**Cycle-1 issue: fixed.** The framing sentence now matches the order of `format_errors`.

**Issue 1 (blocking, a CI gate goes red): US-spelling in the how-to.**

`tests/docs/test_docs_spelling_live.py` fails 2 tests at f6e1d599 (`test_us_pass_clean`, `test_production_entry_point_exits_zero`). The same tests are green on base main a053b674:

```
docs/guides/how-to/missions/accept-and-merge.md:158: [us-spelling] honours — fix: honors
```

The word comes from 8ada3b14 ("Every accept path honours it"). The cycle-1 run covered only a subset of `tests/docs`, which missed it. Fix: change it to "honors". The ADR amendment uses "honours" too (line 64 of the WP diff). The live pass does not scan the ADR, but changing it as well keeps the two consistent.

Verify with `pytest tests/docs/test_docs_spelling_live.py` (or the whole `tests/docs`: 2252 passed and 2 failed here, 2254 passed on base).

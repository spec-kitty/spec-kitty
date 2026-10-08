# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-07 · claude · Seed: dirty tree -> commit only upgrade-changed clean paths (01M4AKVTD3XMCEAJ9TDYBBAJVT); --no-verify removed, no flag (01M4AKVWCWHYNTGTRGXJ0WJ0VM); widen (01M4AY1QM21535SC7AZ6BC9NXT); safe-commit CLI WP05 included (01M4AY1VGXRZYAYGQ0883K7JZQ); 6 merge-conclusion sites allowlisted as priced debt (01M4AY1ZK6PCTM1DKHVWTFJV5W); skill text in scope (01M4AY23FFY71BJA2JRG39SMB6). #5811 interaction: the repair runs after commit_churn and its rewrites are never committed.

2026-10-07 · python-pedro · Ignored-at-baseline probe: kernel status_entries reports a collapsed ignored directory with a bare path and is_directory=True (no trailing slash), so _ignored_paths appends the slash itself; without it the dir-prefix match in _under_ignored never fired (caught by test_prepare_excludes_ignored_at_baseline_even_after_unignore).

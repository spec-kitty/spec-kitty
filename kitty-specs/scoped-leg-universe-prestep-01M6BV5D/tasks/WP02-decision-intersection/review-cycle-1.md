---
affected_files: []
cycle_number: 1
mission_slug: scoped-leg-universe-prestep-01M6BV5D
reproduction_command:
reviewed_at: '2026-11-01T17:27:10Z'
reviewer_agent: reviewer-renata
wp_id: WP02
---

# WP02 review — changes requested (both low, one commit)

Reviewed by reviewer-renata. Checklist: 1 dead code PASS (`selected_gates` is called by
`cmd_consumers`); 2 synthetic fixture PASS (the tests drive `main([...])` against a real file, and
the faked `battery_part_files`/`universe_consumers` are the pre-existing boundary fixture, not the
thing under test); 3 silent return PASS (`None` = "no restriction", documented); 4 FR coverage
PASS (FR-001..FR-004, FR-006 each have an assertion through the CLI); 5 frozen surface PASS (the
battery pytest command line and the step order are untouched — the shape test's
`_FORBIDDEN_IN_PYTEST_STEP` still holds); 6 locked decision PASS (C-002: `collect` is untouched,
so the universe itself is never narrowed); 7 ownership PASS (diff is exactly lane-b's
`write_scope`); 8 fragility PASS (the `OSError` from an unreadable file propagates to `main`'s
handler: non-zero exit, nothing on stdout).

## F1 (low) — `selected_gates` has a parameter nothing exercises

`selected_gates(gates_file=None, environ=None)` takes an `environ` mapping "for testability", but
no caller passes it and no test uses it: the environment path is tested through `monkeypatch` +
`main([...])`, which is the better seam anyway. Speculative generality in a CI decision path is
how a second environment source appears a year later.

**Fix**: drop the parameter and read `os.environ` directly (the module already does), or pass it
from a test. Dropping it is one line and removes the ambiguity.

## F2 (low) — the decision and the leg react differently to a foreign gates file

Given a file that names only the *other* leg's gates, the decision answers `false` (skip the
pre-step) while `battery_partition_plugin.build_state` raises `UsageError` ("selects none of part")
for the same input. Both are safe — the leg reds in its own step either way, and no test can then
collect for itself — but the asymmetry deserves one sentence in the docstring so the next reader
does not "fix" it into a duplicated failure.

**Fix**: state it in `selected_gates`' or `cmd_consumers`' docstring; no behaviour change.

# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · python-pedro · Grounded the sweep on the code rather than on the issue text: `status/reducer.py:17-18`, `:205`, `:401` and `spec_kitty_events.diary._order_transitions` (spec-kitty-events 11.3.0) fix every fact the corrected wording states, including the approved-departure lift and the narrower non-approval residual.

2026-10-30 · python-pedro · Red-first ordering: WP01 landed the guard and recorded it failing 5/9 on the unmodified tree; WP02 corrected the living pages, the domain plan, `AGENTS.md`/`CLAUDE.md` and the `preflight.py` docstring; WP03 added the ADR amendment plus the changelog entry, which turned the guard fully green. That ordering means every corrected sentence is one the guard can observe.

2026-10-30 · python-pedro · ADR handling: `2026-10-01-2` keeps its decision text and gains `## Amendment 2026-10-30 (Accepted)`, matching the record's own 2026-10-03 / 2026-10-12 / 2026-10-29 amendment pattern. `git diff -U0` shows exactly one removed line (the `updated:` frontmatter value).

2026-10-30 · python-pedro · History compaction: rebuilt the branch on `origin/main` as four logically sliced commits (guard test, living docs, ADR + changelog, mission records). The tree hash before and after is identical (`423e2ab8461238cd07f53a4c597b512573f2ff1a`), so nothing but history changed.

2026-10-30 · python-pedro · Freeze discovery: the CI architectural fast gate refused the G-3 edit (`docs/architecture/event-ledger-writers-and-readers.md changed after the freeze`). Rather than re-pinning a freeze without operator approval, reverted that page and filed #6822; the guard now documents why it does not cover the page.

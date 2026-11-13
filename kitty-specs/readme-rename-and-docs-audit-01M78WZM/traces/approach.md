# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-12 · claude · Review cycle 1, issue 9: 07bc8d702 added _renamed_section_index with its test in one commit, so that behaviour change had no red commit of its own. Every fix in cycle 1 is red-first in its own commit. Issue 8: a58f59977 and 07bc8d702 also edited the WP task file; from cycle 1 on, bookkeeping is kept out of code commits. Neither older commit is rewritten.

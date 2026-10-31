# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · python-pedro · Pinned the acquire bound to None rather than to a large number: a bounded-but-large value would reintroduce a second wall clock whose relationship to the harness budget has to be re-argued on every future edit. None is the documented unbounded mode open_decision already uses.
